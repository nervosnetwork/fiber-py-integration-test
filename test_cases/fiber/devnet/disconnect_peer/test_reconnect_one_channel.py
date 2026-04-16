import time
from unittest import TestCase

import pytest

from framework.basic_fiber import FiberTest


class TestReconnectOneChannel(FiberTest):
    @pytest.mark.skip("unstable")
    def test_reconnect_one_channel(self):
        """
        1. 启动fiber3
        2. fiber1 ->fiber2->fiber3 -> fiber1
        3. fiber1->fiber1 不停断连
        4. 测试5次
        5. 预期发送成功
        Returns:

        """
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 1000 * 100000000)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 1000 * 100000000)
        self.open_channel(self.fiber3, self.fiber1, 1000 * 100000000, 1000 * 100000000)

        for i in range(5):
            for i in range(10):
                self.send_payment(self.fiber1, self.fiber1, 1, False)
            self.fiber1.get_client().disconnect_peer(
                {"pubkey": self.fiber3.get_pubkey()}
            )
            self.fiber1.connect_peer(self.fiber3)
            time.sleep(1)
            self.send_payment(self.fiber1, self.fiber1, 1)
        self.wait_fibers_pending_tlc_eq0(self.fiber1)
        self.send_payment(self.fiber1, self.fiber1, 1)
