import pytest

from framework.basic_fiber import FiberTest


class TestComplexRouting(FiberTest):
    """
    测试复杂的路由场景
    包括多个 trampoline 节点、不同的 fee_rate、混合通道类型等
    """

    def test_star_topology_routing(self):
        """
        测试星型拓扑路由
        fiber1 -> fiber2 -> {fiber3, fiber4, fiber5}
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))
        self.fiber5 = self.start_new_fiber(self.generate_account(10000))

        # 建立星型拓扑
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber4, 1000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber5, 1000 * 100000000, 0)

        # 分别向不同的目标节点发送支付
        for target in [self.fiber3, self.fiber4, self.fiber5]:
            payment = self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": target.get_client().node_info()["node_id"],
                    "currency": "Fibd",
                    "amount": hex(1 * 100000000),
                    "keysend": True,
                    "trampoline_hops": [
                        {
                            "pubkey": self.fiber2.get_client().node_info()["node_id"],
                        },
                    ],
                }
            )
            self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

    def test_mesh_topology_routing(self):
        """
        测试网状拓扑路由
        多个节点之间相互连接
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))

        # 建立网状拓扑
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        self.open_channel(self.fiber1, self.fiber3, 1000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber4, 1000 * 100000000, 0)
        self.open_channel(self.fiber3, self.fiber4, 1000 * 100000000, 0)

        # 通过不同的 trampoline 路径路由到同一个目标
        # 路径1: fiber1 -> fiber2 -> fiber4
        payment1 = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                "trampoline_hops": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["node_id"],
                    },
                ],
            }
        )
        self.wait_payment_state(self.fiber1, payment1["payment_hash"], "Success")

        # 路径2: fiber1 -> fiber3 -> fiber4
        payment2 = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                "trampoline_hops": [
                    {
                        "pubkey": self.fiber3.get_client().node_info()["node_id"],
                    },
                ],
            }
        )
        self.wait_payment_state(self.fiber1, payment2["payment_hash"], "Success")

    def test_alternating_ckb_udt_channels(self):
        """
        测试交替的 CKB 和 UDT 通道
        确保只能通过相同类型的通道路由
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))
        self.faucet(
            self.fiber2.account_private,
            0,
            self.fiber1.account_private,
            10000 * 100000000,
        )
        self.faucet(
            self.fiber4.account_private,
            0,
            self.fiber1.account_private,
            10000 * 100000000,
        )

        udt_script = self.get_account_udt_script(self.fiber1.account_private)

        # 建立交替的通道类型
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)  # CKB
        self.open_channel(
            self.fiber2, self.fiber3, 1000 * 100000000, 0, udt=udt_script
        )  # UDT
        self.open_channel(self.fiber3, self.fiber4, 1000 * 100000000, 0)  # CKB

        # 尝试通过混合通道类型路由 UDT（应该失败）
        with pytest.raises(Exception) as exc_info:
            payment = self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                    "currency": "Fibd",
                    "amount": hex(1 * 100000000),
                    "keysend": True,
                    "udt_type_script": udt_script,
                    "trampoline_hops": [
                        {
                            "pubkey": self.fiber2.get_client().node_info()["node_id"],
                        },
                        {
                            "pubkey": self.fiber3.get_client().node_info()["node_id"],
                        },
                    ],
                }
            )
        # 应该因为通道类型不匹配而失败
        assert "no path found" in exc_info.value.args[0] or "Failed" in str(
            exc_info.value
        )

    def test_private_channel_routing(self):
        """
        测试通过私有通道的路由
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))

        # 建立私有通道
        self.open_channel(
            self.fiber1,
            self.fiber2,
            1000 * 100000000,
            0,
            other_config={
                "public": False,
            },
        )
        self.open_channel(
            self.fiber2,
            self.fiber3,
            1000 * 100000000,
            0,
            other_config={
                "public": False,
            },
        )
        self.open_channel(self.fiber3, self.fiber4, 1000 * 100000000, 0)

        # 通过私有通道路由
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                "trampoline_hops": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["node_id"],
                    },
                    {
                        "pubkey": self.fiber3.get_client().node_info()["node_id"],
                    },
                ],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

    def test_one_way_channel_routing(self):
        """
        测试通过单向通道的路由
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))

        # 建立单向通道
        self.open_channel(
            self.fiber1,
            self.fiber2,
            1000 * 100000000,
            0,
            other_config={
                "public": False,
                "one_way": True,
            },
        )
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0)

        # 通过单向通道路由（应该成功，因为方向正确）
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                "trampoline_hops": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["node_id"],
                    },
                ],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

    def test_round_trip_routing(self):
        """
        测试往返路由（通过同一个 trampoline 节点发送和接收）
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))

        # 建立双向通道
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0)
        self.open_channel(self.fiber3, self.fiber2, 1000 * 100000000, 0)  # 反向通道

        # fiber1 -> fiber2 -> fiber3
        payment1 = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                "trampoline_hops": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["node_id"],
                    },
                ],
            }
        )
        self.wait_payment_state(self.fiber1, payment1["payment_hash"], "Success")

        # fiber3 -> fiber2 -> fiber1（反向）
        payment2 = self.fiber3.get_client().send_payment(
            {
                "target_pubkey": self.fiber1.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                "trampoline_hops": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["node_id"],
                    },
                ],
            }
        )
        self.wait_payment_state(self.fiber3, payment2["payment_hash"], "Success")
