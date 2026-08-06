"""SeedSigner anti-exfil request, approval, error, and response views."""

from __future__ import annotations

from dataclasses import dataclass
from gettext import gettext as _

from seedsigner.gui.components import SeedSignerIconConstants
from seedsigner.gui.screens.screen import (
    RET_CODE__BACK_BUTTON,
    ButtonOption,
    DireWarningScreen,
    QRDisplayScreen,
    WarningScreen,
)
from seedsigner.helpers.anti_exfil_protocol import AntiExfilProtocolError, Stage
from seedsigner.models.encode_qr import AntiExfilQrEncoder
from seedsigner.models.settings import SettingsConstants
from seedsigner.views.view import BackStackView, Destination, MainMenuView, View


class AntiExfilModeMismatchView(View):
    OPEN_SETTING = ButtonOption("Open anti-exfil setting")

    def __init__(self, received_anti_exfil: bool):
        super().__init__()
        self.received_anti_exfil = received_anti_exfil

    def run(self):
        if self.received_anti_exfil:
            headline = _("Anti-exfil transaction")
            text = _(
                "This QR requires protected signing. Set Advanced > Anti-exfil signing to Required."
            )
        else:
            headline = _("Protected signing required")
            text = _(
                "This is a regular transaction QR. Disable Anti-exfil signing to use regular signing."
            )

        selected = self.run_screen(
            WarningScreen,
            title=_("Signing Mode Mismatch"),
            status_headline=headline,
            text=text,
            button_data=[self.OPEN_SETTING],
        )
        if selected == RET_CODE__BACK_BUTTON:
            return Destination(MainMenuView, clear_history=True)
        from seedsigner.views.settings_views import SettingsEntryUpdateSelectionView

        return Destination(
            SettingsEntryUpdateSelectionView,
            view_args={"attr_name": SettingsConstants.SETTING__ANTI_EXFIL},
            clear_history=True,
        )


@dataclass
class AntiExfilFailureView(View):
    error_code: str
    error_message: str
    security_failure: bool = False

    def run(self):
        if self.security_failure:
            headline = _("Protected signing stopped")
            text = _(
                "The transaction or anti-exfil transcript did not match. No signature was produced. "
                "Do not continue with a changed transaction or fresh coordinator randomness. "
                "Repeated failures require investigation and may require sweeping to fresh keys."
            )
        else:
            headline = _("Anti-exfil request rejected")
            text = _("No signature was produced. Error {code}: {message}").format(
                code=self.error_code,
                message=self.error_message,
            )

        self.run_screen(
            DireWarningScreen if self.security_failure else WarningScreen,
            title=_("Anti-exfil Error"),
            status_icon_name=SeedSignerIconConstants.ERROR,
            status_headline=headline,
            text=text,
            button_data=[ButtonOption("Back to main menu")],
            show_back_button=False,
        )
        return Destination(MainMenuView, clear_history=True)


class AntiExfilRequestView(View):
    REVIEW = ButtonOption("Review transaction")

    def run(self):
        state = self.controller.anti_exfil_state
        if state is None:
            return Destination(MainMenuView, clear_history=True)

        if state.request_stage == Stage.HOST_COMMIT:
            headline = _("Protected signing 1 of 2")
            text = _(
                "Review this transaction before creating the nonce commitment. "
                "The transaction will not be signed in this round."
            )
        else:
            headline = _("Protected signing 2 of 2")
            text = _(
                "Review the transaction again. SeedSigner will verify the committed session before signing."
            )

        selected = self.run_screen(
            WarningScreen,
            title=_("Anti-exfil Signing"),
            status_headline=headline,
            text=text
            + "\n\n"
            + _("Session: {session}\nTransaction: {transaction}").format(
                session=state.session_fingerprint,
                transaction=state.transaction_fingerprint,
            ),
            button_data=[self.REVIEW],
        )
        if selected == RET_CODE__BACK_BUTTON:
            return Destination(MainMenuView, clear_history=True)

        from seedsigner.views.psbt_views import PSBTSelectSeedView

        return Destination(PSBTSelectSeedView, skip_current_view=True)


class AntiExfilFinalizeView(View):
    CREATE_COMMITMENT = ButtonOption("Create nonce commitment")
    APPROVE_SIGNATURE = ButtonOption("Approve protected signature")

    def run(self):
        state = self.controller.anti_exfil_state
        seed = self.controller.psbt_seed
        if state is None or seed is None:
            return Destination(MainMenuView, clear_history=True)

        if state.request_stage == Stage.HOST_COMMIT:
            headline = _("Transaction not signed")
            text = _(
                "Create the first anti-exfil response. It contains a nonce opening only and cannot authorize the transaction."
            )
            button_data = [self.CREATE_COMMITMENT]
        else:
            headline = _("Verify and sign")
            text = _(
                "Verify the coordinator reveal against this session, then create the protected transaction signature."
            )
            button_data = [self.APPROVE_SIGNATURE]

        selected = self.run_screen(
            WarningScreen,
            title=_("Anti-exfil Approval"),
            status_headline=headline,
            text=text,
            button_data=button_data,
        )
        if selected == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        try:
            state.create_response(
                seed=seed,
                network=self.settings.get_value(SettingsConstants.SETTING__NETWORK),
            )
        except AntiExfilProtocolError as exc:
            security_codes = {
                "AE_TRANSACTION_MISMATCH",
                "AE_COMMITMENT_MISMATCH",
                "AE_OPENING_MISMATCH",
                "AE_SIGNATURE_SLOT_MISMATCH",
                "AE_SIGNING_MODE_MISMATCH",
            }
            return Destination(
                AntiExfilFailureView,
                view_args={
                    "error_code": exc.code.value,
                    "error_message": exc.message,
                    "security_failure": exc.code.value in security_codes,
                },
                clear_history=True,
            )
        except Exception as exc:
            return Destination(
                AntiExfilFailureView,
                view_args={
                    "error_code": "AE_NATIVE_BACKEND",
                    "error_message": str(exc),
                    "security_failure": False,
                },
                clear_history=True,
            )
        return Destination(AntiExfilResponseReadyView, clear_history=True)


class AntiExfilResponseReadyView(View):
    SHOW_QR = ButtonOption("Show anti-exfil QR")

    def run(self):
        state = self.controller.anti_exfil_state
        if state is None or state.response_package is None:
            return Destination(MainMenuView, clear_history=True)

        if state.request_stage == Stage.HOST_COMMIT:
            headline = _("Nonce commitment ready")
            text = _(
                "Transaction not signed. Scan this response into the same coordinator session."
            )
        else:
            headline = _("Protected signature ready")
            text = _(
                "The coordinator must verify this signature and reconstruct its original PSBT before broadcast."
            )

        self.run_screen(
            WarningScreen,
            title=_("Anti-exfil Response"),
            status_headline=headline,
            text=text,
            button_data=[self.SHOW_QR],
            show_back_button=False,
        )
        return Destination(AntiExfilQRDisplayView, skip_current_view=True)


class AntiExfilQRDisplayView(View):
    def run(self):
        state = self.controller.anti_exfil_state
        if state is None or state.response_package is None:
            return Destination(MainMenuView, clear_history=True)
        encoder = AntiExfilQrEncoder(
            package=state.response_package,
            qr_density=self.settings.get_value(SettingsConstants.SETTING__QR_DENSITY),
        )
        self.run_screen(QRDisplayScreen, qr_encoder=encoder)
        if state.request_stage == Stage.HOST_COMMIT:
            return Destination(AntiExfilRoundOneCompleteView, clear_history=True)
        return Destination(MainMenuView, clear_history=True)


class AntiExfilRoundOneCompleteView(View):
    SCAN_HOST_REVEAL = ButtonOption("Scan host reveal")
    EXIT = ButtonOption("Exit to main menu")

    def run(self):
        state = self.controller.anti_exfil_state
        if (
            state is None
            or state.request_stage != Stage.HOST_COMMIT
            or state.response_package is None
        ):
            return Destination(MainMenuView, clear_history=True)

        selected = self.run_screen(
            WarningScreen,
            title=_("Anti-exfil Signing"),
            status_headline=_("Step 1 of 2 complete"),
            text=_(
                "The transaction is not signed. Scan host reveal message 3 from the same "
                "coordinator session to finish, or exit and scan it later."
            ),
            button_data=[self.SCAN_HOST_REVEAL, self.EXIT],
            show_back_button=False,
        )
        if selected == 0:
            from seedsigner.views.scan_views import ScanAntiExfilHostRevealView

            return Destination(ScanAntiExfilHostRevealView, clear_history=True)
        return Destination(MainMenuView, clear_history=True)
