import pytest

# Must import this before the Controller
from base import BaseTest

from seedsigner.controller import Controller
from seedsigner.models.seed import Seed


class TestController(BaseTest):

    def test_reset_controller(self):
        """ The reset_controller util should completely reset the Controller singleton """
        controller = Controller.get_instance()
        controller.address_explorer_data = "foo"

        BaseTest.reset_controller()
        controller = Controller.get_instance()
        assert controller.address_explorer_data is None


    def test_singleton_init_fails(self):
        """ The Controller should not allow any code to instantiate it via Controller() """
        with pytest.raises(Exception):
            c = Controller()


    def test_handle_exception(reset_controller):
        """ Handle exceptions that get caught by the controller """

        def process_exception_asserting_valid_error(exception_type, exception_msg=None):
            """
            Exceptions caught by the controller are forwarded to the
            UnhandledExceptionView with view_args["error"] being a list
            of three strings, ie: [exception_type, line_info, exception_msg]
            """
            try:
                if exception_msg:
                    raise exception_type(exception_msg)
                else:
                    raise exception_type()
            except Exception as e:
                error = controller.handle_exception(e).view_args["error"]

            # assert that error structure is valid
            assert len(error) == 3
            assert error[0] in str(exception_type)
            assert type(error[1]) == str
            if exception_msg:
                assert exception_msg in error[2]
            else:
                assert error[2] == ""

        # Initialize the controller
        controller = Controller.get_instance()

        exception_tests = [
            # exceptions with an exception_msg
            (Exception, "foo"),
            (KeyError, "key not found"),
            # exceptions without an exception_msg
            (Exception, ""),
            (Exception, None),
        ]
            
        for exception_type, exception_msg in exception_tests:
            process_exception_asserting_valid_error(exception_type, exception_msg)


    def test_singleton_get_instance_preserves_state(self):
        """ Changes to the Controller singleton should be preserved across calls to get_instance() """

        # Initialize the instance and verify that it read the config settings
        controller = Controller.get_instance()
        assert controller.unverified_address is None

        # Change a value in the instance...
        controller.unverified_address = "123abc"

        # ...get a new copy of the instance and confirm change
        controller = Controller.get_instance()
        assert controller.unverified_address == "123abc"


    def test_reset_main_menu_state_wipes_transient_psbt_seed(self):
        controller = Controller.get_instance()
        transient_seed = Seed(mnemonic="obscure bone gas open exotic abuse virus bunker shuffle nasty ship dash".split())
        controller.psbt_seed = transient_seed
        controller.psbt = "dummy_psbt"
        controller.psbt_parser = object()
        controller.resume_main_flow = Controller.FLOW__PSBT

        controller._reset_main_menu_state()

        assert controller.psbt_seed is None
        assert controller.psbt is None
        assert controller.psbt_parser is None
        assert controller.resume_main_flow is None
        assert transient_seed.seed_bytes is None
        assert transient_seed.mnemonic_list == []


    def test_reset_main_menu_state_does_not_wipe_onboard_psbt_seed(self):
        controller = Controller.get_instance()
        onboard_seed = Seed(mnemonic="obscure bone gas open exotic abuse virus bunker shuffle nasty ship dash".split())
        controller.storage.seeds.append(onboard_seed)
        controller.psbt_seed = onboard_seed

        controller._reset_main_menu_state()

        assert controller.psbt_seed is None
        assert onboard_seed.seed_bytes is not None
        assert len(onboard_seed.mnemonic_list) == 12
