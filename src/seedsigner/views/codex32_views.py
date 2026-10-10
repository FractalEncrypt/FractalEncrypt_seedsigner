"""Review and confirm bounded codex32 corrections before accepting a share."""

from dataclasses import dataclass
from gettext import gettext as _

from seedsigner.gui.screens import seed_screens
from seedsigner.gui.screens.screen import ButtonListScreen, ButtonOption, RET_CODE__BACK_BUTTON
from seedsigner.models import codex32 as codex32_model
from seedsigner.models.codex32_correction import Codex32Correction
from seedsigner.models.seed import Codex32Seed
from seedsigner.views.view import Destination, MainMenuView, View


@dataclass(frozen=True, repr=False)
class CorrectionFlow:
    proposal: Codex32Correction
    share_num: int = 1
    prefill: str = "MS1"
    share_collection: codex32_model.Codex32ShareCollection | None = None
    replace_existing: bool = False
    entry_method: str = "manual"

    def entry_destination(self, accepted: bool = False, unverified: bool = False) -> Destination:
        from .seed_views import Codex32EntryView

        return Destination(
            Codex32EntryView,
            view_args={
                "share_num": self.share_num,
                "prefill": self.prefill,
                "share_data": self.proposal.corrected if accepted else self.proposal.original,
                "share_collection": self.share_collection,
                "replace_existing": self.replace_existing,
                "entry_method": self.entry_method,
                "auto_submit_share_data": accepted,
                "correction_record": (self.proposal, unverified) if accepted else None,
            },
            skip_current_view=True,
        )


class Codex32LargeRecoveryWarningView(View):
    REVIEW = ButtonOption("Review Reconstruction")
    EDIT = ButtonOption("Review & Edit")

    def __init__(self, flow: CorrectionFlow):
        super().__init__()
        self.flow = flow

    def run(self):
        count = len(self.flow.proposal.erasure_indices)
        if count == 13:
            text = _("13 unknown characters use all checksum redundancy. Another typo can produce the wrong seed. Check readable boxes and verify the recovered fingerprint.")
        else:
            text = _("This large reconstruction leaves little checksum evidence. Another typo can produce the wrong seed. Check readable boxes and verify the recovered fingerprint.")
        buttons = [self.REVIEW, self.EDIT]
        selected = self.run_screen(
            seed_screens.Codex32MessageScreen, title=_("Large Recovery"),
            text=text, button_data=buttons, show_back_button=False,
        )
        if selected == RET_CODE__BACK_BUTTON or buttons[selected] == self.EDIT:
            return self.flow.entry_destination()
        return Destination(Codex32CorrectionReviewView, {"flow": self.flow}, skip_current_view=True)


class Codex32CorrectionReviewView(View):
    NEXT = ButtonOption("Next")
    CONFIRM = ButtonOption("Review Each Change")

    def __init__(self, flow: CorrectionFlow, page_index: int = 0):
        super().__init__()
        self.flow = flow
        self.page_index = page_index

    def run(self):
        buttons = [self.NEXT if self.page_index == 0 else self.CONFIRM]
        selected = self.run_screen(
            seed_screens.Codex32MasterSecretDisplayScreen,
            share_data=self.flow.proposal.corrected,
            share_idx=self.flow.proposal.corrected[8],
            start_index=self.page_index * 24,
            highlight_indices=self.flow.proposal.changed_indices,
            display_title=_("Review Correction"),
            display_back_button=True,
            boxes_label=_("Boxes {}-{}: * changed").format(self.page_index * 24 + 1, self.page_index * 24 + 24),
            button_data=buttons,
        )
        if selected == RET_CODE__BACK_BUTTON:
            if self.page_index:
                return Destination(Codex32CorrectionReviewView, {"flow": self.flow}, skip_current_view=True)
            return self.flow.entry_destination()
        if self.page_index == 0:
            return Destination(Codex32CorrectionReviewView, {"flow": self.flow, "page_index": 1}, skip_current_view=True)
        return Destination(Codex32CorrectionDetailsView, {"flow": self.flow}, skip_current_view=True)


class Codex32CorrectionDetailsView(View):
    NEXT = ButtonOption("Next Changes")
    CONFIRM = ButtonOption("Continue")
    CHANGES_PER_PAGE = 4

    def __init__(self, flow: CorrectionFlow, page_index: int = 0):
        super().__init__()
        self.flow = flow
        self.page_index = page_index

    def run(self):
        proposal = self.flow.proposal
        start = self.page_index * self.CHANGES_PER_PAGE
        indices = proposal.changed_indices[start:start + self.CHANGES_PER_PAGE]
        last_page = start + len(indices) == len(proposal.changed_indices)
        selected = self.run_screen(
            seed_screens.Codex32CorrectionDetailsScreen,
            changes=tuple((i + 1, proposal.original[i], proposal.corrected[i]) for i in indices),
            changes_label=_("Changes {}-{} of {}").format(start + 1, start + len(indices), len(proposal.changed_indices)),
            button_data=[self.CONFIRM if last_page else self.NEXT],
        )
        if selected == RET_CODE__BACK_BUTTON:
            if self.page_index:
                return Destination(Codex32CorrectionDetailsView, {"flow": self.flow, "page_index": self.page_index - 1}, skip_current_view=True)
            return Destination(Codex32CorrectionReviewView, {"flow": self.flow, "page_index": 1}, skip_current_view=True)
        if not last_page:
            return Destination(Codex32CorrectionDetailsView, {"flow": self.flow, "page_index": self.page_index + 1}, skip_current_view=True)
        return Destination(Codex32CorrectionCauseView, {"flow": self.flow}, skip_current_view=True)


class Codex32CorrectionCauseView(View):
    MISTYPED = ButtonOption("I Mistyped")
    REPAIR = ButtonOption("Backup Corrupted")
    REVIEW = ButtonOption("Review Corrections")

    def __init__(self, flow: CorrectionFlow):
        super().__init__()
        self.flow = flow

    def run(self):
        buttons = [self.MISTYPED, self.REPAIR, self.REVIEW]
        selected = self.run_screen(
            seed_screens.Codex32MessageScreen, title=_("Where is the error?"),
            text=_("Did you mistype, or does your backup need repair?"),
            button_data=buttons, show_back_button=False,
        )
        if selected == RET_CODE__BACK_BUTTON or buttons[selected] == self.REVIEW:
            return Destination(Codex32CorrectionDetailsView, {"flow": self.flow}, skip_current_view=True)
        if buttons[selected] == self.REPAIR:
            return Destination(Codex32BackupRepairView, {"flow": self.flow}, skip_current_view=True)
        target = Codex32CorrectionProofView if self.flow.proposal.erasure_indices else Codex32CorrectionEntryView
        return Destination(target, {"flow": self.flow}, skip_current_view=True)


class Codex32BackupRepairView(View):
    NEXT = ButtonOption("Next Repairs")
    READY = ButtonOption("Backup Ready")
    UNREADABLE = ButtonOption("Characters Unreadable")
    CHANGES_PER_PAGE = 3

    def __init__(self, flow: CorrectionFlow, page_index: int = 0):
        super().__init__()
        self.flow = flow
        self.page_index = page_index

    def run(self):
        proposal = self.flow.proposal
        start = self.page_index * self.CHANGES_PER_PAGE
        indices = proposal.changed_indices[start:start + self.CHANGES_PER_PAGE]
        last_page = start + len(indices) == len(proposal.changed_indices)
        buttons = [self.READY if last_page else self.NEXT]
        if last_page and proposal.erasure_indices:
            buttons.append(self.UNREADABLE)
        selected = self.run_screen(
            seed_screens.Codex32CorrectionDetailsScreen,
            changes=tuple((i + 1, proposal.original[i], proposal.corrected[i]) for i in indices),
            changes_label=_("Repairs {}-{} of {}").format(start + 1, start + len(indices), len(proposal.changed_indices)),
            repair_mode=True, button_data=buttons,
        )
        if selected == RET_CODE__BACK_BUTTON:
            if self.page_index:
                return Destination(Codex32BackupRepairView, {"flow": self.flow, "page_index": self.page_index - 1}, skip_current_view=True)
            return Destination(Codex32CorrectionCauseView, {"flow": self.flow}, skip_current_view=True)
        if not last_page:
            return Destination(Codex32BackupRepairView, {"flow": self.flow, "page_index": self.page_index + 1}, skip_current_view=True)
        if buttons[selected] == self.UNREADABLE:
            return Destination(Codex32ReconstructionAcceptView, {"flow": self.flow}, skip_current_view=True)
        return Destination(Codex32CorrectionEntryView, {"flow": self.flow, "backup_repaired": True}, skip_current_view=True)


class Codex32CorrectionProofView(View):
    RETYPE = ButtonOption("Re-enter from Backup")
    UNREADABLE = ButtonOption("Characters Unreadable")
    EDIT = ButtonOption("Review & Edit Original")

    def __init__(self, flow: CorrectionFlow):
        super().__init__()
        self.flow = flow

    def run(self):
        buttons = [self.RETYPE, self.UNREADABLE, self.EDIT]
        selected = self.run_screen(
            seed_screens.Codex32MessageScreen, title=_("Check Your Backup"),
            text=_("Can you read the proposed characters on your backup? Re-enter them if readable."),
            button_data=buttons, show_back_button=False,
        )
        if selected == RET_CODE__BACK_BUTTON or buttons[selected] == self.EDIT:
            return self.flow.entry_destination()
        if buttons[selected] == self.UNREADABLE:
            return Destination(Codex32ReconstructionAcceptView, {"flow": self.flow}, skip_current_view=True)
        return Destination(Codex32CorrectionEntryView, {"flow": self.flow}, skip_current_view=True)


class Codex32ReconstructionAcceptView(View):
    ACCEPT = ButtonOption("Accept Reconstruction")
    EDIT = ButtonOption("Review & Edit Original")

    def __init__(self, flow: CorrectionFlow):
        super().__init__()
        self.flow = flow

    def run(self):
        buttons = [self.ACCEPT, self.EDIT]
        selected = self.run_screen(
            seed_screens.Codex32MessageScreen, title=_("Unverified Characters"),
            text=_("Unreadable characters cannot be checked against the backup. Compare the recovered fingerprint with a trusted record before using the seed."),
            button_data=buttons, show_back_button=False,
        )
        if selected == RET_CODE__BACK_BUTTON or buttons[selected] == self.EDIT:
            return self.flow.entry_destination()
        if self.flow.proposal.substitution_indices:
            return Destination(Codex32CorrectionEntryView, {"flow": self.flow, "unreadable": True}, skip_current_view=True)
        return self.flow.entry_destination(accepted=True, unverified=True)


class Codex32CorrectionEntryView(View):
    def __init__(self, flow: CorrectionFlow, unreadable: bool = False, backup_repaired: bool = False):
        super().__init__()
        self.flow = flow
        self.unreadable = unreadable
        self.backup_repaired = backup_repaired

    def run(self):
        proposal = self.flow.proposal
        indices = proposal.substitution_indices if self.unreadable else proposal.changed_indices
        ret = self.run_screen(
            seed_screens.Codex32EntryScreen,
            share_num=self.flow.share_num, prefill=self.flow.prefill,
            share_data=proposal.corrected, share_collection=self.flow.share_collection,
            reentry_indices=indices, allow_unknown=False,
            start_page=min(indices) // 4,
            warning_message_default=_("Read * boxes from backup"),
        )
        if ret == RET_CODE__BACK_BUTTON:
            return self.flow.entry_destination()
        # Exact equality is required; correction is never run on proof input.
        if not isinstance(ret, str) or ret.upper() != proposal.corrected:
            return Destination(
                Codex32CorrectionMismatchView,
                {"flow": self.flow, "unreadable": self.unreadable, "backup_repaired": self.backup_repaired},
                skip_current_view=True,
            )
        return self.flow.entry_destination(accepted=True, unverified=self.unreadable or self.backup_repaired)


class Codex32CorrectionMismatchView(View):
    RETRY = ButtonOption("Re-enter Again")
    EDIT = ButtonOption("Review & Edit Original")

    def __init__(self, flow: CorrectionFlow, unreadable: bool = False, backup_repaired: bool = False):
        super().__init__()
        self.flow = flow
        self.unreadable = unreadable
        self.backup_repaired = backup_repaired

    def run(self):
        buttons = [self.RETRY, self.EDIT]
        selected = self.run_screen(
            seed_screens.Codex32MessageScreen, title=_("Backup Differs"),
            text=_("Your re-entry does not match the proposal. Check the numbered boxes on your backup. The share has not been accepted."),
            button_data=buttons, show_back_button=False,
        )
        if selected == RET_CODE__BACK_BUTTON or buttons[selected] == self.EDIT:
            return self.flow.entry_destination()
        return Destination(Codex32CorrectionEntryView, {"flow": self.flow, "unreadable": self.unreadable, "backup_repaired": self.backup_repaired}, skip_current_view=True)


class Codex32RecoveryReviewView(View):
    DONE = ButtonOption("Return to Fingerprint")

    def __init__(self, corrections: dict | None = None):
        super().__init__()
        self.corrections = corrections or {}

    def run(self):
        from .seed_views import Codex32EntryView, Codex32MasterShareSuccessView

        seed = self.controller.storage.get_pending_seed()
        if not isinstance(seed, Codex32Seed):
            return Destination(MainMenuView, clear_history=True)
        shares = seed.codex32_export_shares or {}
        sources = seed.codex32_share_sources or {}
        indices = [i for i in codex32_model.Codex32ShareCollection.ordered_share_indices(shares) if sources.get(i) == "entered"]
        buttons = [ButtonOption(_("Review Share {}").format(i.upper())) for i in indices] + [self.DONE]
        selected = self.run_screen(ButtonListScreen, title=_("Review Shares"), button_data=buttons)
        if selected == RET_CODE__BACK_BUTTON or buttons[selected] == self.DONE:
            return Destination(Codex32MasterShareSuccessView, {"corrections": self.corrections}, skip_current_view=True)
        index = indices[selected]
        split = [codex32_model.parse_codex32_share(shares[i]) for i in indices if i != "s"]
        collection = None
        if split:
            collection = codex32_model.Codex32ShareCollection.from_first_share(split[0])
            for share in split[1:]:
                collection.add_share(share)
            if "s" in indices:
                collection.add_share(codex32_model.parse_codex32_share(shares["s"]))
            collection.corrections.update(self.corrections)
        proposal = self.corrections.get(index)
        original = proposal[0].original if proposal else shares[index]
        # Parse/copy before releasing pending seed metadata. Re-entry must rebuild it.
        self.controller.storage.clear_pending_seed()
        self.corrections = {}
        return Destination(
            Codex32EntryView,
            {"share_data": original, "prefill": collection.prefix() if collection else "MS1",
             "share_collection": collection, "replace_existing": collection is not None,
              "resolve_unknowns": "?" in original},
            clear_history=True,
        )


class Codex32FingerprintCheckView(View):
    ENTER = ButtonOption("Enter Fingerprint")
    VISUAL = ButtonOption("Compare Visually")
    NO_RECORD = ButtonOption("No Fingerprint Record")

    def __init__(self, corrections: dict | None = None, fingerprint_check: tuple | None = None):
        super().__init__()
        self.corrections = corrections if corrections is not None else {}
        self.fingerprint_check = fingerprint_check

    def current_fingerprint(self):
        from seedsigner.models.settings_definition import SettingsConstants
        seed = self.controller.storage.get_pending_seed()
        if not isinstance(seed, Codex32Seed):
            return None
        return seed.get_fingerprint(self.settings.get_value(SettingsConstants.SETTING__NETWORK)).lower()

    def navigation_args(self):
        # Only cancellation preserves a previous check. A new result supplies its
        # own marker, and mismatch/no-record choices deliberately clear it.
        return {"corrections": self.corrections, "fingerprint_check": self.fingerprint_check}

    def return_to_fingerprint(self, method=None, preserve_check=False):
        from .seed_views import Codex32MasterShareSuccessView
        fingerprint = self.current_fingerprint()
        if fingerprint is None:
            return Destination(MainMenuView, clear_history=True)
        return Destination(
            Codex32MasterShareSuccessView,
            {"corrections": self.corrections,
             "fingerprint_check": self.fingerprint_check if preserve_check else ((method, fingerprint) if method else None)},
            skip_current_view=True,
        )

    def run(self):
        if self.current_fingerprint() is None:
            return Destination(MainMenuView, clear_history=True)
        buttons = [self.ENTER, self.VISUAL, self.NO_RECORD]
        selected = self.run_screen(
            seed_screens.Codex32MessageScreen, title=_("Check Fingerprint"),
            text=_("Compare with the fingerprint saved on your backup or wallet setup notes before this recovery."),
            button_data=buttons,
        )
        if selected == RET_CODE__BACK_BUTTON:
            return self.return_to_fingerprint(preserve_check=True)
        target = (Codex32FingerprintEntryView, Codex32FingerprintVisualView,
                  Codex32FingerprintNoRecordView)[selected]
        return Destination(target, self.navigation_args(), skip_current_view=True)


class Codex32FingerprintEntryView(Codex32FingerprintCheckView):
    def run(self):
        if self.current_fingerprint() is None:
            return Destination(MainMenuView, clear_history=True)
        entered = self.run_screen(seed_screens.Codex32FingerprintEntryScreen)
        if entered == RET_CODE__BACK_BUTTON:
            return Destination(Codex32FingerprintCheckView, self.navigation_args(), skip_current_view=True)
        # Validate here too: an incomplete/non-hex response is never a comparison.
        if not isinstance(entered, str) or len(entered) != 8 or any(c not in "0123456789abcdef" for c in entered.lower()):
            return Destination(Codex32FingerprintEntryView, self.navigation_args(), skip_current_view=True)
        return Destination(Codex32FingerprintResultView,
                           {"corrections": self.corrections, "recorded_fingerprint": entered.lower()},
                           skip_current_view=True)


class Codex32FingerprintVisualView(Codex32FingerprintCheckView):
    MATCH = ButtonOption("Matches My Record")
    MISMATCH = ButtonOption("Does Not Match")

    def run(self):
        fingerprint = self.current_fingerprint()
        if fingerprint is None:
            return Destination(MainMenuView, clear_history=True)
        buttons = [self.MATCH, self.MISMATCH]
        selected = self.run_screen(
            seed_screens.Codex32MasterShareSuccessScreen, fingerprint=fingerprint,
            button_data=buttons,
            unverified_correction=any(record[1] for record in self.corrections.values()),
            corrected_share=bool(self.corrections),
        )
        if selected == RET_CODE__BACK_BUTTON:
            return Destination(Codex32FingerprintCheckView, self.navigation_args(), skip_current_view=True)
        return Destination(Codex32FingerprintResultView,
                           {"corrections": self.corrections, "visual_match": buttons[selected] == self.MATCH},
                           skip_current_view=True)


class Codex32FingerprintResultView(Codex32FingerprintCheckView):
    LOAD = ButtonOption("Load Seed")
    MORE = ButtonOption("More Options")
    CONTINUE = ButtonOption("Return to Fingerprint")
    RETRY = ButtonOption("Try Again")
    REVIEW = ButtonOption("Review Entered Shares")

    def __init__(self, corrections: dict | None = None, recorded_fingerprint: str | None = None,
                 visual_match: bool | None = None):
        super().__init__(corrections)
        self.recorded_fingerprint = recorded_fingerprint
        self.visual_match = visual_match

    def run(self):
        fingerprint = self.current_fingerprint()
        if fingerprint is None:
            return Destination(MainMenuView, clear_history=True)
        recorded = self.recorded_fingerprint
        valid_record = isinstance(recorded, str) and len(recorded) == 8 and all(c in "0123456789abcdef" for c in recorded)
        matched = recorded == fingerprint if valid_record else self.visual_match is True and recorded is None
        if matched:
            text = _("Saved fingerprint matches (32-bit check). Verify the wallet policy and a known address.")
            if any(record[1] for record in self.corrections.values()):
                text = _("32-bit fingerprint match. Share repairs unverified. Check wallet policy and a known address.")
            buttons = [self.LOAD, self.MORE]
            title = _("Record Matches")
        else:
            text = (_("Record: {}\nSeed: {}\nReview shares.").format(recorded, fingerprint)
                    if valid_record else _("Does not match. Check your record and shares."))
            buttons = [self.RETRY, self.REVIEW, self.CONTINUE]
            title = _("Record Mismatch")
        selected = self.run_screen(
            seed_screens.Codex32FingerprintResultScreen, title=title, text=text, button_data=buttons,
            matched=matched, unverified_correction=any(record[1] for record in self.corrections.values()),
        )
        if selected == RET_CODE__BACK_BUTTON:
            return Destination(Codex32FingerprintCheckView, self.navigation_args(), skip_current_view=True)
        if matched and buttons[selected] == self.LOAD:
            from .seed_views import SeedFinalizeView
            self.controller.codex32_temp_share = None
            self.corrections.clear()
            return Destination(SeedFinalizeView, clear_history=True)
        if matched and buttons[selected] == self.MORE:
            destination = self.return_to_fingerprint("entered" if valid_record else "visual")
            destination.view_args["show_options"] = True
            return destination
        if buttons[selected] == self.REVIEW:
            return Destination(Codex32RecoveryReviewView, {"corrections": self.corrections}, skip_current_view=True)
        if buttons[selected] == self.RETRY:
            return Destination(Codex32FingerprintCheckView, self.navigation_args(), skip_current_view=True)
        return self.return_to_fingerprint(("entered" if valid_record else "visual") if matched else None)


class Codex32FingerprintNoRecordView(Codex32FingerprintCheckView):
    DONE = ButtonOption("Return to Fingerprint")

    def run(self):
        if self.current_fingerprint() is None:
            return Destination(MainMenuView, clear_history=True)
        self.run_screen(
            seed_screens.Codex32MessageScreen, title=_("Without a Record"),
            text=_("Existing wallet? Verify its policy and a known address in your coordinator. First setup? Check worksheets, record the fingerprint, then restart and repeat recovery. A new record cannot verify this recovery."),
            button_data=[self.DONE],
        )
        return self.return_to_fingerprint()
