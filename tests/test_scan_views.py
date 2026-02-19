from unittest.mock import MagicMock

from base import BaseTest
from seedsigner.views import scan_views
from seedsigner.views.view import BackStackView, ErrorView


class TestScanViews(BaseTest):
    def test_scan_seedqr_non_s_error_copy_is_locked(self):
        non_s_share = "ms12namea320zyxwvutsrqpnmlkjhgfedcaxrpp870hkkqrm"

        view = scan_views.ScanSeedQRView()
        view.run_screen = MagicMock(return_value=None)
        view.decoder.add_data(non_s_share)

        destination = view.run()

        assert destination.View_cls == ErrorView
        assert destination.view_args["title"] == "Error"
        assert destination.view_args["status_headline"] == "Non-S Share Not Supported"
        assert destination.view_args["text"] == "This QR is a Codex32 split share. SeedSigner MVP can only scan S-shares. Use Codex32 multi-share recovery to combine shares and recover the S-share."
        assert destination.view_args["button_text"] == "Back"

        next_destination = destination.view_args["next_destination"]
        assert next_destination.View_cls == BackStackView
        assert next_destination.skip_current_view is True
