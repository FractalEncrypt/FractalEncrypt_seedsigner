"""Exercise security-relevant numbered-box confirmation on a real PIL canvas."""

import pytest

from threading import RLock
from unittest.mock import MagicMock, patch

from PIL import Image, ImageDraw, ImageColor
from base import BaseTest
from seedsigner.gui.renderer import Renderer
from seedsigner.gui.keyboard import Keyboard
from seedsigner.gui.screens.seed_screens import Codex32EntryScreen, Codex32MasterSecretDisplayScreen, Codex32MasterShareSuccessScreen, Codex32FingerprintEntryScreen, Codex32FingerprintResultScreen, Codex32StatusScreen
from seedsigner.gui.screens.screen import ButtonOption
from seedsigner.gui.components import GUIConstants
from seedsigner.hardware.buttons import HardwareButtonsConstants as Keys

SHARE = "MS12NAMEA320ZYXWVUTSRQPNMLKJHGFEDCAXRPP870HKKQRM"


class TestCorrectionEntryScreen(BaseTest):
    def build_screen(self, screen_cls=Codex32EntryScreen, **kwargs):
        renderer = MagicMock()
        renderer.canvas_width = renderer.canvas_height = 240
        renderer.canvas = Image.new("RGB", (240, 240))
        renderer.draw = ImageDraw.Draw(renderer.canvas)
        renderer.lock = RLock()
        self.renderer_patch = patch.object(Renderer, "get_instance", return_value=renderer)
        self.renderer_patch.start()
        screen = screen_cls(**kwargs)
        screen.is_input_in_top_nav = False
        screen.focus_area = "keyboard"
        return screen

    def test_adjacent_starred_two_digit_labels_fit_their_grid_cells(self):
        screen = self.build_screen(Codex32MasterSecretDisplayScreen, share_data=SHARE,
                                   highlight_indices=tuple(range(14, 24)), button_data=[ButtonOption("Next")])
        with patch.object(screen.image_draw, "text", wraps=screen.image_draw.text) as draw_text:
            screen._render_boxes()
        labels = [call for call in draw_text.call_args_list if len(call.args) > 1
                  and isinstance(call.args[1], str) and call.args[1].endswith("*")]
        assert len(labels) == 10
        for call in labels:
            assert call.kwargs["font"].getlength(call.args[1]) <= screen.box_width

    def test_unverified_fingerprint_guidance_renders_in_warning_color(self):
        screen = self.build_screen(Codex32MasterShareSuccessScreen, fingerprint="FAB6868A",
                                   unverified_correction=True, button_data=[ButtonOption("Load Seed")])
        screen._render()
        guide = screen.components[-1]
        region = screen.canvas.crop((0, guide.screen_y, 240, guide.screen_y + guide.height))
        # Supersampling can blend every edge pixel; test the rendered yellow ink.
        expected = ImageColor.getrgb(GUIConstants.WARNING_COLOR)
        assert any(max(abs(channel - target) for channel, target in zip(pixel, expected)) < 25
                   for pixel in region.getdata())

    def teardown_method(self):
        if hasattr(self, "renderer_patch"):
            self.renderer_patch.stop()
        super().teardown_method()

    def test_only_changed_boxes_clear_and_arrow_goes_to_next_affected_group(self):
        screen = self.build_screen(share_data=SHARE, reentry_indices=(17, 33), allow_unknown=False)
        assert [i for i, value in enumerate(screen.values) if not value] == [17, 33]
        assert screen.review_mode is False
        screen.hw_inputs = MagicMock()
        screen.hw_inputs.wait_for.side_effect = [Keys.KEY_PRESS, Keys.KEY_RIGHT, Keys.KEY_PRESS, Keys.KEY2]
        screen.keyboard.update_from_input = MagicMock(side_effect=[SHARE[17], SHARE[33], Keyboard.KEY_OK["code"]])
        assert screen._run() == SHARE
        assert screen.active_page == 8
        assert screen.keyboard.get_selected_key().is_selected is True
        assert "?" not in screen.allowed_chars

    def test_proof_waits_at_arrow_and_skips_unchanged_groups(self):
        screen = self.build_screen(share_data=SHARE, reentry_indices=(17, 33), allow_unknown=False)
        screen.hw_inputs = MagicMock()
        inputs = iter([Keys.KEY_PRESS, Keys.KEY_RIGHT, Keys.KEY_PRESS, Keys.KEY2])

        def next_input(*args):
            value = next(inputs)
            if value == Keys.KEY_RIGHT:
                assert screen.active_page == 4
                assert screen.focus_area == "right_arrow"
                assert screen.values[33] == ""
            return value

        screen.hw_inputs.wait_for.side_effect = next_input
        screen.keyboard.update_from_input = MagicMock(side_effect=[SHARE[17], SHARE[33], Keyboard.KEY_OK["code"]])
        assert screen._run() == SHARE
        assert screen.active_page == 8
        screen._go_prev_page()
        assert screen.active_page == 4

    def test_confirmation_cannot_overwrite_an_unchanged_box(self):
        screen = self.build_screen(share_data=SHARE, reentry_indices=(17,), allow_unknown=False)
        screen.cursor_index = 16
        screen.hw_inputs = MagicMock()
        screen.hw_inputs.wait_for.side_effect = [Keys.KEY_PRESS, Keys.KEY_PRESS, Keys.KEY2]
        screen.keyboard.update_from_input = MagicMock(side_effect=["Q", SHARE[17], Keyboard.KEY_OK["code"]])

        def warning(*args):
            screen.cursor_index = 17

        screen._flash_warning = MagicMock(side_effect=warning)
        assert screen._run() == SHARE
        assert screen.values[16] == SHARE[16]

    def test_left_arrow_revisits_previous_correction_and_right_returns_to_next(self):
        screen = self.build_screen(share_data=SHARE, reentry_indices=(17, 25, 41), allow_unknown=False)
        screen.hw_inputs = MagicMock()
        inputs = iter([Keys.KEY_PRESS, Keys.KEY_RIGHT, Keys.KEY_PRESS, Keys.KEY_RIGHT,
                       Keys.KEY_UP, Keys.KEY_PRESS, Keys.KEY3, Keys.KEY_PRESS, Keys.KEY2])
        visits = []

        def next_input(*args):
            value = next(inputs)
            if value == Keys.KEY_UP:
                assert screen.active_page == 10
            if value == Keys.KEY_PRESS and screen.focus_area == "left_arrow":
                assert screen.active_page == 10
                visits.append(screen.active_page)
            if value == Keys.KEY3:
                assert screen.active_page == 6
                assert screen.values[25] == SHARE[25]
                visits.append(screen.active_page)
            return value

        screen.hw_inputs.wait_for.side_effect = next_input
        screen.keyboard.update_from_input = MagicMock(side_effect=[SHARE[17], SHARE[25], SHARE[41], Keyboard.KEY_OK["code"]])
        assert screen._run() == SHARE
        assert visits == [10, 6]
        assert screen.active_page == 10

    def test_unknown_threshold_is_allowed_and_explained_on_first_use(self):
        screen = self.build_screen()
        screen.hw_inputs = MagicMock()
        screen.hw_inputs.wait_for.side_effect = [Keys.KEY_PRESS, Keys.KEY_DOWN, Keys.KEY2]
        screen.keyboard.update_from_input = MagicMock(side_effect=["?", "A", Keyboard.KEY_OK["code"]])
        screen.values = list(SHARE)
        screen.values[3] = ""
        screen.cursor_index = 3
        returned = screen._run()
        assert returned[3] == "?"
        assert screen.unknown_hint_shown is True

    def test_fingerprint_is_lowercase_and_three_buttons_leave_guidance_room(self):
        with patch("seedsigner.gui.screens.seed_screens.IconTextLine", wraps=__import__(
                "seedsigner.gui.screens.seed_screens", fromlist=["IconTextLine"]).IconTextLine) as line:
            screen = self.build_screen(Codex32MasterShareSuccessScreen, fingerprint="FAB6868A",
                                       button_data=[ButtonOption("Check Fingerprint"), ButtonOption("Load Seed"), ButtonOption("More Options")])
            assert line.call_args.kwargs["value_text"] == "fab6868a"
        guide = screen.components[-1]
        assert guide.screen_y + guide.height < screen.buttons[0].screen_y
        assert guide.height > 0
        screen._render()

    def test_fingerprint_keyboard_backspace_and_exact_eighth_character_submission(self):
        screen = self.build_screen(Codex32FingerprintEntryScreen)
        screen.hw_inputs = MagicMock()
        screen.hw_inputs.wait_for.side_effect = [Keys.KEY1, Keys.KEY2, Keys.KEY3, Keys.KEY_PRESS, Keys.KEY2, Keys.KEY3, Keys.KEY1, Keys.KEY2, Keys.KEY3, Keys.KEY_PRESS]
        screen.keyboard.update_from_input = MagicMock(side_effect=list("fab0") + [Keyboard.KEY_BACKSPACE["code"]] + list("6868a"))
        clicks = [Keys.KEY_PRESS, Keys.KEY1, Keys.KEY2, Keys.KEY3]
        with patch.object(Keys, "KEYS__ANYCLICK", clicks), patch.object(Keys, "KEYS__LEFT_RIGHT_UP_DOWN", []):
            assert screen._run() == "fab6868a"
        assert screen.hw_inputs.wait_for.call_args.args[0] == clicks
        assert all(call.args[0] == Keys.KEY_PRESS for call in screen.keyboard.update_from_input.call_args_list)
        assert screen.hw_inputs.wait_for.call_count == 10
        assert screen.keys_charset == "0123456789abcdef"
        assert screen.show_save_button is False

    def test_fingerprint_keyboard_back_exits_without_a_partial_comparison(self):
        screen = self.build_screen(Codex32FingerprintEntryScreen)
        screen.hw_inputs = MagicMock()
        screen.hw_inputs.wait_for.return_value = Keys.KEY_PRESS
        screen.top_nav.is_selected = True
        from seedsigner.gui.screens.screen import RET_CODE__BACK_BUTTON
        assert screen._run() == RET_CODE__BACK_BUTTON

    def test_fingerprint_guidance_and_navigation_fit_the_panel(self):
        from seedsigner.gui.screens.seed_screens import Codex32MessageScreen
        from seedsigner.models.seed import Codex32Seed
        from seedsigner.models.codex32 import parse_codex32_share
        from seedsigner.views import codex32_views as views, seed_views
        secret = "MS12NAMES6XQGUZTTXKEQNJSJZV4JV3NZ5K3KWGSPHUH6EVW"
        self.controller.storage.set_pending_seed(Codex32Seed(parse_codex32_share(secret).data, codex32_master_share=secret))
        cases = [views.Codex32FingerprintCheckView(), views.Codex32FingerprintVisualView(),
                 views.Codex32FingerprintResultView(recorded_fingerprint="fab6868a"),
                 views.Codex32FingerprintResultView(recorded_fingerprint="fab6868b"),
                 views.Codex32FingerprintResultView(visual_match=False),
                 views.Codex32FingerprintNoRecordView(),
                 seed_views.Codex32ShareInvalidView(correction_attempted=True),
                 seed_views.Codex32ShareInvalidView(error_detail="Codex32 share index must be 's' when threshold is 0")]
        for view in cases:
            def render(cls, **kwargs):
                screen = self.build_screen(cls, **kwargs)
                screen._render()
                assert screen.top_nav.title.needs_scroll is False
                if cls in (Codex32MessageScreen, Codex32FingerprintResultScreen, Codex32StatusScreen):
                    area = screen.components[-1]
                    lines = len(area.text_lines)
                    text_height = area.text_height_above_baseline * lines + area.line_spacing * (lines - 1)
                    text_height += area.text_lines[-1].get("px_below_baseline", 0)
                    assert text_height <= area.height
                    assert area.screen_y + area.height < screen.buttons[0].screen_y
                self.renderer_patch.stop()
                return 0
            view.run_screen = render
            view.run()

    def test_repair_caveat_remains_visible_beside_typed_and_visual_checks(self):
        for check in ("", "entered", "visual"):
            screen = self.build_screen(Codex32MasterShareSuccessScreen, fingerprint="fab6868a",
                                       unverified_correction=True, corrected_share=True,
                                       fingerprint_check=check, button_data=[ButtonOption("Check Fingerprint"),
                                       ButtonOption("Load Seed"), ButtonOption("More Options")])
            area = screen.components[-1]
            assert "Share repairs unverified." in area.text
            assert {"": "Compare saved fingerprint.", "entered": "Saved fingerprint matches.",
                    "visual": "Compared visually."}[check] in area.text
            lines = len(area.text_lines)
            height = area.text_height_above_baseline * lines + area.line_spacing * (lines - 1)
            height += area.text_lines[-1].get("px_below_baseline", 0)
            assert height <= area.height
            assert area.screen_y + area.height < screen.buttons[0].screen_y
            fingerprint = screen.components[-2]
            assert fingerprint.screen_y + fingerprint.height <= area.screen_y
            screen._render()
            self.renderer_patch.stop()

    def test_confirmed_transcription_correction_is_distinct_from_unverified_repairs(self):
        screen = self.build_screen(Codex32MasterShareSuccessScreen, fingerprint="fab6868a", corrected_share=True,
                                   button_data=[ButtonOption("Check Fingerprint"), ButtonOption("Load Seed"), ButtonOption("More Options")])
        assert "Share entry corrected." in screen.components[-1].text
        assert "unverified" not in screen.components[-1].text

    def test_rebuild_resolves_sixteen_unknowns_without_premature_ok_or_skipped_boxes(self):
        unknowns = tuple(range(15, 31))
        damaged = list(SHARE)
        for index in unknowns:
            damaged[index] = "?"
        screen = self.build_screen(share_data="".join(damaged), resolve_unknowns=True)
        assert screen.cursor_index == 15 and screen.active_page == 3
        assert "?" not in screen.allowed_chars
        screen.hw_inputs = MagicMock()
        screen.keyboard.update_from_input = MagicMock(side_effect=[Keyboard.KEY_OK["code"]] + [SHARE[i] for i in unknowns] + [Keyboard.KEY_OK["code"]])
        visits = []

        def next_input(*args):
            remaining = [i for i in unknowns if screen.values[i] == "?"]
            ok = next(key for row in screen.keyboard.keys for key in row if key.code == Keyboard.KEY_OK["code"])
            if remaining:
                assert not screen._is_entry_complete()
                if screen.focus_area == "right_arrow":
                    return Keys.KEY_RIGHT
                assert screen.cursor_index == remaining[0]
                assert screen.keyboard.get_selected_key().code != Keyboard.KEY_OK["code"]
                visits.append(screen.cursor_index)
                return Keys.KEY_PRESS
            assert ok.is_active
            assert screen.canvas.getpixel((ok.screen_x + 5, ok.screen_y + 5)) == ImageColor.getrgb(GUIConstants.ACCENT_COLOR)
            assert screen.keyboard.get_selected_key().code == Keyboard.KEY_OK["code"]
            return Keys.KEY2

        screen.hw_inputs.wait_for.side_effect = next_input
        assert screen._run() == SHARE
        assert visits == [15] + list(unknowns)
        assert screen.hw_inputs.wait_for.call_count > 16
        screen._go_prev_page()
        assert screen.active_page == 6 and screen.cursor_index == 24
        screen._go_next_page()
        assert screen.active_page == 7 and screen.cursor_index == 28

    def test_regular_entry_still_accepts_unknowns_for_correction(self):
        damaged = list(SHARE); damaged[17] = "?"
        screen = self.build_screen(share_data="".join(damaged))
        assert screen._is_entry_complete() and screen._is_page_complete()
        assert "?" in screen.allowed_chars

    def test_fingerprint_results_use_standard_colored_status_icons_and_fit(self):
        from seedsigner.gui.components import SeedSignerIconConstants
        for matched, text, buttons in [
            (True, "32-bit fingerprint match. Share repairs unverified. Check wallet policy and a known address.", [ButtonOption("Load Seed"), ButtonOption("More Options")]),
            (False, "Record: fab6868b\nSeed: fab6868a\nReview shares.", [ButtonOption("Try Again"), ButtonOption("Review Entered Shares"), ButtonOption("Return to Fingerprint")]),
        ]:
            screen = self.build_screen(Codex32FingerprintResultScreen, title="Record Matches" if matched else "Record Mismatch", text=text, matched=matched, unverified_correction=True, button_data=buttons)
            icon, area = screen.components[-2:]
            assert icon.icon_name == (SeedSignerIconConstants.SUCCESS if matched else SeedSignerIconConstants.ERROR)
            assert icon.icon_color == (GUIConstants.SUCCESS_COLOR if matched else GUIConstants.ERROR_COLOR)
            assert icon.screen_y + icon.height < screen.buttons[0].screen_y
            assert icon.screen_x + icon.width <= area.screen_x
            lines = len(area.text_lines)
            height = area.text_height_above_baseline * lines + area.line_spacing * (lines - 1) + area.text_lines[-1].get("px_below_baseline", 0)
            assert height <= area.height
            screen._render()
            self.renderer_patch.stop()


    def test_master_display_has_a_real_back_control_on_both_pages(self):
        for start in (0, 24):
            screen = self.build_screen(Codex32MasterSecretDisplayScreen, share_data=SHARE,
                                       start_index=start, display_back_button=True,
                                       button_data=[ButtonOption("Continue" if not start else "Finalize Seed")])
            assert screen.show_back_button and screen.top_nav.show_back_button
            screen._render()
            self.renderer_patch.stop()

    def test_fingerprint_side_button_can_activate_back_without_partial_submission(self):
        screen = self.build_screen(Codex32FingerprintEntryScreen)
        screen.user_input = "fab"
        screen.hw_inputs = MagicMock()
        screen.hw_inputs.wait_for.return_value = Keys.KEY2
        screen.top_nav.is_selected = True
        with patch.object(Keys, "KEYS__ANYCLICK", [Keys.KEY_PRESS, Keys.KEY1, Keys.KEY2, Keys.KEY3]):
            from seedsigner.gui.screens.screen import RET_CODE__BACK_BUTTON
            assert screen._run() == RET_CODE__BACK_BUTTON
        assert screen.user_input == "fab"

    def test_other_keyboards_keep_the_existing_save_button_behavior(self):
        from seedsigner.gui.screens.screen import KeyboardScreen
        screen = self.build_screen(KeyboardScreen, rows=4, cols=5, keys_charset="0123456789abcdef",
                                   show_save_button=True, custom_additional_keys=[Keyboard.KEY_BACKSPACE])
        screen.hw_inputs = MagicMock()
        screen.hw_inputs.wait_for.side_effect = [Keys.KEY_PRESS, Keys.KEY3]
        screen.keyboard.update_from_input = MagicMock(return_value="f")
        with patch.object(Keys, "KEYS__LEFT_RIGHT_UP_DOWN", []):
            assert screen._run() == "f"
        assert screen.hw_inputs.wait_for.call_args.args[0] == [Keys.KEY_PRESS, Keys.KEY3]
        assert screen.keyboard.update_from_input.call_count == 1


    def test_review_edits_known_and_unknown_boxes_without_repeated_ok_jumps(self):
        for unknown in (False, True):
            damaged = list(SHARE)
            damaged[17:19] = ["?", "?"] if unknown else ["A", "A"]
            screen = self.build_screen(share_data="".join(damaged), start_page=4)
            screen.cursor_index = 17
            screen.hw_inputs = MagicMock()
            screen.keyboard.update_from_input = MagicMock(side_effect=[SHARE[17], SHARE[18], Keyboard.KEY_OK["code"]])
            inputs = 0

            def next_input(*args):
                nonlocal inputs
                if inputs:
                    assert screen.focus_area == "keyboard"
                    assert screen.cursor_index == 17 + inputs
                    assert screen.keyboard.get_selected_key().code != Keyboard.KEY_OK["code"]
                inputs += 1
                return Keys.KEY_PRESS

            screen.hw_inputs.wait_for.side_effect = next_input
            assert screen._run() == SHARE
            assert inputs == 3
            self.renderer_patch.stop()

    def test_failure_status_has_large_red_x_clear_limits_and_all_existing_actions(self):
        from seedsigner.views import seed_views
        from seedsigner.gui.components import SeedSignerIconConstants
        view = seed_views.Codex32ShareInvalidView(correction_attempted=True)

        def render(cls, **kwargs):
            screen = self.build_screen(cls, **kwargs)
            assert cls is Codex32StatusScreen
            assert len(screen.buttons) == 3
            icon, area = screen.components[-2:]
            assert icon.icon_name == SeedSignerIconConstants.ERROR
            assert icon.icon_color == GUIConstants.ERROR_COLOR
            assert icon.icon_size == 64
            assert "may exceed device limits" in area.text
            assert "numbered backup boxes" in area.text
            lines = len(area.text_lines)
            height = area.text_height_above_baseline * lines + area.line_spacing * (lines - 1) + area.text_lines[-1].get("px_below_baseline", 0)
            assert height <= area.height
            assert area.screen_y + area.height < screen.buttons[0].screen_y
            assert icon.screen_y + icon.height < screen.buttons[0].screen_y
            screen._render()
            return 0

        view.run_screen = render
        assert view.run().View_cls is seed_views.Codex32EntryView


    @pytest.mark.parametrize("locale", ["en", "ja", "ko", "zh_Hans_CN", "th", "ar"])
    def test_recovered_guidance_fits_locale_fonts_without_overlapping_fingerprint_or_buttons(self, locale):
        from seedsigner.models.settings_definition import SettingsConstants
        self.settings.set_value(SettingsConstants.SETTING__LOCALE, locale)
        for unverified in (False, True):
            for check in ("", "entered", "visual"):
                screen = self.build_screen(Codex32MasterShareSuccessScreen, fingerprint="fab6868a",
                                           corrected_share=True, unverified_correction=unverified,
                                           fingerprint_check=check, button_data=[ButtonOption("Check Fingerprint"),
                                           ButtonOption("Load Seed"), ButtonOption("More Options")])
                fingerprint, guide = screen.components[-2:]
                lines = len(guide.text_lines)
                height = guide.text_height_above_baseline * lines + guide.line_spacing * (lines - 1) + guide.text_lines[-1].get("px_below_baseline", 0)
                assert fingerprint.screen_y >= screen.top_nav.height
                assert fingerprint.screen_y + fingerprint.height <= guide.screen_y
                assert height <= guide.height
                assert guide.screen_y + guide.height < screen.buttons[0].screen_y
                screen._render()
                self.renderer_patch.stop()

    def test_side_button_selection_preserves_key3_save_when_both_options_are_enabled(self):
        from seedsigner.gui.screens.screen import KeyboardScreen
        screen = self.build_screen(KeyboardScreen, rows=4, cols=5, keys_charset="0123456789abcdef",
                                   show_save_button=True, any_button_selects=True,
                                   custom_additional_keys=[Keyboard.KEY_BACKSPACE])
        screen.hw_inputs = MagicMock()
        screen.hw_inputs.wait_for.side_effect = [Keys.KEY1, Keys.KEY2, Keys.KEY3]
        screen.keyboard.update_from_input = MagicMock(side_effect=["f", "a"])
        with patch.object(Keys, "KEYS__ANYCLICK", [Keys.KEY_PRESS, Keys.KEY1, Keys.KEY2, Keys.KEY3]):
            assert screen._run() == "fa"
        assert screen.keyboard.update_from_input.call_count == 2
        assert screen.save_button.is_selected
