"""
update_channel tests: tlc_minimum_value (1 CKB, below-min payment fails, max hex, overflow reject).
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout

# u128 max hex string used in graph assertion
TLC_MIN_U128_MAX_HEX = "0xffffffffffffffffffffffffffffffff"


class TestTlcMinimumValue(FiberTest):
    """
    Test update_channel tlc_minimum_value: set 1 CKB then payment below min fails with 'no path found';
    set max u128 hex; assert graph; overflow hex rejects with 'Invalid params'.
    """

    def test_01(self):
        """
        Set tlc_minimum_value to 1 CKB; payment below 1 CKB fails (no path); set tlc_minimum_value to u128 max; assert graph; overflow rejects.
        Step 1: Open F1-F2, send 1 CKB each way; update_channel tlc_minimum_value 1 CKB.
        Step 2: F2->F1 payment (1 CKB - 1) then F1->F2 (1 CKB - 1); expect F1->F2 'no path found'.
        Step 3: Update tlc_minimum_value to u128 max hex; assert graph_channels shows value.
        Step 4: update_channel tlc_minimum_value overflow hex; expect 'Invalid params'.
        """
        # Step 1: Open F1-F2, send 1 CKB each way; update_channel tlc_minimum_value 1 CKB
        bal = Amount.ckb(1000)
        self.open_channel(self.fiber1, self.fiber2, bal, bal)
        amt_1_ckb = Amount.ckb(1)
        self.send_payment(self.fiber1, self.fiber2, amt_1_ckb, wait=True)
        self.send_payment(self.fiber2, self.fiber1, amt_1_ckb, wait=True)
        client = self.fiber1.get_client()
        ch_id = client.list_channels({})["channels"][0]["channel_id"]
        client.update_channel(
            {"channel_id": ch_id, "tlc_minimum_value": hex(amt_1_ckb)}
        )
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 2: F2->F1 payment (1 CKB - 1); then F1->F2 (1 CKB - 1) expect 'no path found'
        self.send_payment(self.fiber2, self.fiber1, amt_1_ckb - 1, wait=True)
        with pytest.raises(Exception) as exc_info:
            self.send_payment(self.fiber1, self.fiber2, amt_1_ckb - 1, wait=True)
        expected = "no path found"
        assert expected in exc_info.value.args[0], (
            f"Expected '{expected}' not found in '{exc_info.value.args[0]}'"
        )

        # Step 3: Update tlc_minimum_value to u128 max hex; assert graph_channels
        client.update_channel(
            {"channel_id": client.list_channels({})["channels"][0]["channel_id"], "tlc_minimum_value": TLC_MIN_U128_MAX_HEX}
        )
        time.sleep(Timeout.POLL_INTERVAL)
        graph_channels = client.graph_channels({})
        node2_val = graph_channels["channels"][0]["update_info_of_node2"].get("tlc_minimum_value")
        node1_val = graph_channels["channels"][0]["update_info_of_node1"].get("tlc_minimum_value")
        assert (
            node2_val == TLC_MIN_U128_MAX_HEX or node1_val == TLC_MIN_U128_MAX_HEX
        ), f"Expected {TLC_MIN_U128_MAX_HEX} in update_info, got node2={node2_val}, node1={node1_val}"

        # Step 4: update_channel tlc_minimum_value overflow hex; expect 'Invalid params'
        with pytest.raises(Exception) as exc_info:
            client.update_channel(
                {
                    "channel_id": client.list_channels({})["channels"][0]["channel_id"],
                    "tlc_minimum_value": "0xfffffffffffffffffffffffffffffffff",
                }
            )
        assert "Invalid params" in exc_info.value.args[0], (
            f"Expected 'Invalid params' not found in '{exc_info.value.args[0]}'"
        )
