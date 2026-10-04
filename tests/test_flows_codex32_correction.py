from unittest.mock import Mock, patch

from base import BaseTest, FlowTest, FlowStep
from seedsigner.models import codex32 as model
from seedsigner.models.codex32_correction import suggest_correction
from seedsigner.models.seed import Codex32Seed
from seedsigner.gui.screens.screen import RET_CODE__BACK_BUTTON
from seedsigner.views import seed_views
from seedsigner.views import codex32_views as views
from seedsigner.views.view import MainMenuView

SHARE_A = "MS12NAMEA320ZYXWVUTSRQPNMLKJHGFEDCAXRPP870HKKQRM"
SHARE_C = "MS12NAMECACDEFGHJKLMNPQRSTUVWXYZ023FTR2GDZMPY6PN"
SECRET = "MS12NAMES6XQGUZTTXKEQNJSJZV4JV3NZ5K3KWGSPHUH6EVW"
DAMAGED = SHARE_A[:17] + "Q" + SHARE_A[18:]


class TestCorrectionFlows(FlowTest):
    def test_substitution_requires_review_and_exact_reentry_before_acceptance(self):
        def not_accepted(view):
            assert self.controller.storage.pending_seed is None
            assert view.flow.share_collection is None

        self.run_sequence([
            FlowStep(MainMenuView, button_data_selection=MainMenuView.SEEDS),
            FlowStep(seed_views.SeedsMenuView, is_redirect=True),
            FlowStep(seed_views.LoadSeedView, button_data_selection=seed_views.LoadSeedView.TYPE_CODEX32),
            FlowStep(seed_views.Codex32EntryView, screen_return_value=DAMAGED),
            FlowStep(seed_views.Codex32ShareInvalidView, button_data_selection=seed_views.Codex32ShareInvalidView.CORRECTION),
            FlowStep(views.Codex32CorrectionReviewView, before_run=not_accepted, button_data_selection=views.Codex32CorrectionReviewView.NEXT),
            FlowStep(views.Codex32CorrectionReviewView, button_data_selection=views.Codex32CorrectionReviewView.CONFIRM),
            FlowStep(views.Codex32CorrectionDetailsView, button_data_selection=views.Codex32CorrectionDetailsView.CONFIRM),
            FlowStep(views.Codex32CorrectionCauseView, button_data_selection=views.Codex32CorrectionCauseView.MISTYPED),
            FlowStep(views.Codex32CorrectionEntryView, screen_return_value=DAMAGED),
            FlowStep(views.Codex32CorrectionMismatchView, before_run=not_accepted, button_data_selection=views.Codex32CorrectionMismatchView.RETRY),
            FlowStep(views.Codex32CorrectionEntryView, screen_return_value=SHARE_A),
            FlowStep(seed_views.Codex32EntryView, is_redirect=True),
            FlowStep(seed_views.Codex32ShareSuccessView, button_data_selection=seed_views.Codex32ShareSuccessView.NEXT),
            FlowStep(seed_views.Codex32EntryView, screen_return_value=SHARE_C),
            FlowStep(seed_views.Codex32MasterShareSuccessView),
        ])
        assert self.controller.storage.pending_seed.codex32_master_share == SECRET

    def test_thirteen_erasures_warn_before_revealing_and_accept_unreadable_separately(self):
        damaged = SHARE_A[:15] + "?" * 13 + SHARE_A[28:]
        self.run_sequence([
            FlowStep(MainMenuView, button_data_selection=MainMenuView.SEEDS),
            FlowStep(seed_views.SeedsMenuView, is_redirect=True),
            FlowStep(seed_views.LoadSeedView, button_data_selection=seed_views.LoadSeedView.TYPE_CODEX32),
            FlowStep(seed_views.Codex32EntryView, screen_return_value=damaged),
            FlowStep(seed_views.Codex32ShareInvalidView, button_data_selection=seed_views.Codex32ShareInvalidView.CORRECTION),
            FlowStep(views.Codex32LargeRecoveryWarningView, button_data_selection=views.Codex32LargeRecoveryWarningView.REVIEW),
            FlowStep(views.Codex32CorrectionReviewView, button_data_selection=views.Codex32CorrectionReviewView.NEXT),
            FlowStep(views.Codex32CorrectionReviewView, button_data_selection=views.Codex32CorrectionReviewView.CONFIRM),
            FlowStep(views.Codex32CorrectionDetailsView, button_data_selection=views.Codex32CorrectionDetailsView.NEXT),
            FlowStep(views.Codex32CorrectionDetailsView, button_data_selection=views.Codex32CorrectionDetailsView.NEXT),
            FlowStep(views.Codex32CorrectionDetailsView, button_data_selection=views.Codex32CorrectionDetailsView.NEXT),
            FlowStep(views.Codex32CorrectionDetailsView, button_data_selection=views.Codex32CorrectionDetailsView.CONFIRM),
            FlowStep(views.Codex32CorrectionCauseView, button_data_selection=views.Codex32CorrectionCauseView.REPAIR),
            FlowStep(views.Codex32BackupRepairView, button_data_selection=views.Codex32BackupRepairView.NEXT),
            FlowStep(views.Codex32BackupRepairView, button_data_selection=views.Codex32BackupRepairView.NEXT),
            FlowStep(views.Codex32BackupRepairView, button_data_selection=views.Codex32BackupRepairView.NEXT),
            FlowStep(views.Codex32BackupRepairView, button_data_selection=views.Codex32BackupRepairView.NEXT),
            FlowStep(views.Codex32BackupRepairView, button_data_selection=views.Codex32BackupRepairView.UNREADABLE),
            FlowStep(views.Codex32ReconstructionAcceptView, button_data_selection=views.Codex32ReconstructionAcceptView.ACCEPT),
            FlowStep(seed_views.Codex32EntryView, is_redirect=True),
            FlowStep(seed_views.Codex32ShareSuccessView),
        ])


class TestCorrectionBoundaries(BaseTest):
    def test_multi_error_review_shows_every_numbered_entered_proposed_pair(self):
        damaged = SHARE_A[:15] + "?" * 13 + SHARE_A[28:]
        flow = views.CorrectionFlow(suggest_correction(damaged))
        shown = []
        for page in range(4):
            view = views.Codex32CorrectionDetailsView(flow, page_index=page)
            view.run_screen = Mock(return_value=0)
            destination = view.run()
            kwargs = view.run_screen.call_args.kwargs
            shown.extend(kwargs["changes"])
            if page < 3:
                assert destination.View_cls == views.Codex32CorrectionDetailsView
                assert destination.view_args["page_index"] == page + 1
                assert kwargs["button_data"] == [views.Codex32CorrectionDetailsView.NEXT]
            else:
                assert destination.View_cls == views.Codex32CorrectionCauseView
        assert shown == [(i + 1, "?", SHARE_A[i]) for i in range(15, 28)]
        assert self.controller.storage.pending_seed is None

    def test_change_review_back_returns_to_previous_page_or_numbered_overview(self):
        flow = views.CorrectionFlow(suggest_correction(SHARE_A[:15] + "?" * 13 + SHARE_A[28:]))
        for page, expected_cls, expected_page in (
            (1, views.Codex32CorrectionDetailsView, 0),
            (0, views.Codex32CorrectionReviewView, 1),
        ):
            view = views.Codex32CorrectionDetailsView(flow, page_index=page)
            view.run_screen = Mock(return_value=RET_CODE__BACK_BUTTON)
            destination = view.run()
            assert destination.View_cls == expected_cls
            assert destination.view_args["page_index"] == expected_page

    def test_repaired_backup_requires_reentry_and_retains_unverified_status_on_retry(self):
        flow = views.CorrectionFlow(suggest_correction(DAMAGED))
        cause = views.Codex32CorrectionCauseView(flow)
        cause.run_screen = Mock(return_value=1)
        destination = cause.run()
        assert destination.View_cls == views.Codex32BackupRepairView
        repair = destination.View_cls(**destination.view_args)
        repair.run_screen = Mock(return_value=0)
        destination = repair.run()
        assert destination.View_cls == views.Codex32CorrectionEntryView
        assert destination.view_args["backup_repaired"] is True
        assert self.controller.storage.pending_seed is None
        entry = destination.View_cls(**destination.view_args)
        entry.run_screen = Mock(return_value=DAMAGED)
        mismatch_destination = entry.run()
        mismatch = mismatch_destination.View_cls(**mismatch_destination.view_args)
        mismatch.run_screen = Mock(return_value=0)
        retry_destination = mismatch.run()
        assert retry_destination.view_args["backup_repaired"] is True
        retry = retry_destination.View_cls(**retry_destination.view_args)
        retry.run_screen = Mock(return_value=SHARE_A)
        accepted = retry.run()
        assert retry.run_screen.call_args.kwargs["reentry_indices"] == (17,)
        assert accepted.view_args["correction_record"] == (flow.proposal, True)

    def test_repaired_readable_erasures_require_all_changed_boxes(self):
        proposal = suggest_correction(DAMAGED[:25] + "?" + DAMAGED[26:])
        view = views.Codex32CorrectionEntryView(views.CorrectionFlow(proposal), backup_repaired=True)
        view.run_screen = Mock(return_value=SHARE_A)
        destination = view.run()
        assert view.run_screen.call_args.kwargs["reentry_indices"] == (17, 25)
        assert destination.view_args["correction_record"][1] is True

    def test_cause_screen_returns_to_corrections_and_repair_back_returns_to_cause(self):
        flow = views.CorrectionFlow(suggest_correction(DAMAGED))
        for selected in (2, RET_CODE__BACK_BUTTON):
            view = views.Codex32CorrectionCauseView(flow)
            view.run_screen = Mock(return_value=selected)
            destination = view.run()
            assert destination.View_cls == views.Codex32CorrectionDetailsView
            assert self.controller.storage.pending_seed is None
        repair = views.Codex32BackupRepairView(flow)
        repair.run_screen = Mock(return_value=RET_CODE__BACK_BUTTON)
        assert repair.run().View_cls == views.Codex32CorrectionCauseView

    def test_repair_pages_show_all_changes_before_backup_ready(self):
        flow = views.CorrectionFlow(suggest_correction(SHARE_A[:15] + "?" * 8 + SHARE_A[23:]))
        shown = []
        for page in range(3):
            repair = views.Codex32BackupRepairView(flow, page_index=page)
            repair.run_screen = Mock(return_value=0)
            destination = repair.run()
            kwargs = repair.run_screen.call_args.kwargs
            assert kwargs["repair_mode"] is True
            shown.extend(kwargs["changes"])
            if page < 2:
                assert kwargs["button_data"] == [views.Codex32BackupRepairView.NEXT]
                assert destination.View_cls == views.Codex32BackupRepairView
                assert destination.view_args["page_index"] == page + 1
            else:
                assert kwargs["button_data"][0] == views.Codex32BackupRepairView.READY
                assert destination.View_cls == views.Codex32CorrectionEntryView
                assert destination.view_args["backup_repaired"] is True
        assert shown == [(i + 1, "?", SHARE_A[i]) for i in range(15, 23)]
        back = views.Codex32BackupRepairView(flow, page_index=1)
        back.run_screen = Mock(return_value=RET_CODE__BACK_BUTTON)
        destination = back.run()
        assert destination.View_cls == views.Codex32BackupRepairView
        assert destination.view_args["page_index"] == 0

    def test_manual_review_keeps_original_and_declining_large_recovery_does_not_accept(self):
        proposal = suggest_correction(SHARE_A[:15] + "?" * 13 + SHARE_A[28:])
        flow = views.CorrectionFlow(proposal)
        view = views.Codex32LargeRecoveryWarningView(flow)
        view.run_screen = Mock(return_value=1)
        dest = view.run()
        assert dest.view_args["share_data"] == proposal.original
        assert dest.view_args["auto_submit_share_data"] is False
        assert self.controller.storage.pending_seed is None

    def test_mixed_unreadable_recovery_still_requires_known_substitutions_retyped(self):
        damaged = DAMAGED[:25] + "?" + DAMAGED[26:]
        proposal = suggest_correction(damaged)
        view = views.Codex32ReconstructionAcceptView(views.CorrectionFlow(proposal))
        view.run_screen = Mock(return_value=0)
        dest = view.run()
        assert dest.View_cls == views.Codex32CorrectionEntryView
        assert dest.view_args["unreadable"] is True
        entry = dest.View_cls(**dest.view_args)
        entry.run_screen = Mock(return_value=SHARE_A)
        entry.run()
        assert entry.run_screen.call_args.kwargs["reentry_indices"] == (17,)
        assert entry.run_screen.call_args.kwargs["allow_unknown"] is False

    def test_fingerprint_visible_immediately_and_review_rebuilds_original_session(self):
        collection = model.Codex32ShareCollection.from_first_share(model.parse_codex32_share(SHARE_A))
        collection.add_share(model.parse_codex32_share(SHARE_C))
        proposal = suggest_correction(DAMAGED)
        collection.corrections["a"] = (proposal, True)
        destination = seed_views.Codex32EntryView._destination_from_share_collection(seed_views.Codex32EntryView(), collection, 2)
        assert collection.is_wiped and collection.corrections == {}
        success = destination.View_cls(**destination.view_args)
        success.run_screen = Mock(return_value=2)
        review = success.run()
        assert success.run_screen.call_args.kwargs["fingerprint"] == self.controller.storage.pending_seed.get_fingerprint()
        assert success.run_screen.call_args.kwargs["unverified_correction"] is True
        assert review.view_args["show_options"] is True
        options = review.View_cls(**review.view_args)
        options.run_screen = Mock(return_value=1)
        review = options.run()
        assert review.View_cls == views.Codex32RecoveryReviewView
        chooser = review.View_cls(**review.view_args)
        chooser.run_screen = Mock(return_value=0)
        entry = chooser.run()
        assert entry.View_cls == seed_views.Codex32EntryView
        assert entry.view_args["share_data"] == DAMAGED
        assert entry.view_args["replace_existing"] is True
        assert entry.view_args["share_collection"].get_share("c").s == SHARE_C
        assert entry.view_args["share_collection"].corrections["a"] == (proposal, True)
        assert self.controller.storage.pending_seed is None
        assert entry.clear_history is True

    def test_proof_input_is_never_corrected_even_when_another_repair_is_available(self):
        view = views.Codex32CorrectionEntryView(views.CorrectionFlow(suggest_correction(DAMAGED)))
        view.run_screen = Mock(return_value=DAMAGED)
        with patch("seedsigner.models.codex32_correction.suggest_correction", side_effect=AssertionError("Proof must not be repaired")):
            assert view.run().View_cls == views.Codex32CorrectionMismatchView

    def test_omitted_unverified_split_does_not_mark_clean_entered_s(self):
        collection = model.Codex32ShareCollection.from_first_share(model.parse_codex32_share(SHARE_A))
        collection.corrections["a"] = (suggest_correction(DAMAGED), True)
        collection.add_share(model.parse_codex32_share(SECRET))
        destination = seed_views.Codex32EntryView._destination_from_share_collection(seed_views.Codex32EntryView(), collection, 2)
        assert destination.view_args["corrections"] == {}
        assert collection.is_wiped
        seed = self.controller.storage.pending_seed
        assert seed.codex32_master_share == SECRET
        assert seed.codex32_export_shares == {"s": SECRET}
        assert seed.codex32_backup_warning is True
        success = destination.View_cls(**destination.view_args)
        success.run_screen = Mock(return_value=2)
        success.run()
        assert success.run_screen.call_args.kwargs["unverified_correction"] is False

    def test_scan_invalid_input_does_not_start_manual_correction(self):
        view = seed_views.Codex32EntryView(share_data=DAMAGED, auto_submit_share_data=True, entry_method="scan")
        destination = view.run()
        assert destination.view_args["correction_flow"] is None

    def test_backup_confirmation_still_rejects_a_correctable_typo(self):
        parsed = model.parse_codex32_share(SECRET)
        seed = Codex32Seed(parsed.data, codex32_master_share=SECRET)
        view = seed_views.Codex32BackupConfirmEntryView(seed, SECRET)
        view.run_screen = Mock(return_value=SECRET[:17] + "Q" + SECRET[18:])
        assert view.run().View_cls == seed_views.Codex32BackupConfirmInvalidView


class TestFingerprintComparison(BaseTest):
    def recover(self, backup_warning=False):
        seed = Codex32Seed(model.parse_codex32_share(SECRET).data, codex32_master_share=SECRET,
                           codex32_export_shares={"a": SHARE_A, "c": SHARE_C},
                           codex32_share_sources={"a": "entered", "c": "entered"},
                           codex32_backup_warning=backup_warning)
        self.controller.storage.set_pending_seed(seed)
        return seed, {"a": (suggest_correction(DAMAGED), True)}

    def test_all_check_choices_and_back_leave_seed_and_corrections_unchanged(self):
        seed, corrections = self.recover()
        for selection, target in ((0, views.Codex32FingerprintEntryView),
                                  (1, views.Codex32FingerprintVisualView),
                                  (2, views.Codex32FingerprintNoRecordView),
                                  (RET_CODE__BACK_BUTTON, seed_views.Codex32MasterShareSuccessView)):
            view = views.Codex32FingerprintCheckView(corrections)
            view.run_screen = Mock(return_value=selection)
            destination = view.run()
            assert destination.View_cls == target
            assert destination.view_args["corrections"] == corrections
            assert self.controller.storage.pending_seed is seed
            assert corrections["a"][1] is True

    def test_eight_hex_characters_compare_case_insensitively_without_loading_seed(self):
        seed, corrections = self.recover()
        entry = views.Codex32FingerprintEntryView(corrections)
        entry.run_screen = Mock(return_value="FAB6868A")
        destination = entry.run()
        result = destination.View_cls(**destination.view_args)
        result.run_screen = Mock(return_value=1)
        returned = result.run()
        assert result.run_screen.call_args.kwargs["title"] == "Record Matches"
        assert returned.view_args["fingerprint_check"] == ("entered", "fab6868a")
        assert returned.view_args["corrections"] == corrections
        assert self.controller.storage.pending_seed is seed
        assert seed.codex32_share_sources == {"a": "entered", "c": "entered"}
        success = returned.View_cls(**returned.view_args)
        assert returned.view_args["show_options"] is True
        success.run_screen = Mock(return_value=2)
        returned = success.run()
        assert [button.button_label for button in success.run_screen.call_args.kwargs["button_data"]] == [
            "Show Master Seed", "Review Entered Shares", "Return to Fingerprint"]
        assert returned.view_args["fingerprint_check"] == ("entered", "fab6868a")
        fingerprint = returned.View_cls(**returned.view_args)
        fingerprint.run_screen = Mock(return_value=0)
        assert fingerprint.run().View_cls == views.Codex32FingerprintCheckView
        assert fingerprint.run_screen.call_args.kwargs["fingerprint_check"] == "entered"
        assert fingerprint.run_screen.call_args.kwargs["unverified_correction"] is True

    def test_matching_record_can_load_seed_without_losing_backup_provenance(self):
        for kwargs in ({"recorded_fingerprint": "fab6868a"}, {"visual_match": True}):
            seed, corrections = self.recover(backup_warning=True)
            original_sources = seed.codex32_share_sources.copy()
            self.controller.codex32_temp_share = SECRET
            result = views.Codex32FingerprintResultView(corrections, **kwargs)
            result.run_screen = Mock(return_value=0)
            destination = result.run()
            assert [b.button_label for b in result.run_screen.call_args.kwargs["button_data"]] == ["Load Seed", "More Options"]
            assert destination.View_cls == seed_views.SeedFinalizeView
            assert destination.clear_history is True
            assert self.controller.storage.pending_seed is seed
            assert self.controller.codex32_temp_share is None
            assert corrections == {}
            assert seed.codex32_share_sources == original_sources
            assert seed.codex32_backup_warning is True
            assert seed.codex32_export_shares == {"a": SHARE_A, "c": SHARE_C}

    def test_match_more_options_reuses_existing_menu_and_preserves_comparison(self):
        for kwargs, method in (({"recorded_fingerprint": "fab6868a"}, "entered"),
                               ({"visual_match": True}, "visual")):
            for selection, target in ((0, seed_views.Codex32MasterSecretWarningView),
                                      (1, views.Codex32RecoveryReviewView),
                                      (2, seed_views.Codex32MasterShareSuccessView),
                                      (RET_CODE__BACK_BUTTON, seed_views.Codex32MasterShareSuccessView)):
                seed, corrections = self.recover()
                result = views.Codex32FingerprintResultView(corrections, **kwargs)
                result.run_screen = Mock(return_value=1)
                destination = result.run()
                assert destination.view_args["show_options"] is True
                assert destination.view_args["fingerprint_check"] == (method, "fab6868a")
                options = destination.View_cls(**destination.view_args)
                options.run_screen = Mock(return_value=selection)
                returned = options.run()
                assert returned.View_cls == target
                if selection in (2, RET_CODE__BACK_BUTTON):
                    assert returned.view_args["fingerprint_check"] == (method, "fab6868a")
                    assert returned.view_args["corrections"] is corrections
                assert self.controller.storage.pending_seed is seed
                assert corrections["a"][1] is True

    def test_partial_overlong_or_non_hex_entry_cannot_match(self):
        self.recover()
        for entered in ("", "fab6868", "fab6868aa", "fab6868g", None):
            entry = views.Codex32FingerprintEntryView()
            entry.run_screen = Mock(return_value=entered)
            assert entry.run().View_cls == views.Codex32FingerprintEntryView

    def test_mismatch_can_retry_review_or_return_without_a_check_marker(self):
        seed, corrections = self.recover()
        for selected, target in ((0, views.Codex32FingerprintCheckView),
                                 (1, views.Codex32RecoveryReviewView),
                                 (2, seed_views.Codex32MasterShareSuccessView)):
            result = views.Codex32FingerprintResultView(corrections, recorded_fingerprint="fab6868b")
            result.run_screen = Mock(return_value=selected)
            destination = result.run()
            assert result.run_screen.call_args.kwargs["title"] == "Record Mismatch"
            assert "fab6868b" in result.run_screen.call_args.kwargs["text"]
            assert "fab6868a" in result.run_screen.call_args.kwargs["text"]
            assert destination.View_cls == target
            assert not destination.view_args.get("fingerprint_check")
            assert self.controller.storage.pending_seed is seed
            assert corrections["a"][1] is True

    def test_visual_comparison_is_distinguished_and_no_record_stays_unchecked(self):
        seed, corrections = self.recover()
        visual = views.Codex32FingerprintVisualView(corrections)
        visual.run_screen = Mock(return_value=0)
        destination = visual.run()
        result = destination.View_cls(**destination.view_args)
        result.run_screen = Mock(return_value=1)
        assert result.run().view_args["fingerprint_check"] == ("visual", "fab6868a")
        no_record = views.Codex32FingerprintNoRecordView(corrections)
        no_record.run_screen = Mock(return_value=0)
        assert no_record.run().view_args["fingerprint_check"] is None
        assert self.controller.storage.pending_seed is seed
        assert corrections["a"][1] is True

    def test_different_recovered_fingerprint_drops_previous_check_marker(self):
        self.recover()
        view = seed_views.Codex32MasterShareSuccessView(fingerprint_check=("entered", "19c96970"))
        view.run_screen = Mock(return_value=0)
        view.run()
        assert view.run_screen.call_args.kwargs["fingerprint_check"] == ""

    def test_no_pending_seed_returns_home_from_every_fingerprint_view(self):
        for view in (views.Codex32FingerprintCheckView(), views.Codex32FingerprintEntryView(),
                     views.Codex32FingerprintVisualView(), views.Codex32FingerprintResultView(),
                     views.Codex32FingerprintNoRecordView(), seed_views.Codex32MasterShareSuccessView()):
            view.run_screen = Mock(side_effect=AssertionError("No seed to compare"))
            assert view.run().View_cls == MainMenuView

    def test_no_correction_explains_device_limits_and_allows_review_again(self):
        damaged = SHARE_A[:15] + "?" * 14 + SHARE_A[29:]
        entry = seed_views.Codex32EntryView(share_data=damaged, auto_submit_share_data=True)
        destination = entry.run()
        for _ in range(2):
            invalid = destination.View_cls(**destination.view_args)
            invalid.run_screen = Mock(return_value=0)
            edit = invalid.run()
            text = invalid.run_screen.call_args.kwargs["text"]
            assert "may exceed device limits" in text
            assert "too many" not in text.lower() and "corrupted" not in text.lower()
            assert edit.View_cls == seed_views.Codex32EntryView
            assert edit.view_args["share_data"] == damaged
            entry = edit.View_cls(**edit.view_args)
            entry.run_screen = Mock(return_value=damaged)
            destination = entry.run()
        assert self.controller.storage.pending_seed is None

    def test_scan_validation_and_share_set_mismatch_keep_specific_error_messages(self):
        scan = seed_views.Codex32EntryView(share_data=DAMAGED, auto_submit_share_data=True, entry_method="scan")
        destination = scan.run()
        invalid = destination.View_cls(**destination.view_args)
        invalid.run_screen = Mock(return_value=0)
        invalid.run()
        assert "Checksum failure" in invalid.run_screen.call_args.kwargs["text"]
        collection = model.Codex32ShareCollection.from_first_share(model.parse_codex32_share(SHARE_A))
        invalid = seed_views.Codex32ShareInvalidView(share_collection=collection, error_detail="Share header mismatch",
                                                  error_type=model.ERROR_HEADER)
        invalid.run_screen = Mock(return_value=0)
        invalid.run()
        assert "current share set" in invalid.run_screen.call_args.kwargs["text"]

    def test_canceling_check_menu_or_entry_preserves_prior_marker_and_correction_history(self):
        seed, corrections = self.recover()
        for marker in (("entered", "fab6868a"), ("visual", "fab6868a")):
            menu = views.Codex32FingerprintCheckView(corrections, fingerprint_check=marker)
            menu.run_screen = Mock(return_value=RET_CODE__BACK_BUTTON)
            destination = menu.run()
            assert destination.view_args["fingerprint_check"] == marker
            menu.run_screen = Mock(return_value=0)
            destination = menu.run()
            entry = destination.View_cls(**destination.view_args)
            entry.run_screen = Mock(return_value=RET_CODE__BACK_BUTTON)
            destination = entry.run()
            menu = destination.View_cls(**destination.view_args)
            menu.run_screen = Mock(return_value=RET_CODE__BACK_BUTTON)
            assert menu.run().view_args["fingerprint_check"] == marker
            visual = views.Codex32FingerprintVisualView(corrections, fingerprint_check=marker)
            visual.run_screen = Mock(return_value=RET_CODE__BACK_BUTTON)
            destination = visual.run()
            menu = destination.View_cls(**destination.view_args)
            menu.run_screen = Mock(return_value=RET_CODE__BACK_BUTTON)
            assert menu.run().view_args["fingerprint_check"] == marker
        assert self.controller.storage.pending_seed is seed
        assert corrections["a"][1] is True

    def test_mismatch_clears_previous_positive_marker_even_after_back(self):
        self.recover()
        entry = views.Codex32FingerprintEntryView(fingerprint_check=("entered", "fab6868a"))
        entry.run_screen = Mock(return_value="fab6868b")
        destination = entry.run()
        result = destination.View_cls(**destination.view_args)
        result.run_screen = Mock(return_value=RET_CODE__BACK_BUTTON)
        destination = result.run()
        menu = destination.View_cls(**destination.view_args)
        menu.run_screen = Mock(return_value=RET_CODE__BACK_BUTTON)
        assert menu.run().view_args["fingerprint_check"] is None

    def test_valid_checksum_structural_header_error_keeps_specific_numbered_guidance(self):
        from seedsigner.models.codex32_min import CHARSET, ms32_encode
        body = "0" + SHARE_A[4:35].lower()
        raw = ms32_encode([CHARSET.index(c) for c in body]).upper()
        entry = seed_views.Codex32EntryView(share_data=raw, auto_submit_share_data=True)
        with patch("seedsigner.models.codex32_correction.suggest_correction", side_effect=AssertionError("No checksum damage")):
            destination = entry.run()
        invalid = destination.View_cls(**destination.view_args)
        invalid.run_screen = Mock(return_value=0)
        edit = invalid.run()
        assert "Threshold 0 requires share index S" in invalid.run_screen.call_args.kwargs["text"]
        assert "boxes 4 and 9" in invalid.run_screen.call_args.kwargs["text"]
        assert edit.view_args["share_data"] == raw
        assert self.controller.storage.pending_seed is None

    def test_threshold_zero_typo_with_invalid_checksum_still_offers_correction(self):
        raw = SHARE_A[:3] + "0" + SHARE_A[4:]
        entry = seed_views.Codex32EntryView(share_data=raw, auto_submit_share_data=True)
        destination = entry.run()
        assert destination.view_args["correction_flow"].proposal.corrected == SHARE_A
        assert destination.view_args["correction_attempted"] is True


class TestDeviceNavigationRegressions(FlowTest):
    def test_master_back_returns_to_recovery_and_no_record_finalization_is_reachable(self):
        def still_pending(view):
            assert self.controller.storage.pending_seed.codex32_master_share == SECRET
            assert self.controller.codex32_temp_share is None

        self.run_sequence([
            FlowStep(MainMenuView, button_data_selection=MainMenuView.SEEDS),
            FlowStep(seed_views.SeedsMenuView, is_redirect=True),
            FlowStep(seed_views.LoadSeedView, button_data_selection=seed_views.LoadSeedView.TYPE_CODEX32),
            FlowStep(seed_views.Codex32EntryView, screen_return_value=SHARE_A),
            FlowStep(seed_views.Codex32ShareSuccessView, button_data_selection=seed_views.Codex32ShareSuccessView.NEXT),
            FlowStep(seed_views.Codex32EntryView, screen_return_value=SHARE_C),
            FlowStep(seed_views.Codex32MasterShareSuccessView, button_data_selection=seed_views.Codex32MasterShareSuccessView.MORE),
            FlowStep(seed_views.Codex32MasterShareSuccessView, button_data_selection=seed_views.Codex32MasterShareSuccessView.DISPLAY),
            FlowStep(seed_views.Codex32MasterSecretWarningView, screen_return_value=0),
            FlowStep(seed_views.Codex32MasterSecretDisplayView, screen_return_value=0),
            FlowStep(seed_views.Codex32MasterSecretDisplayView, screen_return_value=RET_CODE__BACK_BUTTON),
            FlowStep(seed_views.Codex32MasterSecretDisplayView, screen_return_value=RET_CODE__BACK_BUTTON),
            FlowStep(seed_views.Codex32MasterShareSuccessView, before_run=still_pending, button_data_selection=seed_views.Codex32MasterShareSuccessView.RETURN),
            FlowStep(seed_views.Codex32MasterShareSuccessView, button_data_selection=seed_views.Codex32MasterShareSuccessView.CHECK),
            FlowStep(views.Codex32FingerprintCheckView, button_data_selection=views.Codex32FingerprintCheckView.NO_RECORD),
            FlowStep(views.Codex32FingerprintNoRecordView, screen_return_value=0),
            FlowStep(seed_views.Codex32MasterShareSuccessView, before_run=still_pending, button_data_selection=seed_views.Codex32MasterShareSuccessView.LOAD),
            FlowStep(seed_views.SeedFinalizeView, screen_return_value=0),
            FlowStep(seed_views.SeedOptionsView),
        ])
        assert self.controller.storage.pending_seed is None
        assert self.controller.storage.seeds[0].codex32_master_share == SECRET

    def test_review_of_unknowns_uses_resolution_mode_and_clean_rebuild_clears_repair_status(self):
        damaged = SHARE_A[:15] + "?" * 13 + SHARE_A[28:]
        proposal = suggest_correction(damaged)
        seed = Codex32Seed(model.parse_codex32_share(SECRET).data, codex32_master_share=SECRET,
                           codex32_export_shares={"a": SHARE_A, "c": SHARE_C},
                           codex32_share_sources={"a": "entered", "c": "entered"})
        self.controller.storage.set_pending_seed(seed)
        chooser = views.Codex32RecoveryReviewView({"a": (proposal, True)})
        chooser.run_screen = Mock(return_value=0)
        destination = chooser.run()
        assert destination.view_args["resolve_unknowns"] is True
        entry = destination.View_cls(**destination.view_args)
        entry.run_screen = Mock(return_value=SHARE_A)
        destination = entry.run()
        assert entry.run_screen.call_args.kwargs["resolve_unknowns"] is True
        assert destination.View_cls == seed_views.Codex32MasterShareSuccessView
        assert destination.view_args["corrections"] == {}
        assert destination.view_args.get("fingerprint_check") is None
        assert self.controller.storage.pending_seed.codex32_master_share == SECRET
