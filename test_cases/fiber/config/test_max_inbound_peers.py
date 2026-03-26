import time

from framework.basic_share_fiber import SharedFiberTest
from framework.test_fiber import Fiber


class TestMaxInboundPeers(SharedFiberTest):
    """
    max_inbound_peers
    """

    start_fiber_config = {"fiber_max_inbound_peers": 3}
    fiber3: Fiber
    fiber4: Fiber
    fiber5: Fiber
    fiber6: Fiber
    fiber7: Fiber
    fiber8: Fiber

    debug = True

    def setUp(self):
        if getattr(TestMaxInboundPeers, "_channel_inited", False):
            return
        TestMaxInboundPeers._channel_inited = True
        # 创建 7 个节点（1个发送者 + 6个trampoline，支持测试超过最大hops的场景）
        # self.__class__.fiber3 = self.start_new_mock_fiber("")
        # self.__class__.fiber4 = self.start_new_mock_fiber("")
        # self.__class__.fiber5 = self.start_new_mock_fiber("")
        # self.__class__.fiber6 = self.start_new_mock_fiber("")
        # self.__class__.fiber7 = self.start_new_mock_fiber("")
        # self.__class__.fiber8 = self.start_new_mock_fiber("")

        self.__class__.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber4 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber5 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber6 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber7 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber8 = self.start_new_fiber(self.generate_account(10000))

        # # # 建立通道链

        # self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)

    def test_max_inbound_peers(self):
        """ """

        # Step 1: Set the maximum number of inbound peers to 5
        for fiber in self.new_fibers:
            fiber.connect_peer(self.fiber1)

        time.sleep(5)
        peers = self.fiber1.get_client().list_peers()
        print("len:", len(peers["peers"]))
        assert (
            len(peers["peers"]) == 4
        ), f"Expected at most 3 inbound peers, but got {len(peers['peers'])}"
