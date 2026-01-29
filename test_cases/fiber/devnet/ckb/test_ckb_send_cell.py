"""
Test cases for CKB send_cell / shutdown_channel: open channel, force shutdown, verify tx pool.
"""
from framework.basic_fiber import FiberTest
from framework.constants import Amount


class TestCkbSendCell(FiberTest):
    """
    Test CKB send_cell flow via shutdown_channel: open channel with zero remote balance,
    force shutdown channel, wait for shutdown tx in pool.
    """

    def test_send_cell(self):
        """
        Open channel (fiber1 balance 1000 CKB, fiber2 balance 0), then force shutdown and wait for tx.
        Step 1: Open channel between fiber1 and fiber2.
        Step 2: Force shutdown the channel.
        Step 3: Wait for shutdown tx in pool.
        """
        # Step 1: Open channel between fiber1 and fiber2
        self.open_channel(
            self.fiber1, self.fiber2,
            Amount.ckb(1000),
            0,
        )
        # Step 2: Force shutdown the channel
        self.fiber1.get_client().shutdown_channel(
            {
                "channel_id": self.fiber1.get_client().list_channels({})["channels"][0][
                    "channel_id"
                ],
                "force": True,
            }
        )
        # Step 3: Wait for shutdown tx in pool
        self.wait_and_check_tx_pool_fee(1000, False)
