"""
Test cases for Fiber node startup with wrong password.
Verifies that node_info fails when started with wrong password and succeeds after correct password.
"""
import pytest

from framework.basic_fiber import FiberTest


class TestFiberWrongPassword(FiberTest):
    """
    Test Fiber node behavior when started with wrong password.
    Expect: node_info times out or fails with wrong password; succeeds after restart with correct password.
    """

    def test_wrong_password_then_correct(self):
        """
        Restart fiber with wrong password then correct password.
        Step 1: Stop fiber and start with wrong password.
        Step 2: Call node_info, expect request time out or failure.
        Step 3: Start fiber with correct password and verify node_info succeeds.
        """
        # Step 1: Stop fiber and start with wrong password
        self.fiber1.stop()
        self.fiber1.start("password1")

        # Step 2: Call node_info, expect request time out or failure
        with pytest.raises(Exception) as exc_info:
            self.fiber1.client.try_count = 20
            self.fiber1.get_client().node_info()
        expected_error_message = "request time out"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        # Step 3: Start fiber with correct password and verify node_info succeeds
        self.fiber1.start("password0")
        self.fiber1.get_client().node_info()
