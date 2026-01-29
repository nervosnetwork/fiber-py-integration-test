"""
Test cases for send_payment using multiple channels between two nodes.
Verifies that payments can utilize multiple channels between the same pair.
"""
from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout


class TestMutilChannel(FiberTest):
    """
    Test send_payment when multiple channels exist between two nodes.
    Verifies that payments utilize more than one channel.
    """

    def test_mutil_channel(self):
        """
        Test that payments use multiple channels when available.
        Step 1: Open 5 channels between fiber1 and fiber2.
        Step 2: Send 20 payments from fiber1 to fiber2.
        Step 3: Wait for all payments to complete.
        Step 4: Assert that more than one channel was used (remote_balance increased).
        """
        # Step 1: Open 5 channels between fiber1 and fiber2
        open_channel_size = 5
        send_payment_size = 20
        for _ in range(open_channel_size):
            self.open_channel(
                self.fiber1, self.fiber2,
                Amount.ckb(1000), Amount.ckb(1)
            )

        # Step 2: Send 20 payments from fiber1 to fiber2
        payment_list = []
        before_channels = self.fiber1.get_client().list_channels({})
        for _ in range(send_payment_size):
            payment_list.append(
                self.send_payment(
                    self.fiber1, self.fiber2,
                    Amount.ckb(1), wait=False
                )
            )

        # Step 3: Wait for all payments to complete
        for payment_hash in payment_list:
            self.wait_payment_finished(
                self.fiber1, payment_hash,
                timeout=Timeout.CHANNEL_READY
            )

        # Step 4: Assert that more than one channel was used
        channels = self.fiber1.get_client().list_channels({})
        used_channel = 0
        for i in range(len(channels["channels"])):
            if (
                channels["channels"][i]["remote_balance"]
                > before_channels["channels"][i]["remote_balance"]
            ):
                used_channel += 1
        assert used_channel > 1, "Expected more than one channel to be used"
