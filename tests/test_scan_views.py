from unittest.mock import MagicMock

from base import BaseTest
from seedsigner.models import codex32 as codex32_model
from seedsigner.views import scan_views
from seedsigner.views import seed_views


class TestScanViews(BaseTest):
    def test_scan_seedqr_non_s_routes_to_codex32_entry_collection(self):
        non_s_share = "ms12namea320zyxwvutsrqpnmlkjhgfedcaxrpp870hkkqrm"

        view = scan_views.ScanSeedQRView()
        view.run_screen = MagicMock(return_value=None)
        view.decoder.add_data(non_s_share)

        destination = view.run()

        assert destination.View_cls == seed_views.Codex32EntryView
        assert destination.view_args["share_num"] == 1
        assert destination.view_args["prefill"] == codex32_model.CODEX32_QR_CANONICAL_PREFIX
        assert destination.view_args["share_data"] == codex32_model.normalize_codex32_display(non_s_share)


    def test_scan_codex32_collection_routes_non_s_share_to_entry(self):
        existing_share = codex32_model.parse_codex32_share("MS12NAMEA320ZYXWVUTSRQPNMLKJHGFEDCAXRPP870HKKQRM")
        share_collection = codex32_model.Codex32ShareCollection.from_first_share(existing_share)
        scanned_share = codex32_model.Codex32String.interpolate_at(
            [
                existing_share,
                codex32_model.parse_codex32_share("MS12NAMES6XQGUZTTXKEQNJSJZV4JV3NZ5K3KWGSPHUH6EVW"),
            ],
            target="c",
        ).s

        view = scan_views.ScanCodex32ShareView(share_num=2, share_collection=share_collection)
        view.run_screen = MagicMock(return_value=None)
        view.decoder.add_data(scanned_share)

        destination = view.run()

        assert destination.View_cls == seed_views.Codex32EntryView
        assert destination.view_args["share_num"] == 2
        assert destination.view_args["share_data"] == scanned_share
        assert destination.view_args["share_collection"] is share_collection
