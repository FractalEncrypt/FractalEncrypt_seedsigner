import logging
import random
import time

from binascii import hexlify
from gettext import gettext as _

from embit.descriptor import Descriptor

from seedsigner.gui.components import FontAwesomeIconConstants, SeedSignerIconConstants
from seedsigner.gui.screens import (RET_CODE__BACK_BUTTON, ButtonListScreen,
    WarningScreen, DireWarningScreen, seed_screens)
from seedsigner.gui.screens.screen import ButtonOption, ButtonOptionWithoutTranslation
from seedsigner.models.encode_qr import CompactSeedQrEncoder, GenericStaticQrEncoder, SeedQrEncoder, SpecterLegacyXPubQrEncoder, StaticXpubQrEncoder, UrXpubQrEncoder
from seedsigner.models.qr_type import QRType
from seedsigner.models.seed import Seed, Codex32Seed
from seedsigner.models import codex32 as codex32_model
from seedsigner.models.settings import Settings, SettingsConstants
from seedsigner.models.settings_definition import SettingsDefinition
from seedsigner.models.threads import BaseThread, ThreadsafeCounter
from seedsigner.views.view import NotYetImplementedView, OptionDisabledView, View, Destination, BackStackView, MainMenuView

logger = logging.getLogger(__name__)

class SeedsMenuView(View):
    LOAD = ButtonOption("Load a seed")

    def __init__(self):
        super().__init__()
        self.seeds = []
        for seed in self.controller.storage.seeds:
            self.seeds.append({
                "fingerprint": seed.get_fingerprint(self.settings.get_value(SettingsConstants.SETTING__NETWORK))
            })


    def run(self):
        if not self.seeds:
            # Nothing to do here unless we have a seed loaded
            return Destination(LoadSeedView, clear_history=True)

        button_data = []
        for seed in self.seeds:
            button_data.append(ButtonOption(seed["fingerprint"], SeedSignerIconConstants.FINGERPRINT))
        button_data.append(self.LOAD)

        selected_menu_num = self.run_screen(
            ButtonListScreen,
            title=_("In-Memory Seeds"),
            is_button_text_centered=False,
            button_data=button_data
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)
        elif len(self.seeds) > 0 and selected_menu_num < len(self.seeds):
            selected_seed = self.controller.storage.seeds[selected_menu_num]
            return Destination(SeedOptionsView, view_args={"seed": selected_seed})

        elif button_data[selected_menu_num] == self.LOAD:
            return Destination(LoadSeedView)



class SeedSelectSeedView(View):
    """
    Reusable seed selection UI. Prompts the user to select amongst the already-loaded
    seeds OR to load a seed.

    * `flow`: indicates which user flow is in progress during seed selection (e.g.
                verify single sig addr or sign message).
    """
    SCAN_SEED = ButtonOption("Scan a seed", SeedSignerIconConstants.QRCODE)
    TYPE_12WORD = ButtonOption("Enter 12-word seed", FontAwesomeIconConstants.KEYBOARD)
    TYPE_24WORD = ButtonOption("Enter 24-word seed", FontAwesomeIconConstants.KEYBOARD)
    TYPE_ELECTRUM = ButtonOption("Enter Electrum seed", FontAwesomeIconConstants.KEYBOARD)


    def __init__(self, flow: str):
        super().__init__()
        self.flow = flow


    def run(self):
        from seedsigner.controller import Controller
        seeds = self.controller.storage.seeds

        if self.flow == Controller.FLOW__VERIFY_SINGLESIG_ADDR:
            title = _("Verify Address")
            if not seeds:
                text = _("Load the seed to verify")
            else: 
                text = _("Select seed to verify")

        elif self.flow == Controller.FLOW__SIGN_MESSAGE:
            title = _("Sign Message")
            if not seeds:
                text = _("Load the seed to sign with")
            else:
                text = _("Select seed to sign with")

        else:
            raise Exception(f"Unsupported `flow` specified: {self.flow}")

        button_data = []
        for seed in seeds:
            button_str = seed.get_fingerprint(self.settings.get_value(SettingsConstants.SETTING__NETWORK))
            button_data.append(ButtonOption(button_str, SeedSignerIconConstants.FINGERPRINT, icon_color="blue"))
        
        button_data.append(self.SCAN_SEED)
        button_data.append(self.TYPE_12WORD)
        button_data.append(self.TYPE_24WORD)

        if self.settings.get_value(SettingsConstants.SETTING__ELECTRUM_SEEDS) == SettingsConstants.OPTION__ENABLED:
            button_data.append(self.TYPE_ELECTRUM)

        selected_menu_num = self.run_screen(
            seed_screens.SeedSelectSeedScreen,
            title=title,
            text=text,
            is_button_text_centered=False,
            button_data=button_data,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)
        
        if len(seeds) > 0 and selected_menu_num < len(seeds):
            # User selected one of the n seeds
            seed = seeds[selected_menu_num]
            if self.flow == Controller.FLOW__VERIFY_SINGLESIG_ADDR:
                return Destination(SeedAddressVerificationView, view_args={"seed": seed})

            elif self.flow == Controller.FLOW__SIGN_MESSAGE:
                self.controller.sign_message_data["seed"] = seed
                return Destination(SeedSignMessageConfirmMessageView)

        self.controller.resume_main_flow = self.flow

        if button_data[selected_menu_num] == self.SCAN_SEED:
            from seedsigner.views.scan_views import ScanView
            return Destination(ScanView)

        elif button_data[selected_menu_num] in [self.TYPE_12WORD, self.TYPE_24WORD]:
            from seedsigner.views.seed_views import SeedMnemonicEntryView
            if button_data[selected_menu_num] == self.TYPE_12WORD:
                self.controller.storage.init_pending_mnemonic(num_words=12)
            else:
                self.controller.storage.init_pending_mnemonic(num_words=24)
            return Destination(SeedMnemonicEntryView)

        elif button_data[selected_menu_num] == self.TYPE_ELECTRUM:
            return Destination(SeedElectrumMnemonicStartView)



"""****************************************************************************
    Loading seeds, passphrases, etc
****************************************************************************"""
class LoadSeedView(View):
    SEED_QR = ButtonOption("Scan a SeedQR", SeedSignerIconConstants.QRCODE)
    TYPE_12WORD = ButtonOption("Enter 12-word seed", FontAwesomeIconConstants.KEYBOARD)
    TYPE_24WORD = ButtonOption("Enter 24-word seed", FontAwesomeIconConstants.KEYBOARD)
    TYPE_CODEX32 = ButtonOption("Enter codex32 Seed", FontAwesomeIconConstants.KEYBOARD)
    SCAN_CODEX32 = ButtonOption("Scan codex32 Share", SeedSignerIconConstants.QRCODE)
    TYPE_ELECTRUM = ButtonOption("Enter Electrum seed", FontAwesomeIconConstants.KEYBOARD)
    CREATE = ButtonOption("Create a seed", SeedSignerIconConstants.PLUS)

    def run(self):
        button_data = [
            self.SEED_QR,
            self.TYPE_12WORD,
            self.TYPE_24WORD,
            self.TYPE_CODEX32,
            self.SCAN_CODEX32,
        ]

        if self.settings.get_value(SettingsConstants.SETTING__ELECTRUM_SEEDS) == SettingsConstants.OPTION__ENABLED:
            button_data.append(self.TYPE_ELECTRUM)
        
        button_data.append(self.CREATE)

        selected_menu_num = self.run_screen(
            ButtonListScreen,
            title=_("Load a Seed"),
            is_button_text_centered=False,
            button_data=button_data
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)
        
        if button_data[selected_menu_num] == self.SEED_QR:
            from .scan_views import ScanSeedQRView
            return Destination(ScanSeedQRView)
        
        elif button_data[selected_menu_num] == self.TYPE_12WORD:
            self.controller.storage.init_pending_mnemonic(num_words=12)
            return Destination(SeedMnemonicEntryView)

        elif button_data[selected_menu_num] == self.TYPE_24WORD:
            self.controller.storage.init_pending_mnemonic(num_words=24)
            return Destination(SeedMnemonicEntryView)

        elif button_data[selected_menu_num] == self.TYPE_CODEX32:
            return Destination(Codex32EntryView)

        elif button_data[selected_menu_num] == self.SCAN_CODEX32:
            from .scan_views import ScanCodex32ShareView
            return Destination(ScanCodex32ShareView)

        elif button_data[selected_menu_num] == self.TYPE_ELECTRUM:
            return Destination(SeedElectrumMnemonicStartView)

        elif button_data[selected_menu_num] == self.CREATE:
            from .tools_views import ToolsMenuView
            return Destination(ToolsMenuView)



class SeedMnemonicEntryView(View):
    def __init__(self, cur_word_index: int = 0, is_calc_final_word: bool=False):
        super().__init__()
        self.cur_word_index = cur_word_index
        self.cur_word = self.controller.storage.get_pending_mnemonic_word(cur_word_index)
        self.is_calc_final_word = is_calc_final_word


    def run(self):
        ret = self.run_screen(
            seed_screens.SeedMnemonicEntryScreen,
            # TRANSLATOR_NOTE: Inserts the word number (e.g. "Seed Word #6")
            title=_("Seed Word #{}").format(self.cur_word_index + 1),  # Human-readable 1-indexing!
            initial_letters=list(self.cur_word) if self.cur_word else ["a"],
            wordlist=Seed.get_wordlist(wordlist_language_code=self.settings.get_value(SettingsConstants.SETTING__WORDLIST_LANGUAGE)),
        )

        if ret == RET_CODE__BACK_BUTTON:
            # This handles two possible scenarios:
            # 1. Backing out of the first word cancels the mnemonic entry process;
            #    return to whichever `View` routed us here initially.
            # 2. Backing out of the current word returns to the previous word.
            if self.cur_word_index == 0:
                self.controller.storage.discard_pending_mnemonic()
            return Destination(BackStackView)
        
        # ret will be our new mnemonic word
        self.controller.storage.update_pending_mnemonic(ret, self.cur_word_index)

        if self.is_calc_final_word and self.cur_word_index == self.controller.storage.pending_mnemonic_length - 2:
            # Time to calculate the last word. User must decide how they want to specify
            # the last bits of entropy for the final word.
            from seedsigner.views.tools_views import ToolsCalcFinalWordFinalizePromptView
            return Destination(ToolsCalcFinalWordFinalizePromptView)

        if self.is_calc_final_word and self.cur_word_index == self.controller.storage.pending_mnemonic_length - 1:
            # Time to calculate the last word. User must either select a final word to
            # contribute entropy to the checksum word OR we assume 0 ("abandon").
            from seedsigner.views.tools_views import ToolsCalcFinalWordShowFinalWordView
            return Destination(ToolsCalcFinalWordShowFinalWordView)

        if self.cur_word_index < self.controller.storage.pending_mnemonic_length - 1:
            return Destination(
                SeedMnemonicEntryView,
                view_args={
                    "cur_word_index": self.cur_word_index + 1,
                    "is_calc_final_word": self.is_calc_final_word
                }
            )
        else:
            # Attempt to finalize the mnemonic
            from seedsigner.models.seed import InvalidSeedException
            try:
                self.controller.storage.convert_pending_mnemonic_to_pending_seed()
            except InvalidSeedException:
                return Destination(SeedMnemonicInvalidView)

            return Destination(SeedFinalizeView)


class Codex32EntryView(View):
    def __init__(
        self,
        share_num: int = 1,
        prefill: str = "MS1",
        start_page: int | None = None,
        share_data: str | None = None,
        share_collection: codex32_model.Codex32ShareCollection | None = None,
        replace_existing: bool = False,
        auto_submit_share_data: bool = False,
        entry_method: str = "manual",
    ):
        super().__init__()
        self.share_num = share_num
        self.prefill = prefill
        self.start_page = start_page
        self.share_data = share_data
        self.share_collection = share_collection
        self.replace_existing = replace_existing
        self.auto_submit_share_data = auto_submit_share_data
        self.entry_method = entry_method


    @staticmethod
    def _destination_from_share_collection(
        view: View,
        share_collection: codex32_model.Codex32ShareCollection,
        share_num: int,
        entry_method: str = "manual",
    ) -> Destination:
        secret = share_collection.recovered_secret_share()
        if secret is not None:
            share_map, source_map = share_collection.export_shares()
            share_display = codex32_model.normalize_codex32_display(secret.s)
            seed = Codex32Seed(
                secret.data,
                codex32_master_share=share_display,
                codex32_export_shares=share_map,
                codex32_share_sources=source_map,
            )
            view.controller.storage.set_pending_seed(seed)
            return Destination(Codex32MasterShareSuccessView)

        return Destination(
            Codex32ShareSuccessView,
            view_args={
                "entered_shares": len(share_collection.shares),
                "total_shares": share_collection.threshold,
                "share_num": share_num,
                "prefill": share_collection.prefix(),
                "share_collection": share_collection,
                "entry_method": entry_method,
            },
        )

    def run(self):
        if self.auto_submit_share_data and self.share_data is not None:
            ret = self.share_data
        else:
            ret = self.run_screen(
                seed_screens.Codex32EntryScreen,
                share_num=self.share_num,
                prefill=self.prefill,
                start_page=self.start_page,
                share_data=self.share_data,
                share_collection=self.share_collection,
            )

            if ret == RET_CODE__BACK_BUTTON:
                return Destination(BackStackView)
        try:
            codex = codex32_model.parse_codex32_share(ret)
        except codex32_model.Codex32InputError as exc:
            return Destination(
                Codex32ShareInvalidView,
                view_args={
                    "share_num": self.share_num,
                    "prefill": self.prefill,
                    "share_data": ret,
                    "error_type": exc.error_type,
                    "error_detail": str(exc),
                    "share_collection": self.share_collection,
                    "entry_method": self.entry_method,
                },
            )

        if codex.share_idx.lower() == "s" and self.share_collection is None:
            try:
                codex = codex32_model.validate_codex32_s_share(ret)
            except codex32_model.Codex32InputError as exc:
                return Destination(
                    Codex32ShareInvalidView,
                    view_args={
                        "share_num": self.share_num,
                        "prefill": self.prefill,
                        "share_data": ret,
                        "error_type": exc.error_type,
                        "error_detail": str(exc),
                        "share_collection": self.share_collection,
                        "entry_method": self.entry_method,
                    },
                )

            share_display = codex32_model.normalize_codex32_display(ret)
            seed = Codex32Seed(
                codex.data,
                codex32_master_share=share_display,
                codex32_export_shares={"s": share_display},
                codex32_share_sources={"s": "entered"},
            )
            self.controller.storage.set_pending_seed(seed)
            return Destination(Codex32MasterShareSuccessView)

        try:
            if self.share_collection is None:
                self.share_collection = codex32_model.Codex32ShareCollection.from_first_share(codex)
            else:
                self.share_collection.add_share(codex, replace_existing=self.replace_existing)
        except codex32_model.Codex32InputError as exc:
            if "Conflicting share index entered" in str(exc) and self.share_collection is not None:
                return Destination(
                    Codex32ShareConflictConfirmView,
                    view_args={
                        "share_num": self.share_num,
                        "prefill": self.share_collection.prefix(),
                        "share_data": ret,
                        "share_collection": self.share_collection,
                        "entry_method": self.entry_method,
                    },
                )

            prefill = self.prefill
            if self.share_collection is not None:
                prefill = self.share_collection.prefix()
            return Destination(
                Codex32ShareInvalidView,
                view_args={
                    "share_num": self.share_num,
                    "prefill": prefill,
                    "share_data": ret,
                    "error_type": exc.error_type,
                    "error_detail": str(exc),
                    "share_collection": self.share_collection,
                    "entry_method": self.entry_method,
                },
            )

        return self._destination_from_share_collection(
            view=self,
            share_collection=self.share_collection,
            share_num=self.share_num,
            entry_method=self.entry_method,
        )


class Codex32ShareConflictConfirmView(View):
    REPLACE = ButtonOption("Replace Existing Share")
    KEEP_EXISTING = ButtonOption("Keep Existing Share")

    def __init__(
        self,
        share_num: int,
        prefill: str,
        share_data: str,
        share_collection: codex32_model.Codex32ShareCollection,
        entry_method: str = "manual",
    ):
        super().__init__()
        self.share_num = share_num
        self.prefill = prefill
        self.share_data = share_data
        self.share_collection = share_collection
        self.entry_method = entry_method

    def run(self):
        button_data = [self.REPLACE, self.KEEP_EXISTING]
        selected_menu_num = self.run_screen(
            WarningScreen,
            title=_("Duplicate share index"),
            status_headline=None,
            text=_("This share index is already entered. Replace the existing share with this one?"),
            show_back_button=False,
            button_data=button_data,
        )

        if button_data[selected_menu_num] == self.KEEP_EXISTING:
            return Destination(
                Codex32EntryView,
                view_args={
                    "share_num": self.share_num,
                    "prefill": self.prefill,
                    "start_page": 0,
                    "share_collection": self.share_collection,
                    "entry_method": self.entry_method,
                },
            )

        try:
            codex = codex32_model.parse_codex32_share(self.share_data)
            self.share_collection.add_share(codex, replace_existing=True)
        except codex32_model.Codex32InputError as exc:
            return Destination(
                Codex32ShareInvalidView,
                view_args={
                    "share_num": self.share_num,
                    "prefill": self.prefill,
                    "share_data": self.share_data,
                    "error_type": exc.error_type,
                    "error_detail": str(exc),
                    "share_collection": self.share_collection,
                },
            )

        return Codex32EntryView._destination_from_share_collection(
            view=self,
            share_collection=self.share_collection,
            share_num=self.share_num,
            entry_method=self.entry_method,
        )


class Codex32ShareInvalidView(View):
    EDIT = ButtonOption("Review & Edit")
    DISCARD_INVALID = ButtonOption("Discard Invalid Share")
    DISCARD_ALL = ButtonOption("Discard All Shares", button_label_color="red")

    def __init__(
        self,
        share_num: int = 1,
        prefill: str = "MS1",
        share_data: str | None = None,
        error_type: str = codex32_model.ERROR_CHECKSUM,
        error_detail: str | None = None,
        share_collection: codex32_model.Codex32ShareCollection | None = None,
        entry_method: str = "manual",
    ):
        super().__init__()
        self.share_num = share_num
        self.prefill = prefill
        self.share_data = share_data
        self.error_type = error_type
        self.error_detail = error_detail
        self.share_collection = share_collection
        self.entry_method = entry_method


    def _get_error_text(self) -> str:
        if (
            self.share_collection
            and self.error_detail
            and "Share header mismatch" in self.error_detail
        ):
            return _("Share does not match the current share set (threshold/identifier mismatch).")
        if self.error_type == codex32_model.ERROR_HEADER:
            return _("Invalid header; check MS1, threshold, identifier, and share index.")
        if self.error_type == codex32_model.ERROR_DATA:
            return _("Invalid data payload; check that all boxes are filled correctly.")
        if self.error_type == codex32_model.ERROR_LENGTH:
            return _("Invalid length; codex32 S shares must be 48 characters.")
        if self.error_type == codex32_model.ERROR_CHECKSUM:
            return _("Checksum failure; not a valid codex32 share.")
        if self.error_detail:
            return self.error_detail
        return _("Invalid codex32 share.")

    def run(self):
        button_data = [self.EDIT, self.DISCARD_INVALID, self.DISCARD_ALL]
        selected_menu_num = self.run_screen(
            DireWarningScreen,
            title=_("Invalid codex32 share"),
            status_icon_name=SeedSignerIconConstants.ERROR,
            status_headline=None,
            text=self._get_error_text(),
            show_back_button=False,
            button_data=button_data,
        )

        if button_data[selected_menu_num] == self.EDIT:
            return Destination(
                Codex32EntryView,
                view_args={
                    "share_num": self.share_num,
                    "prefill": self.prefill,
                    "share_data": self.share_data,
                    "share_collection": self.share_collection,
                    "entry_method": self.entry_method,
                },
            )

        elif button_data[selected_menu_num] == self.DISCARD_INVALID:
            return Destination(
                Codex32ShareEntryMethodView,
                view_args={
                    "share_num": self.share_num,
                    "prefill": self.prefill,
                    "share_collection": self.share_collection,
                    "entry_method": self.entry_method,
                },
            )

        elif button_data[selected_menu_num] == self.DISCARD_ALL:
            return Destination(
                Codex32DiscardAllSharesConfirmView,
                view_args={"share_collection": self.share_collection},
            )


class Codex32DiscardAllSharesConfirmView(View):
    CONTINUE = ButtonOption("Continue", button_label_color="red")
    CANCEL = ButtonOption("Cancel")

    def __init__(self, share_collection: codex32_model.Codex32ShareCollection | None = None):
        super().__init__()
        self.share_collection = share_collection

    def run(self):
        button_data = [self.CONTINUE, self.CANCEL]
        selected_menu_num = self.run_screen(
            WarningScreen,
            title=_("Discard all shares?"),
            status_headline=None,
            text=_("Are you sure you want to discard your valid shares too?"),
            show_back_button=False,
            button_data=button_data,
        )

        if button_data[selected_menu_num] == self.CONTINUE:
            if self.share_collection is not None:
                self.share_collection.wipe()
                self.share_collection = None
            return Destination(MainMenuView, clear_history=True)

        return Destination(BackStackView)


class Codex32ShareEntryMethodView(View):
    ENTER = ButtonOption("Enter Next Share")
    SCAN = ButtonOption("Scan Next Share", SeedSignerIconConstants.QRCODE)

    def __init__(
        self,
        share_num: int,
        prefill: str,
        share_collection: codex32_model.Codex32ShareCollection | None = None,
        entry_method: str = "manual",
    ):
        super().__init__()
        self.share_num = share_num
        self.prefill = prefill
        self.share_collection = share_collection
        self.entry_method = entry_method

    def run(self):
        button_data = [self.ENTER, self.SCAN]
        selected_button = 1 if self.entry_method == "scan" else 0
        selected_menu_num = self.run_screen(
            ButtonListScreen,
            title=_("Next share"),
            button_data=button_data,
            selected_button=selected_button,
            is_bottom_list=True,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        if button_data[selected_menu_num] == self.ENTER:
            return Destination(
                Codex32EntryView,
                view_args={
                    "share_num": self.share_num,
                    "prefill": self.prefill,
                    "share_collection": self.share_collection,
                    "entry_method": "manual",
                },
            )

        from .scan_views import ScanCodex32ShareView
        return Destination(
            ScanCodex32ShareView,
            view_args={
                "share_num": self.share_num,
                "share_collection": self.share_collection,
            },
        )


class Codex32ShareSuccessView(View):
    NEXT = ButtonOption("Enter Next Share")
    SCAN = ButtonOption("Scan Next Share", SeedSignerIconConstants.QRCODE)
    DISCARD = ButtonOption("Discard", button_label_color="red")

    def __init__(
        self,
        entered_shares: int = 1,
        total_shares: int = 2,
        share_num: int = 1,
        prefill: str = "MS1",
        share_collection: codex32_model.Codex32ShareCollection | None = None,
        entry_method: str = "manual",
    ):
        super().__init__()
        self.entered_shares = entered_shares
        self.total_shares = total_shares
        self.share_num = share_num
        self.prefill = prefill
        self.share_collection = share_collection
        self.entry_method = entry_method

    def run(self):
        button_data = [self.NEXT, self.SCAN, self.DISCARD]
        selected_button = 1 if self.entry_method == "scan" else 0
        selected_menu_num = self.run_screen(
            seed_screens.Codex32ShareSuccessScreen,
            entered_shares=self.entered_shares,
            total_shares=self.total_shares,
            button_data=button_data,
            selected_button=selected_button,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(
                Codex32DiscardAllSharesConfirmView,
                view_args={"share_collection": self.share_collection},
            )

        if button_data[selected_menu_num] == self.NEXT:
            return Destination(
                Codex32EntryView,
                view_args={
                    "share_num": self.share_num + 1,
                    "prefill": self.prefill,
                    "share_collection": self.share_collection,
                    "entry_method": "manual",
                },
            )

        elif button_data[selected_menu_num] == self.SCAN:
            from .scan_views import ScanCodex32ShareView
            return Destination(
                ScanCodex32ShareView,
                view_args={
                    "share_num": self.share_num + 1,
                    "share_collection": self.share_collection,
                },
            )

        elif button_data[selected_menu_num] == self.DISCARD:
            return Destination(
                Codex32DiscardAllSharesConfirmView,
                view_args={"share_collection": self.share_collection},
            )


class Codex32MasterShareSuccessView(View):
    DISPLAY = ButtonOption("Show codex32 Master Seed")
    LOAD = ButtonOption("Load Seed")

    def __init__(self, share_data: str | None = None):
        super().__init__()
        self.share_data = codex32_model.normalize_codex32_display(share_data) if share_data else None


    def _resolve_share_data(self) -> str | None:
        if self.share_data:
            return self.share_data

        pending_seed = self.controller.storage.get_pending_seed()
        if isinstance(pending_seed, Codex32Seed) and pending_seed.codex32_master_share:
            return codex32_model.normalize_codex32_display(pending_seed.codex32_master_share)

        return None

    def run(self):
        button_data = [self.DISPLAY, self.LOAD]
        selected_menu_num = self.run_screen(
            seed_screens.Codex32MasterShareSuccessScreen,
            button_data=button_data,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(SeedDiscardView)

        if button_data[selected_menu_num] == self.DISPLAY:
            share_data = self._resolve_share_data()
            self.share_data = None
            if share_data is None:
                return Destination(Codex32BackupUnavailableView)
            return Destination(
                Codex32MasterSecretWarningView,
                view_args={"share_data": share_data},
            )

        elif button_data[selected_menu_num] == self.LOAD:
            self.share_data = None
            self.controller.codex32_temp_share = None
            return Destination(SeedFinalizeView)


class Codex32MasterSecretWarningView(View):
    def __init__(self, share_data: str | None = None, seed: Seed | None = None):
        super().__init__()
        self.share_data = codex32_model.normalize_codex32_display(share_data) if share_data else None
        self.seed = seed


    def _resolve_share_data(self) -> str | None:
        if self.share_data:
            return self.share_data

        if self.controller.codex32_temp_share:
            return self.controller.codex32_temp_share

        if self.seed is None:
            pending_seed = self.controller.storage.get_pending_seed()
            if isinstance(pending_seed, Codex32Seed) and pending_seed.codex32_master_share:
                return codex32_model.normalize_codex32_display(pending_seed.codex32_master_share)
            return None

        if isinstance(self.seed, Codex32Seed) and self.seed.codex32_master_share:
            return codex32_model.normalize_codex32_display(self.seed.codex32_master_share)
        return None

    def run(self):
        share_data = self._resolve_share_data()
        if share_data is None:
            return Destination(Codex32BackupUnavailableView)

        self.controller.codex32_temp_share = share_data
        self.share_data = None

        destination = Destination(
            Codex32MasterSecretDisplayView,
            view_args={"page_index": 0, "seed": self.seed},
            skip_current_view=True,
        )

        selected_menu_num = self.run_screen(
            DireWarningScreen,
            status_headline=_("This will display your master seed!"),
            text=_("Never photograph or scan it into a device that connects to the internet."),
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            self.controller.codex32_temp_share = None
            return Destination(BackStackView)

        return destination


class Codex32MasterSecretDisplayView(View):
    CONTINUE = ButtonOption("Continue to Boxes 25-48")
    FINALIZE = ButtonOption("Finalize Seed")
    CONFIRM = ButtonOption("Confirm Backup")

    def __init__(self, share_data: str | None = None, page_index: int = 0, seed: Seed | None = None):
        super().__init__()
        self.share_data = codex32_model.normalize_codex32_display(share_data) if share_data else None
        self.page_index = page_index
        self.seed = seed

    def run(self):
        share_data = self.share_data if self.share_data is not None else self.controller.codex32_temp_share
        if share_data is None:
            return Destination(Codex32BackupUnavailableView)

        if self.page_index == 0:
            button_data = [self.CONTINUE]
            boxes_label = _("Boxes 1-24")
        else:
            button_data = [self.FINALIZE if self.seed is None else self.CONFIRM]
            boxes_label = _("Boxes 25-48")

        selected_menu_num = self.run_screen(
            seed_screens.Codex32MasterSecretDisplayScreen,
            share_data=share_data,
            start_index=self.page_index * 24,
            chunk_size=24,
            boxes_label=boxes_label,
            button_data=button_data,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            if self.page_index == 0:
                self.controller.codex32_temp_share = None
            return Destination(BackStackView)

        if button_data[selected_menu_num] == self.CONTINUE:
            return Destination(
                Codex32MasterSecretDisplayView,
                view_args={"page_index": 1, "seed": self.seed},
            )

        if self.seed is None:
            self.controller.codex32_temp_share = None
            return Destination(SeedFinalizeView)

        self.controller.codex32_temp_share = None
        return Destination(
            Codex32BackupConfirmPromptView,
            view_args={"seed": self.seed, "expected_share": share_data},
        )


class Codex32BackupConfirmPromptView(View):
    CONFIRM = ButtonOption("Confirm codex32 Backup")
    DONE = ButtonOption("Done")

    def __init__(self, seed: Seed, expected_share: str):
        super().__init__()
        self.seed = seed
        self.expected_share = codex32_model.normalize_codex32_display(expected_share)

    def run(self):
        button_data = [self.CONFIRM, self.DONE]
        selected_menu_num = self.run_screen(
            seed_screens.SeedTranscribeSeedQRConfirmQRPromptScreen,
            title=_("Confirm codex32 backup?"),
            prompt_text=_(
                "Optionally re-enter your codex32 backup to confirm that it reads back correctly."
            ),
            button_data=button_data,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        if button_data[selected_menu_num] == self.CONFIRM:
            return Destination(
                Codex32BackupConfirmEntryView,
                view_args={"seed": self.seed, "expected_share": self.expected_share},
            )

        return Destination(SeedOptionsView, view_args={"seed": self.seed}, clear_history=True)


class Codex32BackupConfirmEntryView(View):
    def __init__(
        self,
        seed: Seed,
        expected_share: str,
        share_data: str | None = None,
        start_page: int | None = None,
    ):
        super().__init__()
        self.seed = seed
        self.expected_share = codex32_model.normalize_codex32_display(expected_share)
        self.share_data = share_data
        self.start_page = start_page

    def run(self):
        ret = self.run_screen(
            seed_screens.Codex32EntryScreen,
            share_num=1,
            prefill="MS1",
            start_page=self.start_page,
            share_data=self.share_data,
        )

        if ret == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        try:
            codex32_model.parse_codex32_share(ret)
            share_display = codex32_model.normalize_codex32_display(ret)
        except codex32_model.Codex32InputError:
            share_display = None

        if share_display != self.expected_share:
            return Destination(
                Codex32BackupConfirmInvalidView,
                view_args={
                    "seed": self.seed,
                    "expected_share": self.expected_share,
                    "share_data": ret,
                },
            )

        return Destination(
            Codex32BackupConfirmSuccessView,
            view_args={"seed": self.seed},
        )


class Codex32BackupConfirmInvalidView(View):
    REVIEW = ButtonOption("Review & Edit")

    def __init__(self, seed: Seed, expected_share: str, share_data: str | None = None):
        super().__init__()
        self.seed = seed
        self.expected_share = codex32_model.normalize_codex32_display(expected_share)
        self.share_data = codex32_model.normalize_codex32_display(share_data) if share_data else None

    def run(self):
        self.run_screen(
            DireWarningScreen,
            title=_("Confirm codex32 backup"),
            status_headline=_("Error!"),
            text=_("Your transcribed codex32 backup could not be validated."),
            show_back_button=False,
            button_data=[self.REVIEW],
        )

        return Destination(
            Codex32BackupConfirmEntryView,
            view_args={
                "seed": self.seed,
                "expected_share": self.expected_share,
                "share_data": self.share_data,
            },
            skip_current_view=True,
        )


class Codex32BackupConfirmSuccessView(View):
    def __init__(self, seed: Seed):
        super().__init__()
        self.seed = seed

    def run(self):
        from seedsigner.gui.screens.screen import LargeIconStatusScreen

        self.run_screen(
            LargeIconStatusScreen,
            title=_("Confirm codex32 backup"),
            status_headline=_("Success!"),
            text=_("Your transcribed codex32 backup matched the original master seed."),
            show_back_button=False,
            button_data=[ButtonOption("OK")],
        )

        return Destination(SeedOptionsView, view_args={"seed": self.seed})


class Codex32BackupUnavailableView(View):
    def run(self):
        self.run_screen(
            DireWarningScreen,
            title=_("Backup unavailable"),
            status_icon_name=SeedSignerIconConstants.ERROR,
            status_headline=_("Codex32 secret unavailable"),
            text=_(
                "This codex32 seed is missing, invalid, or inconsistent backup metadata. "
                "Re-import the codex32 secret to restore backup metadata before backing it up."
            ),
            button_data=[ButtonOption("Back")],
            show_back_button=False,
        )

        return Destination(BackStackView)


class Codex32BackupMetadataWarningView(View):
    CONTINUE = ButtonOption("Continue")
    MODE_DISPLAY = "display"
    MODE_EXPORT = "export"

    def __init__(self, seed: Seed, share_data: str, next_mode: str):
        super().__init__()
        self.seed = seed
        self.share_data = codex32_model.normalize_codex32_display(share_data)
        self.next_mode = next_mode

    def run(self):
        self.run_screen(
            WarningScreen,
            title=_("Backup metadata warning"),
            status_headline=None,
            text=_(
                "Some split-share backup metadata was invalid or inconsistent and was omitted. "
                "Continuing with secret seed S only."
            ),
            show_back_button=False,
            button_data=[self.CONTINUE],
        )

        if self.next_mode == self.MODE_DISPLAY:
            return Destination(
                Codex32MasterSecretWarningView,
                view_args={"share_data": self.share_data, "seed": self.seed},
            )

        return Destination(
            SeedTranscribeSeedQRWarningView,
            view_args={
                "seed": self.seed,
                "seedqr_format": QRType.SEED__CODEX32,
                "num_modules": codex32_model.CODEX32_QR_MODULE_TARGET,
                "qr_data": self.share_data,
            },
        )



class SeedMnemonicInvalidView(View):
    EDIT = ButtonOption("Review & edit")
    DISCARD = ButtonOption("Discard", button_label_color="red")

    def __init__(self):
        super().__init__()
        self.mnemonic: list[str] = self.controller.storage.pending_mnemonic


    def run(self):
        button_data = [self.EDIT, self.DISCARD]
        selected_menu_num = self.run_screen(
            DireWarningScreen,
            title=_("Invalid Mnemonic!"),
            status_icon_name=SeedSignerIconConstants.ERROR,
            status_headline=None,
            text=_("Checksum failure; not a valid seed phrase."),
            show_back_button=False,
            button_data=button_data,
        )

        if button_data[selected_menu_num] == self.EDIT:
            return Destination(SeedMnemonicEntryView, view_args={"cur_word_index": 0})

        elif button_data[selected_menu_num] == self.DISCARD:
            self.controller.storage.discard_pending_mnemonic()
            return Destination(MainMenuView)



class SeedFinalizeView(View):
    FINALIZE = ButtonOption("Done")
    PASSPHRASE = ButtonOption("BIP-39 Passphrase")

    def __init__(self):
        super().__init__()
        self.seed = self.controller.storage.get_pending_seed()

        if self.seed is None:
            self.fingerprint = ""
            return

        if not self.seed.has_passphrase:
            # Expected normal user flow. A freshly-loaded seed has no passphrase yet, so
            # we can just get the fingerprint directly.
            self.fingerprint = self.seed.get_fingerprint(network=self.settings.get_value(SettingsConstants.SETTING__NETWORK))

        else:
            # This view should display the "naked" seed's fingerprint. Normally the
            # just-loaded seed would be naked, but this is special handling for the
            # screenshot generator which creates a pending seed w/a passphrase already
            # set.
            passphrase = self.seed.passphrase
            self.seed.set_passphrase("")
            self.fingerprint = self.seed.get_fingerprint(network=self.settings.get_value(SettingsConstants.SETTING__NETWORK))
            self.seed.set_passphrase(passphrase)


    def run(self):
        if self.seed is None:
            return Destination(MainMenuView)

        button_data = [self.FINALIZE]
        self.PASSPHRASE.button_label = self.seed.passphrase_label
        if self.seed.passphrase_supported and self.settings.get_value(SettingsConstants.SETTING__PASSPHRASE) != SettingsConstants.OPTION__DISABLED:
            button_data.append(self.PASSPHRASE)

        selected_menu_num = self.run_screen(
            seed_screens.SeedFinalizeScreen,
            fingerprint=self.fingerprint,
            button_data=button_data,
        )

        if button_data[selected_menu_num] == self.FINALIZE:
            seed = self.controller.storage.finalize_pending_seed()
            return Destination(SeedOptionsView, view_args={"seed": seed}, clear_history=True)

        elif button_data[selected_menu_num] == self.PASSPHRASE:
            return Destination(SeedAddPassphraseView)



class SeedAddPassphraseView(View):
    """
    initial_keyboard: used by the screenshot generator to render each different keyboard layout.
    """
    def __init__(self, initial_keyboard: str = seed_screens.SeedAddPassphraseScreen.KEYBOARD__LOWERCASE_BUTTON_TEXT):
        super().__init__()
        self.initial_keyboard = initial_keyboard
        self.seed = self.controller.storage.get_pending_seed()


    def run(self):
        passphrase_title=self.seed.passphrase_label
        ret_dict = self.run_screen(
            seed_screens.SeedAddPassphraseScreen,
            passphrase=self.seed.passphrase,
            title=passphrase_title,
            initial_keyboard=self.initial_keyboard,
        )

        # The new passphrase will be the return value; it might be empty.
        self.seed.set_passphrase(ret_dict["passphrase"])

        if "is_back_button" in ret_dict or len(self.seed.passphrase) == 0:
            return Destination(SeedAddPassphraseExitDialogView)
                    
        else:
            return Destination(SeedReviewPassphraseView)



class SeedAddPassphraseExitDialogView(View):
    EDIT = ButtonOption("Edit passphrase")
    DISCARD = ButtonOption("Discard passphrase", button_label_color="red")
    SKIP = ButtonOption("Skip passphrase")  # NOT red since we're not throwing anything away

    def __init__(self):
        super().__init__()
        self.seed = self.controller.storage.get_pending_seed()


    def run(self):
        if self.seed.passphrase:
            title = _("Discard passphrase?")
            message = _("Your current passphrase entry will be erased.")
            button_data = [self.EDIT, self.DISCARD]
        else:
            title = _("Skip passphrase?")
            message = _("You have not entered a passphrase yet.")
            button_data = [self.EDIT, self.SKIP]
        
        selected_menu_num = self.run_screen(
            WarningScreen,
            title=title,
            status_headline=None,
            text=message,
            show_back_button=False,
            button_data=button_data,
        )

        if button_data[selected_menu_num] == self.EDIT:
            return Destination(SeedAddPassphraseView)

        elif button_data[selected_menu_num] in [self.DISCARD, self.SKIP]:
            self.seed.set_passphrase("")
            return Destination(SeedFinalizeView)
        


class SeedReviewPassphraseView(View):
    """
        Display the completed passphrase back to the user.
    """
    EDIT = ButtonOption("Edit passphrase")
    DONE = ButtonOption("Done")

    def __init__(self):
        super().__init__()
        self.seed = self.controller.storage.get_pending_seed()


    def run(self):
        # Get the before/after fingerprints
        network = self.settings.get_value(SettingsConstants.SETTING__NETWORK)
        passphrase = self.seed.passphrase
        fingerprint_with = self.seed.get_fingerprint(network=network)
        self.seed.set_passphrase("")
        fingerprint_without = self.seed.get_fingerprint(network=network)
        self.seed.set_passphrase(passphrase)
        
        button_data = [self.EDIT, self.DONE]

        # Because we have an explicit "Edit" button, we disable "BACK" to keep the
        # routing options sane.
        selected_menu_num = self.run_screen(
            seed_screens.SeedReviewPassphraseScreen,
            fingerprint_without=fingerprint_without,
            fingerprint_with=fingerprint_with,
            passphrase=self.seed.passphrase,
            button_data=button_data,
            show_back_button=False,
        )

        if button_data[selected_menu_num] == self.EDIT:
            return Destination(SeedAddPassphraseView)
        
        elif button_data[selected_menu_num] == self.DONE:
            seed = self.controller.storage.finalize_pending_seed()
            return Destination(SeedOptionsView, view_args={"seed": seed}, clear_history=True)
            

            
class SeedDiscardView(View):
    KEEP = ButtonOption("Keep seed")
    DISCARD = ButtonOption("Discard", button_label_color="red")

    def __init__(self, seed: Seed = None):
        super().__init__()
        if seed is None:
            self.is_pending_seed = True
            self.seed = self.controller.storage.get_pending_seed()
        else:
            self.is_pending_seed = False
            self.seed = seed


    def run(self):
        button_data = [self.KEEP, self.DISCARD]

        fingerprint = self.seed.get_fingerprint(self.settings.get_value(SettingsConstants.SETTING__NETWORK))
        # TRANSLATOR_NOTE: Inserts the seed fingerprint
        text = _("Wipe seed {} from the device?").format(fingerprint)
        selected_menu_num = self.run_screen(
            WarningScreen,
            title=_("Discard Seed?"),
            status_headline=None,
            text=text,
            show_back_button=False,
            button_data=button_data,
        )

        if button_data[selected_menu_num] == self.KEEP:
            # Use skip_current_view=True to prevent BACK from landing on this warning screen
            if self.is_pending_seed:
                return Destination(SeedFinalizeView, skip_current_view=True)
            else:
                return Destination(SeedOptionsView, view_args={"seed": self.seed}, skip_current_view=True)

        elif button_data[selected_menu_num] == self.DISCARD:
            if self.is_pending_seed:
                self.controller.storage.clear_pending_seed()
            else:
                self.controller.discard_seed(self.seed)
            return Destination(MainMenuView, clear_history=True)



class SeedElectrumMnemonicStartView(View):
    """
    Currently just a warning display before entering an Electrum seed.
    
    Could be expanded with a follow-up View to specify Electrum seed type.
    """
    def run(self):
        self.run_screen(
                WarningScreen,
                title=_("Electrum Warning"),
                status_headline=None,
                text=_("Some features are disabled for Electrum seeds."),
                show_back_button=False,
        )

        self.controller.storage.init_pending_mnemonic(num_words=12, is_electrum=True)

        return Destination(SeedMnemonicEntryView)



"""****************************************************************************
    Views for actions on individual seeds:
****************************************************************************"""
class SeedOptionsView(View):
    SCAN_PSBT = ButtonOption("Scan transaction", SeedSignerIconConstants.QRCODE)
    EXPORT_XPUB = ButtonOption("Export xpub")
    EXPLORER = ButtonOption("Address explorer")
    SIGN_MESSAGE = ButtonOption("Sign message")
    BACKUP = ButtonOption("Backup seed", right_icon_name=SeedSignerIconConstants.CHEVRON_RIGHT)
    BIP85_CHILD_SEED = ButtonOption("BIP-85 child seed")
    DISCARD = ButtonOption("Discard seed", button_label_color="red")


    def __init__(self, seed: Seed):
        super().__init__()
        self.seed = seed


    def run(self):
        from seedsigner.controller import Controller
        from seedsigner.views.psbt_views import PSBTOverviewView

        if self.controller.unverified_address:
            if self.controller.resume_main_flow == Controller.FLOW__VERIFY_SINGLESIG_ADDR:
                # Jump straight back into the single sig addr verification flow
                self.controller.resume_main_flow = None
                return Destination(SeedAddressVerificationView, view_args=dict(seed=self.seed), skip_current_view=True)

        if self.controller.resume_main_flow == Controller.FLOW__ADDRESS_EXPLORER:
            # Jump straight back into the address explorer script type selection flow
            # But don't cancel the `resume_main_flow` as we'll still need that after
            # derivation path is specified.
            return Destination(SeedExportXpubScriptTypeView, view_args=dict(seed=self.seed, sig_type=SettingsConstants.SINGLE_SIG), skip_current_view=True)

        elif self.controller.resume_main_flow == Controller.FLOW__SIGN_MESSAGE:
            self.controller.sign_message_data["seed"] = self.seed
            return Destination(SeedSignMessageConfirmMessageView, skip_current_view=True)

        if self.controller.psbt:
            from seedsigner.models.psbt_parser import PSBTParser
            if PSBTParser.has_matching_input_fingerprint(self.controller.psbt, self.seed, network=self.settings.get_value(SettingsConstants.SETTING__NETWORK)):
                if self.controller.resume_main_flow and self.controller.resume_main_flow == Controller.FLOW__PSBT:
                    # Re-route us directly back to the start of the PSBT flow
                    self.controller.resume_main_flow = None
                    self.controller.psbt_seed = self.seed
                    return Destination(PSBTOverviewView, skip_current_view=True)

        button_data = []

        button_data.append(self.SCAN_PSBT)
        
        button_data.append(self.EXPORT_XPUB)

        button_data.append(self.EXPLORER)
        button_data.append(self.BACKUP)

        if self.settings.get_value(SettingsConstants.SETTING__MESSAGE_SIGNING) == SettingsConstants.OPTION__ENABLED:
            button_data.append(self.SIGN_MESSAGE)
        
        if self.settings.get_value(SettingsConstants.SETTING__BIP85_CHILD_SEEDS) == SettingsConstants.OPTION__ENABLED and self.seed.bip85_supported:
            button_data.append(self.BIP85_CHILD_SEED)

        button_data.append(self.DISCARD)
        
        selected_menu_num = self.run_screen(
            seed_screens.SeedOptionsScreen,
            button_data=button_data,
            fingerprint=self.seed.get_fingerprint(self.settings.get_value(SettingsConstants.SETTING__NETWORK)),
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            # Force BACK to always return to the Main Menu
            return Destination(MainMenuView)

        if button_data[selected_menu_num] == self.SCAN_PSBT:
            from seedsigner.views.scan_views import ScanPSBTView
            self.controller.psbt_seed = self.seed
            return Destination(ScanPSBTView)

        elif button_data[selected_menu_num] == self.EXPORT_XPUB:
            return Destination(SeedExportXpubSigTypeView, view_args=dict(seed=self.seed))

        elif button_data[selected_menu_num] == self.EXPLORER:
            self.controller.resume_main_flow = Controller.FLOW__ADDRESS_EXPLORER
            return Destination(SeedExportXpubScriptTypeView, view_args=dict(seed=self.seed, sig_type=SettingsConstants.SINGLE_SIG))

        elif button_data[selected_menu_num] == self.SIGN_MESSAGE:
            from seedsigner.views.scan_views import ScanView
            self.controller.sign_message_data = dict(seed=self.seed)
            self.controller.resume_main_flow = Controller.FLOW__SIGN_MESSAGE
            return Destination(ScanView)

        elif button_data[selected_menu_num] == self.BACKUP:
            return Destination(SeedBackupView, view_args=dict(seed=self.seed))

        elif button_data[selected_menu_num] == self.BIP85_CHILD_SEED:
            return Destination(SeedBIP85SelectNumWordsView, view_args={"seed": self.seed})

        elif button_data[selected_menu_num] == self.DISCARD:
            return Destination(SeedDiscardView, view_args=dict(seed=self.seed))



class SeedBackupView(View):
    VIEW_CODEX32_SECRET = ButtonOption("View codex32 Secret")
    VIEW_CODEX32_SECRET_UNAVAILABLE = ButtonOption("View codex32 Secret (Unavailable)")
    EXPORT_CODEX32QR = ButtonOption("Export as codex32 QR")
    VIEW_WORDS = ButtonOption("View seed words")
    EXPORT_SEEDQR = ButtonOption("Export as SeedQR")

    def __init__(self, seed: Seed):
        super().__init__()
        self.seed = seed


    @staticmethod
    def _normalize_source_value(source_value: str | None) -> str:
        return source_value if source_value in ["entered", "derived"] else "entered"


    def _codex32_metadata_warning_destination(self, share_data: str, next_mode: str) -> Destination:
        return Destination(
            Codex32BackupMetadataWarningView,
            view_args={
                "seed": self.seed,
                "share_data": share_data,
                "next_mode": next_mode,
            },
        )


    def _get_codex32_export_data(self) -> tuple[dict[str, str], dict[str, str], bool]:
        raw_share_map = self.seed.codex32_export_shares or {}
        raw_source_map = self.seed.codex32_share_sources or {}
        share_map: dict[str, str] = {}
        source_map: dict[str, str] = {}
        dropped_non_s_entries = False

        raw_s_candidates: list[tuple[str, codex32_model.Codex32String, str]] = []
        invalid_s_context = False

        for share_idx_raw, share_value in raw_share_map.items():
            share_idx = str(share_idx_raw).lower()
            if share_idx != "s":
                continue

            if not isinstance(share_value, str) or not share_value:
                invalid_s_context = True
                continue

            share_display = codex32_model.normalize_codex32_display(share_value)
            try:
                parsed = codex32_model.validate_codex32_s_share(share_display)
            except codex32_model.Codex32InputError:
                invalid_s_context = True
                continue

            raw_s_candidates.append((share_display, parsed, str(share_idx_raw)))

        if invalid_s_context:
            return {}, {}, False

        canonical_s_display: str | None = None
        canonical_s: codex32_model.Codex32String | None = None
        canonical_s_source = "entered"

        if raw_s_candidates:
            canonical_s_display = raw_s_candidates[0][0]
            canonical_s = raw_s_candidates[0][1]
            canonical_s_key = raw_s_candidates[0][2]

            for candidate_display, _, _ in raw_s_candidates[1:]:
                if candidate_display != canonical_s_display:
                    return {}, {}, False

            source_value = raw_source_map.get(canonical_s_key) or raw_source_map.get("s")
            canonical_s_source = self._normalize_source_value(source_value)

            if self.seed.codex32_master_share is not None:
                master_share = codex32_model.normalize_codex32_display(self.seed.codex32_master_share)
                try:
                    codex32_model.validate_codex32_s_share(master_share)
                except codex32_model.Codex32InputError:
                    master_share = None
                if master_share is not None and master_share != canonical_s_display:
                    return {}, {}, False

        elif self.seed.codex32_master_share is not None:
            master_share = codex32_model.normalize_codex32_display(self.seed.codex32_master_share)
            try:
                canonical_s = codex32_model.validate_codex32_s_share(master_share)
                canonical_s_display = master_share
            except codex32_model.Codex32InputError:
                return {}, {}, False
        else:
            return {}, {}, False

        if canonical_s_display is None or canonical_s is None:
            return {}, {}, False

        if canonical_s.data != self.seed.seed_bytes:
            return {}, {}, False

        share_map["s"] = canonical_s_display
        source_map["s"] = canonical_s_source

        for share_idx_raw, share_value in raw_share_map.items():
            share_idx = str(share_idx_raw).lower()
            if share_idx == "s":
                continue

            if not isinstance(share_value, str) or not share_value:
                dropped_non_s_entries = True
                continue

            share_display = codex32_model.normalize_codex32_display(share_value)
            try:
                parsed = codex32_model.parse_codex32_share(share_display)
            except codex32_model.Codex32InputError:
                dropped_non_s_entries = True
                continue

            if parsed.share_idx.lower() != share_idx:
                dropped_non_s_entries = True
                continue

            if parsed.k != canonical_s.k or parsed.ident != canonical_s.ident:
                dropped_non_s_entries = True
                continue

            share_map[share_idx] = share_display
            source_value = raw_source_map.get(share_idx_raw) or raw_source_map.get(share_idx)
            source_map[share_idx] = self._normalize_source_value(source_value)

        split_indices = [idx for idx in share_map.keys() if idx != "s"]
        if len(split_indices) > codex32_model.CODEX32_MAX_SPLIT_SHARES:
            return {}, {}, False

        validated_share_map = {"s": share_map["s"]} if dropped_non_s_entries else share_map
        try:
            codex32_model.validate_codex32_seed_metadata(
                self.seed.seed_bytes,
                master_share=canonical_s_display,
                export_shares=validated_share_map,
            )
        except codex32_model.Codex32InputError:
            return {}, {}, False

        if dropped_non_s_entries:
            return {"s": share_map["s"]}, {"s": source_map["s"]}, True

        return share_map, source_map, False
    

    def run(self):
        if isinstance(self.seed, Codex32Seed):
            button_data = [self.VIEW_CODEX32_SECRET]
            if self.seed.codex32_master_share is None:
                button_data = [self.VIEW_CODEX32_SECRET_UNAVAILABLE]
            else:
                button_data.append(self.EXPORT_CODEX32QR)
        else:
            button_data = [self.VIEW_WORDS]
            if self.seed.seedqr_supported:
                button_data.append(self.EXPORT_SEEDQR)

        selected_menu_num = self.run_screen(
            ButtonListScreen,
            title=_("Backup Seed"),
            button_data=button_data,
            is_bottom_list=True,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        elif button_data[selected_menu_num] == self.VIEW_CODEX32_SECRET:
            share_map, source_map, show_metadata_warning = self._get_codex32_export_data()
            if not share_map:
                return Destination(Codex32BackupUnavailableView)

            ordered_indices = codex32_model.Codex32ShareCollection.ordered_share_indices(share_map)
            if len(ordered_indices) > 1:
                return Destination(
                    Codex32BackupShareSelectView,
                    view_args={
                        "seed": self.seed,
                        "share_map": share_map,
                        "source_map": source_map,
                        "selection_mode": "display",
                    },
                )

            selected_share = share_map.get("s")
            if selected_share is None and ordered_indices:
                selected_share = share_map[ordered_indices[0]]
            if selected_share is None:
                return Destination(Codex32BackupUnavailableView)

            if show_metadata_warning:
                return self._codex32_metadata_warning_destination(
                    share_data=selected_share,
                    next_mode=Codex32BackupMetadataWarningView.MODE_DISPLAY,
                )

            return Destination(
                Codex32MasterSecretWarningView,
                view_args={"share_data": selected_share, "seed": self.seed},
            )

        elif button_data[selected_menu_num] == self.VIEW_CODEX32_SECRET_UNAVAILABLE:
            return Destination(Codex32BackupUnavailableView)

        elif button_data[selected_menu_num] == self.VIEW_WORDS:
            return Destination(SeedWordsWarningView, view_args={"seed": self.seed})

        elif button_data[selected_menu_num] == self.EXPORT_SEEDQR:
            return Destination(SeedTranscribeSeedQRFormatView, view_args={"seed": self.seed})

        elif button_data[selected_menu_num] == self.EXPORT_CODEX32QR:
            share_map, source_map, show_metadata_warning = self._get_codex32_export_data()
            if not share_map:
                return Destination(Codex32BackupUnavailableView)

            ordered_indices = codex32_model.Codex32ShareCollection.ordered_share_indices(share_map)

            if len(ordered_indices) > 1:
                return Destination(
                    Codex32BackupShareSelectView,
                    view_args={
                        "seed": self.seed,
                        "share_map": share_map,
                        "source_map": source_map,
                    },
                )

            qr_share = share_map.get("s")
            if qr_share is None and ordered_indices:
                qr_share = share_map[ordered_indices[0]]
            if qr_share is None:
                return Destination(Codex32BackupUnavailableView)

            if show_metadata_warning:
                return self._codex32_metadata_warning_destination(
                    share_data=qr_share,
                    next_mode=Codex32BackupMetadataWarningView.MODE_EXPORT,
                )

            return Destination(
                SeedTranscribeSeedQRWarningView,
                view_args={
                    "seed": self.seed,
                    "seedqr_format": QRType.SEED__CODEX32,
                    "num_modules": codex32_model.CODEX32_QR_MODULE_TARGET,
                    "qr_data": qr_share,
                },
            )


class Codex32BackupShareSelectView(View):
    def __init__(
        self,
        seed: Seed,
        share_map: dict[str, str],
        source_map: dict[str, str],
        selection_mode: str = "qr",
    ):
        super().__init__()
        self.seed = seed
        self.share_map = share_map
        self.source_map = source_map
        self.selection_mode = selection_mode


    @staticmethod
    def _label_for_index(share_idx: str, source: str | None) -> str:
        if share_idx == "s":
            if source == "derived":
                return _("Secret seed S (derived)")
            return _("Secret seed S")
        return _("Share {}").format(share_idx.upper())


    def run(self):
        ordered_indices = codex32_model.Codex32ShareCollection.ordered_share_indices(self.share_map)
        if not ordered_indices:
            return Destination(Codex32BackupUnavailableView)

        button_data = []
        for share_idx in ordered_indices:
            button_data.append(
                ButtonOption(
                    self._label_for_index(share_idx, self.source_map.get(share_idx)),
                    return_data=share_idx,
                )
            )

        selected_menu_num = self.run_screen(
            ButtonListScreen,
            title=_("Export codex32 string"),
            button_data=button_data,
            is_bottom_list=True,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        selected_share_idx = button_data[selected_menu_num].return_data
        if selected_share_idx not in self.share_map:
            return Destination(Codex32BackupUnavailableView)

        if self.selection_mode == "display":
            return Destination(
                Codex32MasterSecretWarningView,
                view_args={
                    "seed": self.seed,
                    "share_data": self.share_map[selected_share_idx],
                },
            )

        return Destination(
            SeedTranscribeSeedQRWarningView,
            view_args={
                "seed": self.seed,
                "seedqr_format": QRType.SEED__CODEX32,
                "num_modules": codex32_model.CODEX32_QR_MODULE_TARGET,
                "qr_data": self.share_map[selected_share_idx],
            },
        )



"""****************************************************************************
    Export Xpub flow
****************************************************************************"""
class SeedExportXpubSigTypeView(View):
    SINGLE_SIG = ButtonOption("Single Sig", return_data=SettingsConstants.SINGLE_SIG)
    MULTISIG = ButtonOption("Multisig", return_data=SettingsConstants.MULTISIG)

    def __init__(self, seed: Seed):
        super().__init__()
        self.seed = seed


    def run(self):
        if len(self.settings.get_value(SettingsConstants.SETTING__SIG_TYPES)) == 1:
            # Nothing to select; skip this screen
            return Destination(SeedExportXpubScriptTypeView, view_args={"seed": self.seed, "sig_type": self.settings.get_value(SettingsConstants.SETTING__SIG_TYPES)[0]}, skip_current_view=True)

        button_data = [self.SINGLE_SIG, self.MULTISIG]

        selected_menu_num = self.run_screen(
            ButtonListScreen,
            title=_("Export Xpub"),
            button_data=button_data
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        return Destination(SeedExportXpubScriptTypeView, view_args={"seed": self.seed, "sig_type": button_data[selected_menu_num].return_data})



class SeedExportXpubScriptTypeView(View):
    def __init__(self, seed: Seed, sig_type: str):
        super().__init__()
        self.seed = seed
        self.sig_type = sig_type


    def run(self):
        from seedsigner.controller import Controller
        from .tools_views import ToolsAddressExplorerAddressTypeView
        args = {"seed": self.seed, "sig_type": self.sig_type}

        script_types = self.settings.get_value(SettingsConstants.SETTING__SCRIPT_TYPES)

        if self.seed.script_override:
            # This seed only allows one script type
            # TODO: Does it matter if the Settings don't have the override script type
            # enabled?
            script_types = [self.seed.script_override]

        if len(script_types) == 1:
            # Nothing to select; skip this screen
            args["script_type"] = script_types[0]

            if self.controller.resume_main_flow == Controller.FLOW__ADDRESS_EXPLORER:
                del args["sig_type"]
                return Destination(ToolsAddressExplorerAddressTypeView, view_args=args, skip_current_view=True)
            else:
                return Destination(SeedExportXpubQRFormatView, view_args=args, skip_current_view=True)
        
        title = _("Export Xpub")
        if self.controller.resume_main_flow == Controller.FLOW__ADDRESS_EXPLORER:
            title = _("Address Explorer")

        button_data = []
        for script_type, display_name in SettingsConstants.ALL_SCRIPT_TYPES:
            if script_type in self.settings.get_value(SettingsConstants.SETTING__SCRIPT_TYPES):
                button_data.append(ButtonOption(display_name, return_data=script_type))

        selected_menu_num = self.run_screen(
            ButtonListScreen,
            title=title,
            is_button_text_centered=False,
            button_data=button_data,
            is_bottom_list=True,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            # If previous view is SeedOptionsView then that should be where resume_main_flow started (otherwise it would have been skipped).
            if len(self.controller.back_stack) >= 2 and self.controller.back_stack[-2].View_cls == SeedOptionsView:
                self.controller.resume_main_flow = None
            return Destination(BackStackView)

        else:
            args["script_type"] = button_data[selected_menu_num].return_data

            if args["script_type"] == SettingsConstants.CUSTOM_DERIVATION:
                return Destination(SeedExportXpubCustomDerivationView, view_args=args)

            if self.controller.resume_main_flow == Controller.FLOW__ADDRESS_EXPLORER:
                del args["sig_type"]
                return Destination(ToolsAddressExplorerAddressTypeView, view_args=args)
            else:
                return Destination(SeedExportXpubQRFormatView, view_args=args)



class SeedExportXpubCustomDerivationView(View):
    def __init__(self, seed: Seed, sig_type: str, script_type: str):
        super().__init__()
        self.seed = seed
        self.sig_type = sig_type
        self.script_type = script_type
        self.custom_derivation_path = "m/"


    def run(self):
        from seedsigner.controller import Controller
        ret = self.run_screen(
            seed_screens.SeedExportXpubCustomDerivationScreen,
            initial_value=self.custom_derivation_path,
        )

        if ret == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)
        
        # ret will be the custom derivation path
        custom_derivation = ret

        if self.controller.resume_main_flow == Controller.FLOW__ADDRESS_EXPLORER:
            from .tools_views import ToolsAddressExplorerAddressTypeView
            return Destination(ToolsAddressExplorerAddressTypeView, view_args=dict(seed=self.seed, script_type=self.script_type, custom_derivation=custom_derivation))

        return Destination(
            SeedExportXpubQRFormatView,
            view_args={
                "seed": self.seed,
                "sig_type": self.sig_type,
                "script_type": self.script_type,
                "custom_derivation": custom_derivation,
            }
        )



class SeedExportXpubQRFormatView(View):
    def __init__(self, seed: Seed, sig_type: str, script_type: str, custom_derivation: str = None):
        super().__init__()
        self.seed = seed
        self.sig_type = sig_type
        self.script_type = script_type
        self.custom_derivation = custom_derivation


    def run(self):
        args = {
            "seed": self.seed,
            "sig_type": self.sig_type,
            "script_type": self.script_type,
            "custom_derivation": self.custom_derivation,
        }
        if len(self.settings.get_value(SettingsConstants.SETTING__XPUB_QR_FORMAT)) == 1:
            # Nothing to select; skip this screen
            args["xpub_qr_format"] = self.settings.get_value(SettingsConstants.SETTING__XPUB_QR_FORMAT)[0]
            return Destination(SeedExportXpubWarningView, view_args=args, skip_current_view=True)

        button_data = []
        for display_name, setting_option in zip(self.settings.get_multiselect_value_display_names(SettingsConstants.SETTING__XPUB_QR_FORMAT), self.settings.get_value(SettingsConstants.SETTING__XPUB_QR_FORMAT)):
            button_data.append(ButtonOption(display_name, return_data=setting_option))

        selected_menu_num = self.run_screen(
            ButtonListScreen,
            title=_("Xpub QR Format"),
            is_button_text_centered=False,
            button_data=button_data,
            is_bottom_list=True,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        args["xpub_qr_format"] = button_data[selected_menu_num].return_data

        return Destination(SeedExportXpubWarningView, view_args=args)



class SeedExportXpubWarningView(View):
    def __init__(self, seed: Seed, sig_type: str, script_type: str, xpub_qr_format: str, custom_derivation: str):
        super().__init__()
        self.seed = seed
        self.sig_type = sig_type
        self.script_type = script_type
        self.xpub_qr_format = xpub_qr_format
        self.custom_derivation = custom_derivation


    def run(self):
        destination = Destination(
            SeedExportXpubDetailsView,
            view_args={
                "seed": self.seed,
                "sig_type": self.sig_type,
                "script_type": self.script_type,
                "xpub_qr_format": self.xpub_qr_format,
                "custom_derivation": self.custom_derivation,
            },
            skip_current_view=True,  # Prevent going BACK to WarningViews
        )

        if self.settings.get_value(SettingsConstants.SETTING__PRIVACY_WARNINGS) == SettingsConstants.OPTION__DISABLED:
            # Skip the WarningView entirely
            return destination

        selected_menu_num = self.run_screen(
            WarningScreen,
            status_headline=_("Privacy Leak!"),
            text=_("Xpub can be used to view all future transactions."),
        )

        if selected_menu_num == 0:
            # User clicked "I Understand"
            return destination

        elif selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)



class SeedExportXpubDetailsView(View):
    """
        Collects the user input from all the previous screens leading up to this and
        finally calculates the xpub and displays the summary view to the user.
    """
    def __init__(self, seed: Seed, sig_type: str, script_type: str, xpub_qr_format: str, custom_derivation: str):
        super().__init__()
        self.sig_type = sig_type
        self.script_type = script_type
        self.xpub_qr_format = xpub_qr_format
        self.custom_derivation = custom_derivation
        
        self.seed = seed


    def run(self):
        seed_derivation_override = self.seed.derivation_override(self.sig_type)
        if self.script_type == SettingsConstants.CUSTOM_DERIVATION:
            derivation_path = self.custom_derivation
        elif seed_derivation_override:
            derivation_path = seed_derivation_override
        else:
            from seedsigner.helpers import embit_utils
            derivation_path = embit_utils.get_standard_derivation_path(
                network=self.settings.get_value(SettingsConstants.SETTING__NETWORK),
                wallet_type=self.sig_type,
                script_type=self.script_type
            )

        if self.settings.get_value(SettingsConstants.SETTING__XPUB_DETAILS) == SettingsConstants.OPTION__DISABLED:
            # We're just skipping right past this screen
            selected_menu_num = 0

        else:
            # The derivation calc takes a few moments. Run the loading screen while we wait.
            from seedsigner.gui.screens.screen import LoadingScreenThread
            self.loading_screen = LoadingScreenThread(text=_("Generating xpub..."))
            self.loading_screen.start()

            try:
                from embit.bip32 import HDKey
                from embit.networks import NETWORKS
                embit_network = NETWORKS[SettingsConstants.map_network_to_embit(self.settings.get_value(SettingsConstants.SETTING__NETWORK))]
                version = self.seed.detect_version(
                    derivation_path,
                    self.settings.get_value(SettingsConstants.SETTING__NETWORK),
                    self.sig_type
                )
                root = HDKey.from_seed(
                    self.seed.seed_bytes,
                    version=embit_network["xprv"]
                )
                fingerprint = hexlify(root.child(0).fingerprint).decode('utf-8')
                xprv = root.derive(derivation_path)
                xpub = xprv.to_public()
                xpub_base58 = xpub.to_string(version=version)

            finally:
                self.loading_screen.stop()

            selected_menu_num = self.run_screen(
                seed_screens.SeedExportXpubDetailsScreen,
                fingerprint=fingerprint,
                derivation_path=derivation_path,
                xpub=xpub_base58,
            )

        if selected_menu_num == 0:
            return Destination(
                SeedExportXpubQRDisplayView,
                dict(seed=self.seed,
                     xpub_qr_format=self.xpub_qr_format,
                     derivation_path=derivation_path,
                     sig_type=self.sig_type
                )
            )

        elif selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)



class SeedExportXpubQRDisplayView(View):
    def __init__(self, seed: Seed, xpub_qr_format: str, derivation_path: str, sig_type: str = SettingsConstants.SINGLE_SIG):
        super().__init__()
        self.seed = seed

        encoder_args = dict(
            seed=self.seed,
            derivation=derivation_path,
            network=self.settings.get_value(SettingsConstants.SETTING__NETWORK),
            qr_density=self.settings.get_value(SettingsConstants.SETTING__QR_DENSITY),
            sig_type=sig_type
        )

        if xpub_qr_format == SettingsConstants.XPUB_QR_FORMAT__STATIC:
            self.qr_encoder = StaticXpubQrEncoder(**encoder_args)

        elif xpub_qr_format == SettingsConstants.XPUB_QR_FORMAT__SPECTER_LEGACY:
            self.qr_encoder = SpecterLegacyXPubQrEncoder(**encoder_args)

        else:
            # Default: UR crypto-address
            self.qr_encoder = UrXpubQrEncoder(**encoder_args)


    def run(self):
        from seedsigner.gui.screens.screen import QRDisplayScreen
        self.run_screen(
            QRDisplayScreen,
            qr_encoder=self.qr_encoder
        )

        return Destination(MainMenuView)



"""****************************************************************************
    View Seed Words flow
****************************************************************************"""
class SeedWordsWarningView(View):
    def __init__(self, seed: Seed, bip85_data: dict = None):
        super().__init__()
        self.seed = seed
        self.bip85_data = bip85_data


    def run(self):
        destination = Destination(
            SeedWordsView,
            view_args=dict(
                seed=self.seed,
                page_index=0,
                bip85_data=self.bip85_data
            ),
            skip_current_view=True,  # Prevent going BACK to WarningViews
        )
        if self.settings.get_value(SettingsConstants.SETTING__DIRE_WARNINGS) == SettingsConstants.OPTION__DISABLED:
            # Forward straight to showing the words
            return destination

        selected_menu_num = self.run_screen(
            DireWarningScreen,
            text=_("You must keep your seed words private & away from all online devices."),
        )

        if selected_menu_num == 0:
            # User clicked "I Understand"
            return destination

        elif selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)



class SeedWordsView(View):
    NEXT = ButtonOption("Next")
    DONE = ButtonOption("Done")

    def __init__(self, seed: Seed, bip85_data: dict = None, page_index: int = 0):
        super().__init__()
        if seed is None:
            self.is_pending_seed = True
            self.seed = self.controller.storage.get_pending_seed()
        else:
            self.is_pending_seed = False
            self.seed = seed
        self.bip85_data = bip85_data
        self.page_index = page_index


    def run(self):
        # Slice the mnemonic to our current 4-word section
        words_per_page = 4  # TODO: eventually make this configurable for bigger screens?

        if self.bip85_data is not None:
            mnemonic = self.seed.get_bip85_child_mnemonic(self.bip85_data["child_index"], self.bip85_data["num_words"]).split()
            # TRANSLATOR_NOTE: Inserts the child index (e.g. "Child #0")
            title = _("Child #{}").format(self.bip85_data["child_index"])
        else:
            mnemonic = self.seed.mnemonic_display_list
            title = _("Seed Words")
        words = mnemonic[self.page_index*words_per_page:(self.page_index + 1)*words_per_page]

        button_data = []
        num_pages = int(len(mnemonic)/words_per_page)
        if self.page_index < num_pages - 1 or self.is_pending_seed:
            button_data.append(self.NEXT)
        else:
            button_data.append(self.DONE)

        selected_menu_num = self.run_screen(
            seed_screens.SeedWordsScreen,
            title=f"{title}: {self.page_index+1}/{num_pages}",
            words=words,
            page_index=self.page_index,
            num_pages=num_pages,
            button_data=button_data,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        if self.is_pending_seed:
            self.seed = None # Set to None for next View to know it's a pending seed

        if button_data[selected_menu_num] == self.NEXT:
            if self.is_pending_seed and self.page_index == num_pages - 1:
                return Destination(
                    SeedWordsBackupTestPromptView,
                    view_args=dict(seed=self.seed, bip85_data=self.bip85_data),
                )
            else:
                return Destination(
                    SeedWordsView,
                    view_args=dict(seed=self.seed, page_index=self.page_index + 1, bip85_data=self.bip85_data)
                )

        elif button_data[selected_menu_num] == self.DONE:
            # Must clear history to avoid BACK button returning to private info
            return Destination(
                SeedWordsBackupTestPromptView,
                view_args=dict(seed=self.seed, bip85_data=self.bip85_data),
            )



"""****************************************************************************
    BIP-85 - Derive child mnemonic (seed) flow (Application number 39')
****************************************************************************"""
class SeedBIP85SelectNumWordsView(View):
    WORDS_12 = ButtonOption("12 Words")
    WORDS_24 = ButtonOption("24 Words")

    def __init__(self, seed: Seed):
        super().__init__()
        self.seed = seed
        self.num_words = 0


    def run(self):
        button_data = [self.WORDS_12, self.WORDS_24]

        selected_menu_num = self.run_screen(
            ButtonListScreen,
            title=_("BIP-85 Num Words"),
            button_data=button_data
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        if button_data[selected_menu_num] == self.WORDS_12:
            self.num_words = 12
        elif button_data[selected_menu_num] == self.WORDS_24:
            self.num_words = 24

        return Destination(
            SeedBIP85SelectChildIndexView,
            view_args=dict(seed=self.seed, num_words=self.num_words)
        )



class SeedBIP85SelectChildIndexView(View):
    # View to retrieve the derived seed index
    def __init__(self, seed: Seed, num_words: int):
        super().__init__()
        self.seed = seed
        self.num_words = num_words


    def run(self):
        # TODO: Change this later to use the generic Screen input keyboard
        ret = self.run_screen(seed_screens.SeedBIP85SelectChildIndexScreen)

        if ret == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        if not 0 <= int(ret) < 2**31:
            return Destination(
                SeedBIP85InvalidChildIndexView,
                view_args=dict(
                    seed=self.seed,
                    num_words=self.num_words
                ),
                skip_current_view=True
            )

        return Destination(
            SeedWordsWarningView,
            view_args=dict(
                seed=self.seed,
                bip85_data=dict(child_index=int(ret), num_words=self.num_words),
            )
        )



class SeedBIP85InvalidChildIndexView(View):
    def __init__(self, seed: Seed, num_words: int):
        super().__init__()
        self.seed = seed
        self.num_words = num_words


    def run(self):
        self.run_screen(
            DireWarningScreen,
            title=_("BIP-85 Index Error"),
            show_back_button=False,
            status_icon_name=SeedSignerIconConstants.ERROR,
            status_headline=_("Invalid Child Index"),
            text=_("BIP-85 Child Index must be between 0 and 2^31-1."),
            button_data=[ButtonOption("Try again")]
        )

        return Destination(
                SeedBIP85SelectChildIndexView,
                view_args=dict(
                    seed=self.seed,
                    num_words=self.num_words
                ),
                skip_current_view=True
            )



"""****************************************************************************
    Seed Words Backup Test
****************************************************************************"""
class SeedWordsBackupTestPromptView(View):
    VERIFY = ButtonOption("Verify")
    SKIP = ButtonOption("Skip")

    def __init__(self, seed: Seed, bip85_data: dict = None):
        super().__init__()
        self.seed = seed
        self.bip85_data = bip85_data


    def run(self):
        button_data = [self.VERIFY, self.SKIP]
        selected_menu_num = self.run_screen(
            seed_screens.SeedWordsBackupTestPromptScreen,
            button_data=button_data,
        )

        if button_data[selected_menu_num] == self.VERIFY:
            return Destination(
                SeedWordsBackupTestView,
                view_args=dict(seed=self.seed, bip85_data=self.bip85_data),
            )

        elif button_data[selected_menu_num] == self.SKIP:
            if self.seed is None:
                return Destination(SeedFinalizeView)
            else:
                return Destination(SeedOptionsView, view_args=dict(seed=self.seed))



class SeedWordsBackupTestView(View):
    def __init__(self, seed: Seed, bip85_data: dict = None, confirmed_list: list[bool] = None, cur_index: int = None, rand_seed: int = None):
        """
        Note: `rand_seed` is ONLY USED BY THE SCREENSHOT GENERATOR!!! (to ensure
        consistent screenshot results).
        """
        super().__init__()
        if seed is None:
            self.is_pending_seed = True
            self.seed = self.controller.storage.get_pending_seed()
        else:
            self.is_pending_seed = False
            self.seed = seed
        self.bip85_data = bip85_data

        if self.bip85_data is not None:
            self.mnemonic_list = self.seed.get_bip85_child_mnemonic(self.bip85_data["child_index"], self.bip85_data["num_words"]).split()
        else:
            self.mnemonic_list = self.seed.mnemonic_display_list

        self.confirmed_list = confirmed_list
        if not self.confirmed_list:
            self.confirmed_list = []

        self.cur_index = cur_index
        self.rand_seed = rand_seed


    def run(self):
        from embit import bip39

        if self.rand_seed is not None:
            random.seed(self.rand_seed + self.cur_index if self.cur_index is not None else 0)

        if self.cur_index is None:
            self.cur_index = int(random.random() * len(self.mnemonic_list))
            while self.cur_index in self.confirmed_list:
                self.cur_index = int(random.random() * len(self.mnemonic_list))

        real_word = ButtonOption(self.mnemonic_list[self.cur_index])
        fake_word1 = ButtonOption(bip39.WORDLIST[int(random.random() * 2047)])
        fake_word2 = ButtonOption(bip39.WORDLIST[int(random.random() * 2047)])
        fake_word3 = ButtonOption(bip39.WORDLIST[int(random.random() * 2047)])

        button_data = [real_word, fake_word1, fake_word2, fake_word3]
        random.shuffle(button_data)

        # TRANSLATOR_NOTE: Inserts the word number (e.g. "Verify Word #1")
        title = _("Verify Word #{}").format(self.cur_index + 1)
        selected_menu_num = self.run_screen(
            ButtonListScreen,
            title=title,
            show_back_button=False,
            button_data=button_data,
            is_bottom_list=True,
            is_button_text_centered=True,
        )

        if self.is_pending_seed:
            self.seed = None # Set to None for next View to know it's a pending seed

        if button_data[selected_menu_num] == real_word:
            self.confirmed_list.append(self.cur_index)
            if len(self.confirmed_list) == len(self.mnemonic_list):
                # Successfully confirmed the full mnemonic!
                return Destination(
                    SeedWordsBackupTestSuccessView,
                    view_args=dict(seed=self.seed),
                )
            else:
                # Continue testing the remaining words
                return Destination(
                    SeedWordsBackupTestView,
                    view_args=dict(seed=self.seed, confirmed_list=self.confirmed_list, bip85_data=self.bip85_data),
                )

        else:
            # Picked the WRONG WORD!
            return Destination(
                SeedWordsBackupTestMistakeView,
                view_args=dict(
                    seed=self.seed,
                    bip85_data=self.bip85_data,
                    cur_index=self.cur_index,
                    wrong_word=button_data[selected_menu_num].button_label,
                    confirmed_list=self.confirmed_list,
                )
            )



class SeedWordsBackupTestMistakeView(View):
    REVIEW = ButtonOption("Review seed words")
    RETRY = ButtonOption("Try again")

    def __init__(self, seed: Seed, bip85_data: dict = None, cur_index: int = None, wrong_word: str = None, confirmed_list: list[bool] = None):
        super().__init__()
        self.seed = seed
        self.bip85_data = bip85_data
        self.cur_index = cur_index
        self.wrong_word = wrong_word
        self.confirmed_list = confirmed_list


    def run(self):
        button_data = [self.REVIEW, self.RETRY]

        # TRANSLATOR_NOTE: Inserts the word number and the word (e.g. "Word #1 is not "apple"!")
        text = _("Word #{} is not \"{}\"!").format(self.cur_index + 1, self.wrong_word)

        # TRANSLATOR_NOTE: User selected the wrong word during the mnemonic backup test (e.g. incorrectly said the 5th word was "zoo")
        status_headline = _("Wrong Word!")

        selected_menu_num = self.run_screen(
            DireWarningScreen,
            title=_("Verification Error"),
            show_back_button=False,
            status_icon_name=SeedSignerIconConstants.ERROR,
            status_headline=status_headline,
            button_data=button_data,
            text=text,
        )

        if button_data[selected_menu_num] == self.REVIEW:
            return Destination(
                SeedWordsView,
                view_args=dict(seed=self.seed, bip85_data=self.bip85_data),
            )

        elif button_data[selected_menu_num] == self.RETRY:
            return Destination(
                SeedWordsBackupTestView,
                view_args=dict(
                    seed=self.seed,
                    confirmed_list=self.confirmed_list,
                    cur_index=self.cur_index,
                    bip85_data=self.bip85_data,
                )
            )



class SeedWordsBackupTestSuccessView(View):
    def __init__(self, seed: Seed):
        super().__init__()
        self.seed = seed

    def run(self):
        from seedsigner.gui.screens.screen import LargeIconStatusScreen
        self.run_screen(
            LargeIconStatusScreen,
            title=_("Backup Verified"),
            show_back_button=False,
            status_headline=_("Success!"),
            text=_("All mnemonic backup words were successfully verified!"),
            button_data=[ButtonOption("OK")]
        )

        if self.seed is None:
            return Destination(SeedFinalizeView)
        else:
            return Destination(SeedOptionsView, view_args=dict(seed=self.seed), clear_history=True)



"""****************************************************************************
    Export as SeedQR
****************************************************************************"""
class SeedTranscribeSeedQRFormatView(View):
    # SeedQR dims for 12-word seeds
    STANDARD_12 = ButtonOption("Standard: 25x25", return_data=25)
    COMPACT_12 = ButtonOption("Compact: 21x21", return_data=21)

    # SeedQR dims for 24-word seeds
    STANDARD_24 = ButtonOption("Standard: 29x29", return_data=29)
    COMPACT_24 = ButtonOption("Compact: 25x25", return_data=25)

    def __init__(self, seed: Seed):
        super().__init__()
        self.seed = seed


    def run(self):

        if self.settings.get_value(SettingsConstants.SETTING__COMPACT_SEEDQR) != SettingsConstants.OPTION__ENABLED:
            # Only configured for standard SeedQR
            return Destination(
                SeedTranscribeSeedQRWarningView,
                view_args={
                    "seed": self.seed,
                    "seedqr_format": QRType.SEED__SEEDQR,
                    "num_modules": self.STANDARD_12.return_data,
                },
                skip_current_view=True,
            )

        if len(self.seed.mnemonic_list) == 12:
            button_data = [self.STANDARD_12, self.COMPACT_12]
        else:
            button_data = [self.STANDARD_24, self.COMPACT_24]

        selected_menu_num = self.run_screen(
            seed_screens.SeedTranscribeSeedQRFormatScreen,
            title=_("SeedQR Format"),
            button_data=button_data,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)
        
        if button_data[selected_menu_num] in [self.STANDARD_12, self.STANDARD_24]:
            seedqr_format = QRType.SEED__SEEDQR
        else:
            seedqr_format = QRType.SEED__COMPACTSEEDQR

        num_modules = button_data[selected_menu_num].return_data
        
        return Destination(
            SeedTranscribeSeedQRWarningView,
                view_args={
                    "seed": self.seed,
                    "seedqr_format": seedqr_format,
                    "num_modules": num_modules,
                }
            )



class SeedTranscribeSeedQRWarningView(View):
    def __init__(self, seed: Seed, seedqr_format: str = QRType.SEED__SEEDQR, num_modules: int = 29, qr_data: str | None = None):
        super().__init__()
        self.seed = seed
        self.seedqr_format = seedqr_format
        self.num_modules = num_modules
        self.qr_data = qr_data
    

    def run(self):
        is_codex32 = self.seedqr_format == QRType.SEED__CODEX32
        status_headline = (
            _("Codex32 QR is your master seed!")
            if is_codex32
            else _("SeedQR is your private key!")
        )
        destination = Destination(
            SeedTranscribeSeedQRWholeQRView,
            view_args={
                "seed": self.seed,
                "seedqr_format": self.seedqr_format,
                "num_modules": self.num_modules,
                "qr_data": self.qr_data,
            },
            skip_current_view=True,  # Prevent going BACK to WarningViews
        )

        if self.settings.get_value(SettingsConstants.SETTING__DIRE_WARNINGS) == SettingsConstants.OPTION__DISABLED:
            # Forward straight to transcribing the SeedQR
            return destination

        selected_menu_num = self.run_screen(
            DireWarningScreen,
            status_headline=status_headline,
            text=_("Never photograph or scan it into a device that connects to the internet."),
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        else:
            # User clicked "I Understand"
            return destination
    


class SeedTranscribeSeedQRWholeQRView(View):
    def __init__(self, seed: Seed, seedqr_format: str, num_modules: int, qr_data: str | None = None):
        super().__init__()
        self.seed = seed
        self.seedqr_format = seedqr_format
        self.num_modules = num_modules
        self.qr_data = qr_data
    

    def run(self):
        if self.qr_data is not None:
            data = self.qr_data
        else:
            encoder_args = dict(mnemonic=self.seed.mnemonic_list,
                                wordlist_language_code=self.settings.get_value(SettingsConstants.SETTING__WORDLIST_LANGUAGE))
            if self.seedqr_format == QRType.SEED__SEEDQR:
                e = SeedQrEncoder(**encoder_args)
            elif self.seedqr_format == QRType.SEED__COMPACTSEEDQR:
                e = CompactSeedQrEncoder(**encoder_args)
            data = e.next_part()

        title = _("Transcribe SeedQR")
        if self.seedqr_format == QRType.SEED__CODEX32:
            title = _("Transcribe codex32 QR")

        ret = self.run_screen(
            seed_screens.SeedTranscribeSeedQRWholeQRScreen,
            qr_data=data,
            num_modules=self.num_modules,
            title=title,
        )

        if ret == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)
        
        else:
            return Destination(
                SeedTranscribeSeedQRZoomedInView,
                view_args={
                    "seed": self.seed,
                    "seedqr_format": self.seedqr_format,
                    "num_modules": self.num_modules,
                    "qr_data": self.qr_data,
                }
            )



class SeedTranscribeSeedQRZoomedInView(View):
    """
    intial_zone_x, initial_zone_y: Used by the screenshot generator to shift the view
    to a more interesting part of the QR code template.
    """
    def __init__(self, seed: Seed, seedqr_format: str, initial_zone_x: int = 0, initial_zone_y: int = 0, num_modules: int | None = None, qr_data: str | None = None):
        super().__init__()
        self.seed = seed
        self.seedqr_format = seedqr_format
        self.num_modules = num_modules
        self.qr_data = qr_data
        self.initial_zone_x = initial_zone_x
        self.initial_zone_y = initial_zone_y
        self.is_screensaver_allowed = False


    def run(self):
        if self.qr_data is not None:
            data = self.qr_data
            num_modules = self.num_modules or codex32_model.CODEX32_QR_MODULE_TARGET
        else:
            encoder_args = dict(mnemonic=self.seed.mnemonic_list,
                                wordlist_language_code=self.settings.get_value(SettingsConstants.SETTING__WORDLIST_LANGUAGE))
            if self.seedqr_format == QRType.SEED__SEEDQR:
                e = SeedQrEncoder(**encoder_args)
            elif self.seedqr_format == QRType.SEED__COMPACTSEEDQR:
                e = CompactSeedQrEncoder(**encoder_args)

            data = e.next_part()

            if len(self.seed.mnemonic_list) == 24:
                if self.seedqr_format == QRType.SEED__COMPACTSEEDQR:
                    num_modules = 25
                else:
                    num_modules = 29
            else:
                if self.seedqr_format == QRType.SEED__COMPACTSEEDQR:
                    num_modules = 21
                else:
                    num_modules = 25

        self.run_screen(
            seed_screens.SeedTranscribeSeedQRZoomedInScreen,
            qr_data=data,
            num_modules=num_modules,
            initial_zone_x=self.initial_zone_x,
            initial_zone_y=self.initial_zone_y,
        )

        return Destination(
            SeedTranscribeSeedQRConfirmQRPromptView,
            view_args={
                "seed": self.seed,
                "seedqr_format": self.seedqr_format,
                "expected_qr_data": self.qr_data,
            },
        )



class SeedTranscribeSeedQRConfirmQRPromptView(View):
    SCAN = ButtonOption("Confirm SeedQR", SeedSignerIconConstants.QRCODE)
    SCAN_CODEX32QR = ButtonOption("Confirm codex32 QR", SeedSignerIconConstants.QRCODE)
    DONE = ButtonOption("Done")

    def __init__(self, seed: Seed, seedqr_format: str = QRType.SEED__SEEDQR, expected_qr_data: str | None = None):
        super().__init__()
        self.seed = seed
        self.seedqr_format = seedqr_format
        self.expected_qr_data = expected_qr_data
    

    def run(self):
        scan_button = self.SCAN
        title = _("Confirm SeedQR?")
        prompt_text = _("Optionally scan your transcribed SeedQR to confirm that it reads back correctly.")
        if self.seedqr_format == QRType.SEED__CODEX32:
            scan_button = self.SCAN_CODEX32QR
            title = _("Confirm codex32 QR?")
            prompt_text = _("Optionally scan your transcribed codex32 QR to confirm that it reads back correctly.")
        button_data = [scan_button, self.DONE]

        selected_menu_option = self.run_screen(
            seed_screens.SeedTranscribeSeedQRConfirmQRPromptScreen,
            title=title,
            prompt_text=prompt_text,
            button_data=button_data,
        )

        if selected_menu_option == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        elif button_data[selected_menu_option] == scan_button:
            return Destination(
                SeedTranscribeSeedQRConfirmScanView,
                view_args={
                    "seed": self.seed,
                    "seedqr_format": self.seedqr_format,
                    "expected_qr_data": self.expected_qr_data,
                },
            )

        elif button_data[selected_menu_option] == self.DONE:
            return Destination(SeedOptionsView, view_args={"seed": self.seed}, clear_history=True)



class SeedTranscribeSeedQRConfirmScanView(View):
    def __init__(self, seed: Seed, seedqr_format: str = QRType.SEED__SEEDQR, expected_qr_data: str | None = None):
        from seedsigner.models.decode_qr import DecodeQR
        super().__init__()
        self.seed = seed
        self.seedqr_format = seedqr_format
        self.expected_qr_data = expected_qr_data
        wordlist_language_code = self.settings.get_value(SettingsConstants.SETTING__WORDLIST_LANGUAGE)
        self.decoder = DecodeQR(wordlist_language_code=wordlist_language_code)

    def run(self):
        from seedsigner.gui.screens.scan_screens import ScanScreen

        # Run the live preview and QR code capture process
        # TODO: Does this belong in its own BaseThread?
        scanning_done=self.run_screen(
            ScanScreen,
            decoder=self.decoder,
            instructions_text=_("Scan your codex32 QR") if self.seedqr_format == QRType.SEED__CODEX32 else _("Scan your SeedQR")
        )

        # If the scanning was canceled because the back button was pressed, return to BackStackView (SeedTranscribeSeedQRConfirmQRPromptView).
        if scanning_done==False:
           return Destination(BackStackView, skip_current_view=False)

        if self.decoder.is_complete:
            if self.seedqr_format == QRType.SEED__CODEX32:
                if self.decoder.is_codex32:
                    scanned_share = self.decoder.get_codex32_share()
                    expected_share = codex32_model.normalize_codex32_display(self.expected_qr_data)
                    if scanned_share != expected_share:
                        return Destination(
                            SeedTranscribeSeedQRConfirmWrongSeedView,
                            view_args={"seedqr_format": self.seedqr_format},
                            skip_current_view=True,
                        )
                    return Destination(
                        SeedTranscribeSeedQRConfirmSuccessView,
                        view_args={"seed": self.seed, "seedqr_format": self.seedqr_format},
                    )
            elif self.decoder.is_seed:
                seed_mnemonic = self.decoder.get_seed_phrase()
                # Found a valid mnemonic seed! But does it match?
                if seed_mnemonic != self.seed.mnemonic_list:
                    return Destination(
                        SeedTranscribeSeedQRConfirmWrongSeedView,
                        view_args={"seedqr_format": self.seedqr_format},
                        skip_current_view=True,
                    )
                else:
                    return Destination(
                        SeedTranscribeSeedQRConfirmSuccessView,
                        view_args={"seed": self.seed, "seedqr_format": self.seedqr_format},
                    )

        # Will trigger if a different kind of QR code is scanned (non SeedQR)
        return Destination(
            SeedTranscribeSeedQRConfirmInvalidQRView,
            view_args={"seedqr_format": self.seedqr_format},
            skip_current_view=True,
        )



class SeedTranscribeSeedQRConfirmWrongSeedView(View):
    """
    A valid SeedQR was scanned but it did NOT match the one we just transcribed!
    """
    def __init__(self, seedqr_format: str = QRType.SEED__SEEDQR):
        super().__init__()
        self.seedqr_format = seedqr_format


    def run(self):
        is_codex32 = self.seedqr_format == QRType.SEED__CODEX32
        title = _("Confirm codex32 QR") if is_codex32 else _("Confirm SeedQR")
        text = (
            _("Your transcribed codex32 QR does not match the original share.")
            if is_codex32
            else _("Your transcribed SeedQR does not match your original seed!")
        )
        review_label = _("Review codex32 QR") if is_codex32 else _("Review SeedQR")
        self.run_screen(
            DireWarningScreen,
            title=title,
            status_headline=_("Error!"),
            text=text,
            show_back_button=False,
            button_data=[ButtonOption(review_label)],
        )

        # Skip BACK to the zoomed in transcription view
        return Destination(BackStackView, skip_current_view=True)



class SeedTranscribeSeedQRConfirmInvalidQRView(View):
    """
    A QR code was scanned but it was not a SeedQR and certainly not the SeedQR we just
    transcribed!
    """
    def __init__(self, seedqr_format: str = QRType.SEED__SEEDQR):
        super().__init__()
        self.seedqr_format = seedqr_format


    def run(self):
        is_codex32 = self.seedqr_format == QRType.SEED__CODEX32
        title = _("Confirm codex32 QR") if is_codex32 else _("Confirm SeedQR")
        text = (
            _("Your transcribed codex32 QR could not be read!")
            if is_codex32
            else _("Your transcribed SeedQR could not be read!")
        )
        review_label = _("Review codex32 QR") if is_codex32 else _("Review SeedQR")
        # TODO: A better error message would be something like: "The QR code you scanned does not contain a valid SeedQR."
        self.run_screen(
            DireWarningScreen,
            title=title,
            status_headline=_("Error!"),
            text=text,
            show_back_button=False,
            button_data=[ButtonOption(review_label)],
        )

        # Skip BACK to the zoomed in transcription view
        return Destination(BackStackView, skip_current_view=True)



class SeedTranscribeSeedQRConfirmSuccessView(View):
    """
    The SeedQR we just scanned matched the one we just transcribed.
    """
    def __init__(self, seed: Seed, seedqr_format: str = QRType.SEED__SEEDQR):
        super().__init__()
        self.seed = seed
        self.seedqr_format = seedqr_format


    def run(self):
        from seedsigner.gui.screens.screen import LargeIconStatusScreen
        is_codex32 = self.seedqr_format == QRType.SEED__CODEX32
        title = _("Confirm codex32 QR") if is_codex32 else _("Confirm SeedQR")
        text = (
            _("Your transcribed codex32 QR successfully scanned and matched the original share.")
            if is_codex32
            else _("Your transcribed SeedQR successfully scanned and yielded the same seed.")
        )
        self.run_screen(
            LargeIconStatusScreen,
            title=title,
            status_headline=_("Success!"),
            text=text,
            show_back_button=False,
            button_data=[ButtonOption("OK")],
        )

        return Destination(SeedOptionsView, view_args={"seed": self.seed})



"""****************************************************************************
    Address verification
****************************************************************************"""
class AddressVerificationStartView(View):
    def __init__(self, address: str, script_type: str, network: str):
        super().__init__()
        self.controller.unverified_address = dict(
            address=address,
            script_type=script_type,
            network=network
        )


    def run(self):
        from seedsigner.helpers import embit_utils
        from seedsigner.controller import Controller

        if self.controller.unverified_address["script_type"] == SettingsConstants.LEGACY_P2PKH:
            # Legacy P2PKH addresses are always singlesig
            sig_type = SettingsConstants.SINGLE_SIG
            destination = Destination(SeedSelectSeedView, view_args=dict(flow=Controller.FLOW__VERIFY_SINGLESIG_ADDR), skip_current_view=True)

        if self.controller.unverified_address["script_type"] == SettingsConstants.NESTED_SEGWIT:
            # No way to differentiate single sig from multisig
            return Destination(AddressVerificationSigTypeView, skip_current_view=True)

        if self.controller.unverified_address["script_type"] == SettingsConstants.NATIVE_SEGWIT:
            if len(self.controller.unverified_address["address"]) >= 62:
                # Mainnet/testnet are 62, regtest is 64
                sig_type = SettingsConstants.MULTISIG
                if self.controller.multisig_wallet_descriptor:
                    # Can jump straight to the brute-force verification View
                    destination = Destination(SeedAddressVerificationView, skip_current_view=True)
                else:
                    self.controller.resume_main_flow = Controller.FLOW__VERIFY_MULTISIG_ADDR
                    destination = Destination(LoadMultisigWalletDescriptorView, skip_current_view=True)

            else:
                sig_type = SettingsConstants.SINGLE_SIG
                destination = Destination(SeedSelectSeedView, view_args=dict(flow=Controller.FLOW__VERIFY_SINGLESIG_ADDR), skip_current_view=True)

        elif self.controller.unverified_address["script_type"] == SettingsConstants.TAPROOT:
            sig_type = SettingsConstants.SINGLE_SIG
            destination = Destination(SeedSelectSeedView, view_args=dict(flow=Controller.FLOW__VERIFY_SINGLESIG_ADDR), skip_current_view=True)

        derivation_path = embit_utils.get_standard_derivation_path(
            network=self.controller.unverified_address["network"],
            wallet_type=sig_type,
            script_type=self.controller.unverified_address["script_type"]
        )

        self.controller.unverified_address["sig_type"] = sig_type
        self.controller.unverified_address["derivation_path"] = derivation_path

        return destination



class AddressVerificationSigTypeView(View):
    SINGLE_SIG = ButtonOption("Single Sig")
    MULTISIG = ButtonOption("Multisig")

    def run(self):
        from seedsigner.helpers import embit_utils
        from seedsigner.controller import Controller
        button_data = [self.SINGLE_SIG, self.MULTISIG]
        selected_menu_num = self.run_screen(
            seed_screens.AddressVerificationSigTypeScreen,
            title=_("Verify Address"),
            text=_("Sig type can't be auto-detected from this address. Please specify:"),
            button_data=button_data,
            is_bottom_list=True,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            self.controller.unverified_address = None
            return Destination(BackStackView)
        
        elif button_data[selected_menu_num] == self.SINGLE_SIG:
            sig_type = SettingsConstants.SINGLE_SIG
            destination = Destination(SeedSelectSeedView, view_args=dict(flow=Controller.FLOW__VERIFY_SINGLESIG_ADDR))

        elif button_data[selected_menu_num] == self.MULTISIG:
            sig_type = SettingsConstants.MULTISIG
            if self.controller.multisig_wallet_descriptor:
                destination = Destination(SeedAddressVerificationView)
            else:
                self.controller.resume_main_flow = Controller.FLOW__VERIFY_MULTISIG_ADDR
                destination = Destination(LoadMultisigWalletDescriptorView)

        self.controller.unverified_address["sig_type"] = sig_type
        derivation_path = embit_utils.get_standard_derivation_path(
            network=self.controller.unverified_address["network"],
            wallet_type=sig_type,
            script_type=self.controller.unverified_address["script_type"]
        )
        self.controller.unverified_address["derivation_path"] = derivation_path

        return destination



class SeedAddressVerificationView(View):
    """
        Creates a worker thread to brute-force calculate addresses. Writes its
        iteration status to a shared `ThreadsafeCounter`.

        The `ThreadsafeCounter` is sent to the display Screen which is monitored in
        its own `ProgressThread` to show the current iteration onscreen.

        Performs single sig verification on `seed` if specified, otherwise assumes
        multisig.
    """
    # TRANSLATOR_NOTE: Option when scanning for a matching address; skips ten addresses ahead
    SKIP_10 = ButtonOption("Skip 10")
    CANCEL = ButtonOption("Cancel")

    def __init__(self, seed: Seed = None):
        super().__init__()
        self.seed = seed
        self.is_multisig = self.controller.unverified_address["sig_type"] == SettingsConstants.MULTISIG
        self.seed_derivation_override = ""
        if not self.is_multisig:
            if self.seed is None:
                # Shouldn't be able to get here
                raise Exception("Can't validate a single sig addr without specifying a seed")
            self.seed_derivation_override = self.seed.derivation_override(sig_type=SettingsConstants.SINGLE_SIG)
        self.address = self.controller.unverified_address["address"]
        self.derivation_path = self.seed_derivation_override if self.seed_derivation_override else self.controller.unverified_address["derivation_path"]
        self.script_type = self.controller.unverified_address["script_type"]
        self.sig_type = self.controller.unverified_address["sig_type"]
        self.network = self.controller.unverified_address["network"]

        # TODO: This should be in `Seed` or `PSBT` utility class
        embit_network = SettingsConstants.map_network_to_embit(self.network)

        # The ThreadsafeCounter will be shared by the brute-force thread to keep track of
        # its current addr index number and the Screen to display its progress and
        # respond to UI requests to jump the index ahead.
        self.threadsafe_counter = ThreadsafeCounter()

        # Shared coordination var so the display thread can detect success
        self.verified_index = ThreadsafeCounter(initial_value=None)
        self.verified_index_is_change = ThreadsafeCounter(initial_value=None)

        # Create the brute-force calculation thread that will run in the background
        self.addr_verification_thread = self.BruteForceAddressVerificationThread(
            address=self.address,
            seed=None if self.is_multisig else self.seed,
            descriptor=self.controller.multisig_wallet_descriptor,
            script_type=self.script_type,
            embit_network=embit_network,
            derivation_path=self.derivation_path,
            threadsafe_counter=self.threadsafe_counter,
            verified_index=self.verified_index,
            verified_index_is_change=self.verified_index_is_change,
        )


    def run(self):
        # Start brute-force calculations from the zero-th index
        try:
            self.addr_verification_thread.start()

            button_data = [self.SKIP_10, self.CANCEL]

            script_type_settings_entry = SettingsDefinition.get_settings_entry(SettingsConstants.SETTING__SCRIPT_TYPES)
            script_type_display = script_type_settings_entry.get_selection_option_display_name_by_value(self.script_type)

            sig_type_settings_entry = SettingsDefinition.get_settings_entry(SettingsConstants.SETTING__SIG_TYPES)
            sig_type_display = sig_type_settings_entry.get_selection_option_display_name_by_value(self.sig_type)

            network_settings_entry = SettingsDefinition.get_settings_entry(SettingsConstants.SETTING__NETWORK)
            network_display = network_settings_entry.get_selection_option_display_name_by_value(self.network)
            mainnet = network_settings_entry.get_selection_option_display_name_by_value(SettingsConstants.MAINNET)

            # Display the Screen to show the brute-forcing progress.
            # Using a loop here to handle the SKIP_10 button presses to increment the counter
            # and resume displaying the screen. User won't even notice that the Screen is
            # being re-constructed.
            while True:
                selected_menu_num = self.run_screen(
                    seed_screens.SeedAddressVerificationScreen,
                    address=self.address,
                    derivation_path=self.derivation_path,
                    script_type=script_type_display,
                    sig_type=sig_type_display,
                    network=network_display,
                    is_mainnet=network_display == mainnet,
                    threadsafe_counter=self.threadsafe_counter,
                    verified_index=self.verified_index,
                    button_data=button_data,
                )

                if self.verified_index.cur_count is not None:
                    break

                if selected_menu_num == RET_CODE__BACK_BUTTON:
                    break

                if selected_menu_num is None:
                    # Only happens in the test suite; the screen isn't actually executed so
                    # it returns before the brute force thread has completed.
                    time.sleep(0.1)
                    continue

                if button_data[selected_menu_num] == self.SKIP_10:
                    self.threadsafe_counter.increment(10)

                elif button_data[selected_menu_num] == self.CANCEL:
                    break

            if self.verified_index.cur_count is not None:
                # Successfully verified the addr; update the data
                self.controller.unverified_address["verified_index"] = self.verified_index.cur_count
                self.controller.unverified_address["verified_index_is_change"] = self.verified_index_is_change.cur_count == 1
                return Destination(SeedAddressVerificationSuccessView)

        finally:
            # Halt the thread if the user gave up (will already be stopped if it verified the
            # target addr).
            self.addr_verification_thread.stop()

            # Block until the thread has stopped
            while self.addr_verification_thread.is_alive():
                time.sleep(0.01)

        return Destination(MainMenuView)



    class BruteForceAddressVerificationThread(BaseThread):
        def __init__(self, address: str, seed: Seed, descriptor: Descriptor, script_type: str, embit_network: str, derivation_path: str, threadsafe_counter: ThreadsafeCounter, verified_index: ThreadsafeCounter, verified_index_is_change: ThreadsafeCounter):
            """
                Either seed or descriptor will be None
            """
            super().__init__()
            self.address = address
            self.seed = seed
            self.descriptor = descriptor
            self.script_type = script_type
            self.embit_network = embit_network
            self.derivation_path = derivation_path
            self.threadsafe_counter = threadsafe_counter
            self.verified_index = verified_index
            self.verified_index_is_change = verified_index_is_change

            if self.seed:
                self.xpub = self.seed.get_xpub(wallet_path=self.derivation_path, network=Settings.get_instance().get_value(SettingsConstants.SETTING__NETWORK))


        def run(self):
            from seedsigner.helpers import embit_utils
            while self.keep_running:
                if self.threadsafe_counter.cur_count % 10 == 0:
                    logger.info(f"Incremented to {self.threadsafe_counter.cur_count}")
                
                i = self.threadsafe_counter.cur_count

                if self.descriptor:
                    receive_address = embit_utils.get_multisig_address(descriptor=self.descriptor, index=i, is_change=False, embit_network=self.embit_network)
                    change_address = embit_utils.get_multisig_address(descriptor=self.descriptor, index=i, is_change=True, embit_network=self.embit_network)

                else:
                    receive_address = embit_utils.get_single_sig_address(xpub=self.xpub, script_type=self.script_type, index=i, is_change=False, embit_network=self.embit_network)
                    change_address = embit_utils.get_single_sig_address(xpub=self.xpub, script_type=self.script_type, index=i, is_change=True, embit_network=self.embit_network)
                    
                if self.address == receive_address:
                    self.verified_index.set_value(i)
                    self.verified_index_is_change.set_value(0)
                    self.keep_running = False
                    break

                elif self.address == change_address:
                    self.verified_index.set_value(i)
                    self.verified_index_is_change.set_value(1)
                    self.keep_running = False
                    break

                # Increment our index counter
                self.threadsafe_counter.increment()



class SeedAddressVerificationSuccessView(View):
    def run(self):
        self.run_screen(
            seed_screens.SeedAddressVerificationSuccessScreen,
            address = self.controller.unverified_address["address"],
            verified_index = self.controller.unverified_address["verified_index"],
            verified_index_is_change = self.controller.unverified_address["verified_index_is_change"],
        )

        return Destination(MainMenuView)



class LoadMultisigWalletDescriptorView(View):
    SCAN = ButtonOption("Scan descriptor", SeedSignerIconConstants.QRCODE)
    CANCEL = ButtonOption("Cancel")

    def run(self):
        button_data = [self.SCAN, self.CANCEL]
        selected_menu_num = self.run_screen(
            seed_screens.LoadMultisigWalletDescriptorScreen,
            button_data=button_data,
            show_back_button=False,
        )

        if button_data[selected_menu_num] == self.SCAN:
            from seedsigner.views.scan_views import ScanWalletDescriptorView
            return Destination(ScanWalletDescriptorView)

        elif button_data[selected_menu_num] == self.CANCEL:
            from seedsigner.controller import Controller
            if self.controller.resume_main_flow == Controller.FLOW__PSBT:
                return Destination(BackStackView)
            else:
                return Destination(MainMenuView)



class MultisigWalletDescriptorView(View):
    RETURN = ButtonOption("Return to transaction")
    VERIFY_ADDR = ButtonOption("Verify addr")
    ADDRESS_EXPLORER = ButtonOption("Address explorer")
    OK = ButtonOption("OK")

    def run(self):
        descriptor = self.controller.multisig_wallet_descriptor

        fingerprints = []
        for key in descriptor.keys:
            fingerprint = hexlify(key.fingerprint).decode()
            fingerprints.append(fingerprint)
        
        from seedsigner.helpers.embit_utils import get_multisig_policy
        threshold, n = get_multisig_policy(descriptor)
        # TRANSLATOR_NOTE: Multisig policy. For a "2 of 3" policy, "threshold" = 2; "n" = 3
        policy = _("{threshold} of {n}").format(threshold=threshold, n=n)

        button_data = [self.OK]
        if self.controller.resume_main_flow:
            from seedsigner.controller import Controller
            if self.controller.resume_main_flow == Controller.FLOW__PSBT:
                button_data = [self.RETURN]
            elif self.controller.resume_main_flow == Controller.FLOW__VERIFY_MULTISIG_ADDR and self.controller.unverified_address:
                verify_addr_display = f"""{_(self.VERIFY_ADDR.button_label)} {self.controller.unverified_address["address"][:7]}"""
                button_data = [ButtonOption(verify_addr_display)]
            elif self.controller.resume_main_flow == Controller.FLOW__ADDRESS_EXPLORER:
                button_data = [self.ADDRESS_EXPLORER]

        selected_menu_num = self.run_screen(
            seed_screens.MultisigWalletDescriptorScreen,
            policy=policy,
            fingerprints=fingerprints,
            button_data=button_data,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            self.controller.multisig_wallet_descriptor = None
            return Destination(BackStackView)
        
        elif button_data[selected_menu_num] == self.RETURN:
            # Jump straight back to PSBT change verification
            from seedsigner.views.psbt_views import PSBTChangeDetailsView
            self.controller.resume_main_flow = None
            return Destination(PSBTChangeDetailsView, view_args=dict(change_address_num=0))

        elif button_data[selected_menu_num].button_label.startswith(_(self.VERIFY_ADDR.button_label)):
            self.controller.resume_main_flow = None
            return Destination(SeedAddressVerificationView)

        elif button_data[selected_menu_num] == self.ADDRESS_EXPLORER:
            from seedsigner.views.tools_views import ToolsAddressExplorerAddressTypeView
            self.controller.resume_main_flow = None
            return Destination(ToolsAddressExplorerAddressTypeView)

        return Destination(MainMenuView)



"""****************************************************************************
    Sign Message Views
****************************************************************************"""
class SeedSignMessageStartView(View):
    """
    Routes users straight through to the "Sign" screen if a signing `seed` has
    already been selected. Otherwise routes to `SeedSelectSeedView` to select or
    load a seed first.
    """
    def __init__(self, derivation_path: str, message: str):
        from seedsigner.helpers import embit_utils
        super().__init__()
        self.derivation_path = derivation_path
        self.message = message

        if self.settings.get_value(SettingsConstants.SETTING__MESSAGE_SIGNING) == SettingsConstants.OPTION__DISABLED:
            self.set_redirect(Destination(OptionDisabledView, view_args=dict(settings_attr=SettingsConstants.SETTING__MESSAGE_SIGNING)))
            return

        # calculate the actual receive address
        addr_format = embit_utils.parse_derivation_path(derivation_path)
        if not addr_format["clean_match"]:
            self.set_redirect(Destination(NotYetImplementedView, view_args=dict(text=f"Signing messages for custom derivation paths not supported")))
            self.controller.resume_main_flow = None
            return

        # Note: addr_format["network"] can be MAINNET or [TESTNET, REGTEST]
        if self.settings.get_value(SettingsConstants.SETTING__NETWORK) not in addr_format["network"]:
            from seedsigner.views.view import NetworkMismatchErrorView
            self.set_redirect(Destination(NetworkMismatchErrorView, view_args=dict(derivation_path=self.derivation_path)))

            # cleanup. Note: We could leave this in place so the user can resume the
            # flow, but for now we avoid complications and keep things simple.
            self.controller.resume_main_flow = None
            return

        data = self.controller.sign_message_data
        if data is None:
            data = {}
            self.controller.sign_message_data = data
        data["derivation_path"] = derivation_path
        data["message"] = message
        data["addr_format"] = addr_format

        if data.get("seed") is not None:
            # We already know which seed we're signing with
            self.set_redirect(Destination(SeedSignMessageConfirmMessageView, skip_current_view=True))
        else:
            from seedsigner.controller import Controller
            self.set_redirect(Destination(SeedSelectSeedView, view_args=dict(flow=Controller.FLOW__SIGN_MESSAGE), skip_current_view=True))



class SeedSignMessageConfirmMessageView(View):
    def __init__(self, page_num: int = 0):
        super().__init__()
        self.page_num = page_num  # Note: zero-indexed numbering!


    def run(self):
        from seedsigner.gui.screens.seed_screens import SeedSignMessageConfirmMessageScreen

        selected_menu_num = self.run_screen(
            SeedSignMessageConfirmMessageScreen,
            page_num=self.page_num,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            if self.page_num == 0:
                # We're exiting this flow entirely
                self.controller.resume_main_flow = None
                self.controller.sign_message_data = None
            return Destination(BackStackView)

        # User clicked "Next"
        if self.page_num == len(self.controller.sign_message_data["paged_message"]) - 1:
            # We've reached the end of the paged message
            return Destination(SeedSignMessageConfirmAddressView)
        else:
            return Destination(SeedSignMessageConfirmMessageView, view_args=dict(page_num=self.page_num + 1))



class SeedSignMessageConfirmAddressView(View):
    def __init__(self):
        from seedsigner.helpers import embit_utils
        super().__init__()
        data = self.controller.sign_message_data
        seed = data.get("seed")
        self.derivation_path = data.get("derivation_path")
        addr_format = data.get("addr_format")

        if seed is None or not self.derivation_path:
            raise Exception("Routing error: sign_message_data hasn't been set")

        if not addr_format["clean_match"] or addr_format["script_type"] == SettingsConstants.CUSTOM_DERIVATION:
            raise Exception(_("Signing messages for custom derivation paths not supported"))

        if addr_format["network"] != SettingsConstants.MAINNET:
            # We're in either Testnet or Regtest or...?
            if self.settings.get_value(SettingsConstants.SETTING__NETWORK) in [SettingsConstants.TESTNET, SettingsConstants.REGTEST]:
                addr_format["network"] = self.settings.get_value(SettingsConstants.SETTING__NETWORK)
            else:
                from seedsigner.views.view import NetworkMismatchErrorView
                self.set_redirect(Destination(NetworkMismatchErrorView, view_args=dict(derivation_path=self.derivation_path)))

                # cleanup. Note: We could leave this in place so the user can resume the
                # flow, but for now we avoid complications and keep things simple.
                self.controller.resume_main_flow = None
                self.controller.sign_message_data = None
                return

        xpub = seed.get_xpub(wallet_path=addr_format["wallet_derivation_path"], network=addr_format["network"])
        embit_network = embit_utils.get_embit_network_name(addr_format["network"])
        self.address = embit_utils.get_single_sig_address(xpub=xpub, script_type=addr_format["script_type"], index=addr_format["index"], is_change=addr_format["is_change"], embit_network=embit_network)


    def run(self):
        from seedsigner.gui.screens.seed_screens import SeedSignMessageConfirmAddressScreen
        selected_menu_num = self.run_screen(
            SeedSignMessageConfirmAddressScreen,
            derivation_path=self.derivation_path,
            address=self.address,
        )

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        # User clicked "Sign Message"
        return Destination(SeedSignMessageSignedMessageQRView)



class SeedSignMessageSignedMessageQRView(View):
    """
    Displays the signed message as a QR code.
    """
    def __init__(self):
        from seedsigner.helpers import embit_utils
        super().__init__()
        data = self.controller.sign_message_data

        self.seed = data["seed"]
        derivation_path = data["derivation_path"]
        message: str = data["message"]

        self.signed_message = embit_utils.sign_message(seed_bytes=self.seed.seed_bytes, derivation=derivation_path, msg=message.encode())


    def run(self):
        from seedsigner.gui.screens.screen import QRDisplayScreen
        qr_encoder = GenericStaticQrEncoder(data=self.signed_message)
        
        self.run_screen(
            QRDisplayScreen,
            qr_encoder=qr_encoder,
        )
    
        # cleanup
        self.controller.resume_main_flow = None
        self.controller.sign_message_data = None

        # Exiting/Canceling the QR display screen always returns Home
        return Destination(MainMenuView, skip_current_view=True)
