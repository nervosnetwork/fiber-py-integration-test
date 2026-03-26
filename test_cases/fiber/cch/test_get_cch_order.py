import pytest

from framework.basic_fiber_with_cch import FiberCchTest


class TestGetCchOrder(FiberCchTest):

    def test_get_cch_order_not_exist(self):
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().get_cch_order(
                {"payment_hash": self.generate_random_preimage()}
            )
        expected_error_message = "Key not found"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )
