from unittest.mock import Mock, patch

from base import BaseTest, FlowStep, FlowTest

from seedsigner.models.settings import Settings, SettingsConstants
from seedsigner.views.view import MainMenuView
from seedsigner.views.anti_exfil_views import (
    AntiExfilFinalizeView,
    AntiExfilModeMismatchView,
    AntiExfilQRDisplayView,
    AntiExfilRequestView,
    AntiExfilResponseReadyView,
    AntiExfilRoundOneCompleteView,
)
from seedsigner.views.scan_views import ScanAntiExfilHostRevealView, ScanView
from seedsigner.views import psbt_views

from test_anti_exfil_protocol import FakeNativeBackend
from test_anti_exfil_state import make_round_one, make_round_two_request


class FakeCompletedDecoder:
    def __init__(self, *, is_anti_exfil=False, is_psbt=False, package=None):
        self.is_complete = True
        self.is_invalid = False
        self.is_anti_exfil = is_anti_exfil
        self.is_psbt = is_psbt
        self.is_seed = False
        self.is_settings = False
        self.is_wallet_descriptor = False
        self.is_address = False
        self.is_sign_message = False
        self.qr_type = "crypto__psbt" if is_psbt else "x_btc__anti_exfil"
        self.package = package

    def get_anti_exfil_package(self, network):
        return self.package


class TestAntiExfilViews(BaseTest):
    def run_scan(self, decoder):
        view = ScanView()
        view.decoder = decoder
        view.run_screen = Mock(return_value=None)
        view.controller.reset_screensaver_timeout = Mock()
        return view.run()

    def test_anti_exfil_qr_is_rejected_while_disabled(self):
        _, _, package = make_round_one()
        destination = self.run_scan(
            FakeCompletedDecoder(is_anti_exfil=True, package=package)
        )
        assert destination.View_cls is AntiExfilModeMismatchView
        assert destination.view_args == {"received_anti_exfil": True}
        assert self.controller.anti_exfil_state is None

    def test_regular_psbt_is_rejected_while_anti_exfil_is_required(self):
        self.settings.set_value(
            SettingsConstants.SETTING__ANTI_EXFIL,
            SettingsConstants.OPTION__REQUIRED,
        )
        destination = self.run_scan(FakeCompletedDecoder(is_psbt=True))
        assert destination.View_cls is AntiExfilModeMismatchView
        assert destination.view_args == {"received_anti_exfil": False}
        assert self.controller.psbt is None

    def test_enabled_anti_exfil_qr_loads_request_state(self):
        self.settings.set_value(
            SettingsConstants.SETTING__ANTI_EXFIL,
            SettingsConstants.OPTION__REQUIRED,
        )
        _, _, package = make_round_one()
        destination = self.run_scan(
            FakeCompletedDecoder(is_anti_exfil=True, package=package)
        )
        assert destination.View_cls is AntiExfilRequestView
        assert self.controller.anti_exfil_state.round_number == 1
        assert self.controller.psbt.serialize() == package.psbt

    def test_host_reveal_shortcut_accepts_only_message_three(self):
        self.settings.set_value(
            SettingsConstants.SETTING__ANTI_EXFIL,
            SettingsConstants.OPTION__REQUIRED,
        )
        _, package = make_round_two_request()
        view = ScanAntiExfilHostRevealView()
        view.decoder = FakeCompletedDecoder(is_anti_exfil=True, package=package)
        view.run_screen = Mock(return_value=None)
        view.controller.reset_screensaver_timeout = Mock()
        destination = view.run()
        assert destination.View_cls is AntiExfilRequestView
        assert self.controller.anti_exfil_state.request_stage.name == "HOST_REVEAL"

    def test_host_reveal_shortcut_rejects_message_one(self):
        self.settings.set_value(
            SettingsConstants.SETTING__ANTI_EXFIL,
            SettingsConstants.OPTION__REQUIRED,
        )
        _, _, package = make_round_one()
        view = ScanAntiExfilHostRevealView()
        view.decoder = FakeCompletedDecoder(is_anti_exfil=True, package=package)
        view.run_screen = Mock(return_value=None)
        view.controller.reset_screensaver_timeout = Mock()
        destination = view.run()
        from seedsigner.views.anti_exfil_views import AntiExfilFailureView

        assert destination.View_cls is AntiExfilFailureView
        assert destination.view_args["error_code"] == "AE_WRONG_STAGE"
        assert "message 3" in destination.view_args["error_message"]

    def test_host_reveal_shortcut_rejects_an_ordinary_psbt_type(self):
        view = ScanAntiExfilHostRevealView()
        view.decoder = FakeCompletedDecoder(is_psbt=True)
        view.run_screen = Mock(return_value=None)
        view.controller.reset_screensaver_timeout = Mock()
        destination = view.run()
        from seedsigner.views.view import ErrorView

        assert destination.View_cls is ErrorView
        assert "Expected anti-exfil host reveal message 3" in destination.view_args["text"]

    def test_round_one_complete_routes_to_scan_or_explicit_exit(self):
        seed, _, package = make_round_one()
        from seedsigner.models.anti_exfil_state import AntiExfilFlowState

        state = AntiExfilFlowState.from_package(package)
        state.create_response(
            seed=seed,
            network=SettingsConstants.REGTEST,
            backend=FakeNativeBackend(),
        )
        self.controller.anti_exfil_state = state

        scan_view = AntiExfilRoundOneCompleteView()
        scan_view.run_screen = Mock(return_value=0)
        destination = scan_view.run()
        assert destination.View_cls is ScanAntiExfilHostRevealView
        assert destination.clear_history

        exit_view = AntiExfilRoundOneCompleteView()
        exit_view.run_screen = Mock(return_value=1)
        destination = exit_view.run()
        assert destination.View_cls is MainMenuView
        assert destination.clear_history

    def test_message_three_remains_scannable_without_round_one_memory(self):
        self.settings.set_value(
            SettingsConstants.SETTING__ANTI_EXFIL,
            SettingsConstants.OPTION__REQUIRED,
        )
        self.controller.anti_exfil_state = None
        _, package = make_round_two_request()
        destination = self.run_scan(
            FakeCompletedDecoder(is_anti_exfil=True, package=package)
        )
        assert destination.View_cls is AntiExfilRequestView
        assert self.controller.anti_exfil_state.request_stage.name == "HOST_REVEAL"

    def test_required_policy_persists_only_with_persistent_settings(self):
        self.settings.set_value(
            SettingsConstants.SETTING__PERSISTENT_SETTINGS,
            SettingsConstants.OPTION__ENABLED,
        )
        self.settings.set_value(
            SettingsConstants.SETTING__ANTI_EXFIL,
            SettingsConstants.OPTION__REQUIRED,
        )
        Settings._instance = None
        restored = Settings.get_instance()
        assert restored.get_value(SettingsConstants.SETTING__ANTI_EXFIL) == SettingsConstants.OPTION__REQUIRED

        restored.set_value(
            SettingsConstants.SETTING__PERSISTENT_SETTINGS,
            SettingsConstants.OPTION__DISABLED,
        )
        restored.set_value(
            SettingsConstants.SETTING__ANTI_EXFIL,
            SettingsConstants.OPTION__REQUIRED,
        )
        Settings._instance = None
        ephemeral = Settings.get_instance()
        assert ephemeral.get_value(SettingsConstants.SETTING__ANTI_EXFIL) == SettingsConstants.OPTION__DISABLED


class TestAntiExfilReviewFlow(FlowTest):
    def test_round_one_complete_scan_cancel_returns_to_main_menu(self):
        seed, _, package = make_round_one()
        from seedsigner.models.anti_exfil_state import AntiExfilFlowState

        state = AntiExfilFlowState.from_package(package)
        state.create_response(
            seed=seed,
            network=SettingsConstants.REGTEST,
            backend=FakeNativeBackend(),
        )
        self.controller.anti_exfil_state = state
        self.run_sequence(
            [
                FlowStep(
                    AntiExfilRoundOneCompleteView,
                    button_data_selection=AntiExfilRoundOneCompleteView.SCAN_HOST_REVEAL,
                ),
                FlowStep(ScanAntiExfilHostRevealView, screen_return_value=None),
                FlowStep(MainMenuView),
            ]
        )

    def test_round_one_review_intercepts_ordinary_signing(self):
        seed, _, package = make_round_one()
        from seedsigner.models.anti_exfil_state import AntiExfilFlowState

        state = AntiExfilFlowState.from_package(package)
        self.settings.set_value(SettingsConstants.SETTING__NETWORK, SettingsConstants.REGTEST)
        self.settings.set_value(
            SettingsConstants.SETTING__ANTI_EXFIL,
            SettingsConstants.OPTION__REQUIRED,
        )
        self.controller.storage.seeds.append(seed)

        def load_request(view):
            view.decoder = FakeCompletedDecoder(is_anti_exfil=True, package=package)

        original_create_response = AntiExfilFlowState.create_response

        def create_with_fake_backend(flow_state, *, seed, network):
            return original_create_response(
                flow_state,
                seed=seed,
                network=network,
                backend=FakeNativeBackend(),
            )

        with patch.object(
            AntiExfilFlowState,
            "create_response",
            autospec=True,
            side_effect=create_with_fake_backend,
        ):
            with patch("embit.psbt.PSBT.sign_with", autospec=True) as ordinary_sign:
                self.run_sequence(
                    [
                        FlowStep(
                            MainMenuView,
                            button_data_selection=MainMenuView.SCAN,
                        ),
                        FlowStep(ScanView, before_run=load_request),
                        FlowStep(
                            AntiExfilRequestView,
                            button_data_selection=AntiExfilRequestView.REVIEW,
                        ),
                        FlowStep(psbt_views.PSBTSelectSeedView, screen_return_value=0),
                        FlowStep(psbt_views.PSBTOverviewView),
                        FlowStep(psbt_views.PSBTNoChangeWarningView),
                        FlowStep(psbt_views.PSBTMathView),
                        FlowStep(psbt_views.PSBTAddressDetailsView, screen_return_value=0),
                        FlowStep(psbt_views.PSBTFinalizeView, is_redirect=True),
                        FlowStep(
                            AntiExfilFinalizeView,
                            button_data_selection=AntiExfilFinalizeView.CREATE_COMMITMENT,
                        ),
                        FlowStep(
                            AntiExfilResponseReadyView,
                            button_data_selection=AntiExfilResponseReadyView.SHOW_QR,
                        ),
                        FlowStep(AntiExfilQRDisplayView),
                        FlowStep(
                            AntiExfilRoundOneCompleteView,
                            button_data_selection=AntiExfilRoundOneCompleteView.EXIT,
                        ),
                        FlowStep(MainMenuView),
                    ]
                )
                ordinary_sign.assert_not_called()
