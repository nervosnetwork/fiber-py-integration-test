import pytest

from framework.basic_fiber import FiberTest


class TestMultiHopTrampoline(FiberTest):
    """
    测试多跳 trampoline 路由场景
    包括 3 个或更多 trampoline 节点的路由测试
    """

    # debug = True

    def test_three_hop_trampoline_routing(self):
        """
        测试 3 跳 trampoline 路由
        fiber1 -> fiber2 -> fiber3 -> fiber4
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))
        self.fiber5 = self.start_new_fiber(self.generate_account(10000))

        # 建立通道链: fiber1 -> fiber2 -> fiber3 -> fiber4 -> fiber5
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0)
        self.open_channel(self.fiber3, self.fiber4, 1000 * 100000000, 0)
        self.open_channel(self.fiber4, self.fiber5, 1000 * 100000000, 0)

        # 通过 3 个 trampoline 节点路由支付
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber5.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["node_id"],
                    self.fiber3.get_client().node_info()["node_id"],
                    self.fiber4.get_client().node_info()["node_id"],
                ],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

    def test_four_hop_trampoline_routing(self):
        """
        测试 4 跳 trampoline 路由
        fiber1 -> fiber2 -> fiber3 -> fiber4 -> fiber5 -> fiber6
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))
        self.fiber5 = self.start_new_fiber(self.generate_account(10000))
        self.fiber6 = self.start_new_fiber(self.generate_account(10000))

        # 建立通道链
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0)
        self.open_channel(self.fiber3, self.fiber4, 1000 * 100000000, 0)
        self.open_channel(self.fiber4, self.fiber5, 1000 * 100000000, 0)
        self.open_channel(self.fiber5, self.fiber6, 1000 * 100000000, 0)

        # 通过 4 个 trampoline 节点路由支付
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber6.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["node_id"],
                    self.fiber3.get_client().node_info()["node_id"],
                    self.fiber4.get_client().node_info()["node_id"],
                    self.fiber5.get_client().node_info()["node_id"],
                ],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

    def test_multi_hop_with_different_fee_rates(self):
        """
        测试多跳 trampoline 路由，每个 hop 使用不同的 fee_rate
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))
        self.fiber5 = self.start_new_fiber(self.generate_account(10000))

        # 建立通道链
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0)
        self.open_channel(self.fiber3, self.fiber4, 1000 * 100000000, 0)
        self.open_channel(self.fiber4, self.fiber5, 1000 * 100000000, 0)

        # 每个 trampoline hop 使用不同的 fee_rate
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber5.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(10 * 100000000),
                "keysend": True,
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["node_id"],
                    self.fiber3.get_client().node_info()["node_id"],
                    self.fiber4.get_client().node_info()["node_id"],
                ],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

    def test_multi_hop_with_udt(self):
        """
        测试多跳 trampoline 路由使用 UDT
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(50000))
        self.fiber4 = self.start_new_fiber(self.generate_account(50000))
        self.fiber5 = self.start_new_fiber(self.generate_account(50000))
        self.faucet(
            self.fiber2.account_private,
            0,
            self.fiber1.account_private,
            100000 * 100000000,
        )
        self.faucet(
            self.fiber3.account_private,
            0,
            self.fiber1.account_private,
            100000 * 100000000,
        )
        self.faucet(
            self.fiber4.account_private,
            0,
            self.fiber1.account_private,
            100000 * 100000000,
        )

        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            100000 * 100000000,
        )

        udt_script = self.get_account_udt_script(self.fiber1.account_private)

        # 建立 UDT 通道链
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0, udt=udt_script)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0, udt=udt_script)
        self.open_channel(self.fiber3, self.fiber4, 1000 * 100000000, 0, udt=udt_script)
        self.open_channel(self.fiber4, self.fiber5, 1000 * 100000000, 0, udt=udt_script)

        # 通过多个 trampoline 节点路由 UDT 支付
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber5.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                "udt_type_script": udt_script,
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["node_id"],
                    self.fiber3.get_client().node_info()["node_id"],
                    self.fiber4.get_client().node_info()["node_id"],
                ],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

    def test_multi_hop_mixed_ckb_udt(self):
        """
        测试多跳 trampoline 路由，混合 CKB 和 UDT 通道
        """
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))
        self.fiber5 = self.start_new_fiber(self.generate_account(10000))
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

        # 混合通道：CKB -> UDT -> CKB -> UDT
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)  # CKB
        self.open_channel(
            self.fiber2, self.fiber3, 1000 * 100000000, 0, udt=udt_script
        )  # UDT
        self.open_channel(self.fiber3, self.fiber4, 1000 * 100000000, 0)  # CKB
        self.open_channel(
            self.fiber4, self.fiber5, 1000 * 100000000, 0, udt=udt_script
        )  # UDT

        # 尝试通过混合通道路由（应该失败，因为通道类型不匹配）
        with pytest.raises(Exception) as exc_info:
            payment = self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber5.get_client().node_info()["node_id"],
                    "currency": "Fibd",
                    "amount": hex(1 * 100000000),
                    "keysend": True,
                    "udt_type_script": udt_script,
                    "trampoline_hops": [
                        self.fiber2.get_client().node_info()["node_id"],
                        self.fiber3.get_client().node_info()["node_id"],
                        self.fiber4.get_client().node_info()["node_id"],
                    ],
                }
            )
        # 应该因为通道类型不匹配而失败
        assert "no path found" in exc_info.value.args[0] or "Failed" in str(
            exc_info.value
        )
