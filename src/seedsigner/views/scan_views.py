import logging
import re

from gettext import gettext as _
from seedsigner.helpers.l10n import mark_for_translation as _mft
from seedsigner.models.settings import SettingsConstants
from seedsigner.helpers.anti_exfil_protocol_v1 import Stage
from seedsigner.views.view import BackStackView, ErrorView, MainMenuView, NotYetImplementedView, View, Destination
from seedsigner.gui.screens.screen import ButtonOption

logger = logging.getLogger(__name__)



class ScanView(View):
    """
        The catch-all generic scanning View that will accept any of our supported QR
        formats and will route to the most sensible next step.

        Can also be used as a base class for more specific scanning flows with
        dedicated errors when an unexpected QR type is scanned (e.g. Scan PSBT was
        selected but a SeedQR was scanned).
    """
    instructions_text = _mft("Scan a QR code")
    invalid_qr_type_message = _mft("QRCode not recognized or not yet supported.")
    expected_anti_exfil_stage: Stage | None = None
    preserve_psbt_seed = False


    def __init__(self):
        from seedsigner.models.decode_qr import DecodeQR

        super().__init__()
        # Define the decoder here to make it available to child classes' is_valid_qr_type
        # checks and so we can inject data into it in the test suite's `before_run()`.
        self.wordlist_language_code = self.settings.get_value(SettingsConstants.SETTING__WORDLIST_LANGUAGE)
        self.decoder: DecodeQR = DecodeQR(wordlist_language_code=self.wordlist_language_code)


    @property
    def is_valid_qr_type(self):
        return True


    def run(self):
        from seedsigner.gui.screens.scan_screens import ScanScreen

        # Start the live preview and background QR reading
        self.run_screen(
            ScanScreen,
            instructions_text=self.instructions_text,
            decoder=self.decoder
        )

        # A long scan might have exceeded the screensaver timeout; ensure screensaver
        # doesn't immediately engage when we leave here.
        self.controller.reset_screensaver_timeout()

        # Handle the results
        if self.decoder.is_complete:
            if not self.is_valid_qr_type:
                if self.decoder.is_anti_exfil:
                    from seedsigner.views.anti_exfil_views import AntiExfilModeMismatchView
                    return Destination(
                        AntiExfilModeMismatchView,
                        view_args={"received_anti_exfil": True},
                        clear_history=True,
                    )
                # We recognized the QR type but it was not the type expected for the
                # current flow.
                # Report QR types in more human-readable text (e.g. QRType
                # `seed__compactseedqr` as "seed: compactseedqr").
                # TODO: cleanup l10n presentation
                return Destination(ErrorView, view_args=dict(
                    title="Error",
                    status_headline=_("Wrong QR Type"),
                    text=_(self.invalid_qr_type_message) + f""", received "{self.decoder.qr_type.replace("__", ": ").replace("_", " ")}\" format""",
                    button_text="Back",
                    next_destination=Destination(BackStackView, skip_current_view=True),
                ))

            if self.decoder.is_seed:
                seed_mnemonic = self.decoder.get_seed_phrase()

                if not seed_mnemonic:
                    # seed is not valid, Exit if not valid with message
                    return Destination(NotYetImplementedView)
                else:
                    # Found a valid mnemonic seed! All new seeds should be considered
                    #   pending (might set a passphrase, SeedXOR, etc) until finalized.
                    from seedsigner.models.seed import Seed
                    from .seed_views import SeedFinalizeView
                    self.controller.storage.set_pending_seed(
                        Seed(mnemonic=seed_mnemonic, wordlist_language_code=self.wordlist_language_code)
                    )
                    if self.settings.get_value(SettingsConstants.SETTING__PASSPHRASE) == SettingsConstants.OPTION__REQUIRED:
                        from seedsigner.views.seed_views import SeedAddPassphraseView
                        return Destination(SeedAddPassphraseView)
                    else:
                        return Destination(SeedFinalizeView)
            
            elif self.decoder.is_anti_exfil:
                from seedsigner.helpers.anti_exfil_protocol import (
                    AntiExfilProtocolCode,
                    AntiExfilProtocolError,
                )
                from seedsigner.models.anti_exfil_state import AntiExfilFlowState
                from seedsigner.views.anti_exfil_views import (
                    AntiExfilFailureView,
                    AntiExfilModeMismatchView,
                    AntiExfilRequestView,
                )

                if self.settings.get_value(SettingsConstants.SETTING__ANTI_EXFIL) != SettingsConstants.OPTION__REQUIRED:
                    return Destination(
                        AntiExfilModeMismatchView,
                        view_args={"received_anti_exfil": True},
                        clear_history=True,
                    )
                try:
                    package = self.decoder.get_anti_exfil_package(
                        self.settings.get_value(SettingsConstants.SETTING__NETWORK)
                    )
                    state = AntiExfilFlowState.from_package(package)
                    if (
                        self.expected_anti_exfil_stage is not None
                        and state.request_stage != self.expected_anti_exfil_stage
                    ):
                        raise AntiExfilProtocolError(
                            AntiExfilProtocolCode.WRONG_STAGE,
                            _("Expected host reveal message 3, received anti-exfil message {number}").format(
                                number=int(state.request_stage)
                            ),
                        )
                except AntiExfilProtocolError as exc:
                    return Destination(
                        AntiExfilFailureView,
                        view_args={
                            "error_code": exc.code.value,
                            "error_message": exc.message,
                            "security_failure": False,
                        },
                        clear_history=True,
                    )
                except Exception as exc:
                    logger.info(repr(exc), exc_info=True)
                    return Destination(
                        AntiExfilFailureView,
                        view_args={
                            "error_code": "AE_INVALID_MESSAGE",
                            "error_message": "anti-exfil QR could not be decoded",
                            "security_failure": False,
                        },
                        clear_history=True,
                    )
                selected_seed = (
                    self.controller.psbt_seed if self.preserve_psbt_seed else None
                )
                self.controller.anti_exfil_state = state
                self.controller.psbt = state.request_psbt
                self.controller.psbt_parser = None
                self.controller.psbt_seed = selected_seed
                return Destination(AntiExfilRequestView, skip_current_view=True)

            elif self.decoder.is_psbt:
                if self.settings.get_value(SettingsConstants.SETTING__ANTI_EXFIL) == SettingsConstants.OPTION__REQUIRED:
                    from seedsigner.views.anti_exfil_views import AntiExfilModeMismatchView
                    return Destination(
                        AntiExfilModeMismatchView,
                        view_args={"received_anti_exfil": False},
                        clear_history=True,
                    )
                from seedsigner.views.psbt_views import PSBTSelectSeedView
                psbt = self.decoder.get_psbt()
                self.controller.psbt = psbt
                self.controller.psbt_parser = None
                return Destination(PSBTSelectSeedView, skip_current_view=True)

            elif self.decoder.is_settings:
                from seedsigner.views.settings_views import SettingsIngestSettingsQRView
                data = self.decoder.get_settings_data()
                return Destination(SettingsIngestSettingsQRView, view_args=dict(data=data))
            
            elif self.decoder.is_wallet_descriptor:
                from embit.descriptor import Descriptor
                from seedsigner.views.seed_views import MultisigWalletDescriptorView
                descriptor_str = self.decoder.get_wallet_descriptor()

                try:
                    # We need to replace `/0/*` wildcards with `/{0,1}/*` in order to use
                    # the Descriptor to verify change, too.
                    orig_descriptor_str = descriptor_str
                    if len(re.findall (r'\[([0-9,a-f,A-F]+?)(\/[0-9,\/,h\']+?)\].*?(\/0\/\*)', descriptor_str)) > 0:
                        p = re.compile(r'(\[[0-9,a-f,A-F]+?\/[0-9,\/,h\']+?\].*?)(\/0\/\*)')
                        descriptor_str = p.sub(r'\1/{0,1}/*', descriptor_str)
                    elif len(re.findall (r'(\[[0-9,a-f,A-F]+?\/[0-9,\/,h,\']+?\][a-z,A-Z,0-9]*?)([\,,\)])', descriptor_str)) > 0:
                        p = re.compile(r'(\[[0-9,a-f,A-F]+?\/[0-9,\/,h,\']+?\][a-z,A-Z,0-9]*?)([\,,\)])')
                        descriptor_str = p.sub(r'\1/{0,1}/*\2', descriptor_str)
                except Exception as e:
                    logger.info(repr(e), exc_info=True)
                    descriptor_str = orig_descriptor_str

                descriptor = Descriptor.from_string(descriptor_str)

                if not descriptor.is_basic_multisig:
                    # TODO: Handle single-sig descriptors?
                    logger.info(f"Received single sig descriptor: {descriptor}")
                    return Destination(NotYetImplementedView)

                self.controller.multisig_wallet_descriptor = descriptor
                return Destination(MultisigWalletDescriptorView, skip_current_view=True)
            
            elif self.decoder.is_address:
                from seedsigner.views.seed_views import AddressVerificationStartView
                address = self.decoder.get_address()
                (script_type, network) = self.decoder.get_address_type()

                return Destination(
                    AddressVerificationStartView,
                    skip_current_view=True,
                    view_args={
                        "address": address,
                        "script_type": script_type,
                        "network": network,
                    }
                )
            
            elif self.decoder.is_sign_message:
                from seedsigner.views.seed_views import SeedSignMessageStartView
                qr_data = self.decoder.get_qr_data()

                return Destination(
                    SeedSignMessageStartView,
                    view_args=dict(
                        derivation_path=qr_data["derivation_path"],
                        message=qr_data["message"],
                    )
                )
            
            else:
                return Destination(NotYetImplementedView)

        elif self.decoder.is_invalid:
            # For now, don't even try to re-do the attempted operation, just reset and
            # start everything over.
            self.controller.resume_main_flow = None
            return Destination(ScanInvalidQRTypeView)

        return Destination(MainMenuView)



class ScanPSBTView(ScanView):
    instructions_text = _mft("Scan Transaction")
    invalid_qr_type_message = _mft("Expected a transaction")
    preserve_psbt_seed = True

    @property
    def is_valid_qr_type(self):
        # An anti-exfil host request is also a transaction QR. Let the common
        # router enforce the Required/Disabled mode policy and decode it.
        return self.decoder.is_psbt or self.decoder.is_anti_exfil


class ScanAntiExfilHostRevealView(ScanView):
    instructions_text = _mft("Scan host reveal")
    invalid_qr_type_message = _mft("Expected anti-exfil host reveal message 3")
    expected_anti_exfil_stage = Stage.HOST_REVEAL

    @property
    def is_valid_qr_type(self):
        return self.decoder.is_anti_exfil



class ScanSeedQRView(ScanView):
    instructions_text = _mft("Scan SeedQR")
    invalid_qr_type_message = _mft("Expected a SeedQR")

    @property
    def is_valid_qr_type(self):
        return self.decoder.is_seed



class ScanWalletDescriptorView(ScanView):
    instructions_text = _mft("Scan descriptor")
    invalid_qr_type_message = _mft("Expected a wallet descriptor QR")

    @property
    def is_valid_qr_type(self):
        return self.decoder.is_wallet_descriptor



class ScanAddressView(ScanView):
    instructions_text = _mft("Scan address QR")
    invalid_qr_type_message = _mft("Expected an address QR")

    @property
    def is_valid_qr_type(self):
        return self.decoder.is_address



class ScanInvalidQRTypeView(View):
    def run(self):
        from seedsigner.gui.screens import WarningScreen

        # TODO: This screen says "Error" but is intentionally using the WarningScreen in
        # order to avoid the perception that something is broken on our end. This should
        # either change to use the red ErrorScreen or the "Error" title should be
        # changed to something softer.
        self.run_screen(
            WarningScreen,
            title=_("Error"),
            status_headline=_("Unknown QR Type"),
            text=_("QRCode is invalid or is a data format not yet supported."),
            button_data=[ButtonOption("Back to Main Menu")],
        )

        return Destination(MainMenuView, clear_history=True)
