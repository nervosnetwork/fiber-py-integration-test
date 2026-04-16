import time

import pytest

from framework.basic_share_fiber import SharedFiberTest
from framework.test_fiber import Fiber


class TestRebalancingStandardRing3(SharedFiberTest):
    """
    共享 3 节点环: fiber1 -> fiber2 -> fiber3 -> fiber1（各 1000 CKB local / 0 remote）。

    合并原 TestRebalancingAutoRoute 与 TestRebalancingManualRoute 中依赖此拓扑的用例，
    整类只启动一套 Fiber 环境，显著缩短总耗时。
    """

    fiber3: Fiber
    # debug = True

    def setUp(self):
        if getattr(TestRebalancingStandardRing3, "_channel_inited", False):
            return
        TestRebalancingStandardRing3._channel_inited = True

        # self.__class__.fiber3 = self.start_new_mock_fiber("")
        self.__class__.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber3.connect_peer(self.fiber1)
        self.fiber3.connect_peer(self.fiber2)

        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0)
        self.open_channel(self.fiber3, self.fiber1, 1000 * 100000000, 0)
        time.sleep(1)

    # --- Method 1: auto route (send_payment + allow_self_payment) ---

    def test_rebalance_auto_route_keysend(self):
        """
        Method 1: send_payment with target_pubkey = self, allow_self_payment = true, keysend = true.
        """
        channels_f1_before = self.fiber1.get_client().list_channels({})
        print("fiber1 channels before rebalance:", channels_f1_before)
        before_balances = self.get_fibers_balance()
        rebalance_amount = 100 * 100000000
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber1.get_client().node_info()["pubkey"],
                "amount": hex(rebalance_amount),
                "keysend": True,
                "allow_self_payment": True,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
        after_balances = self.get_fibers_balance()
        result = self.get_channel_balance_change(before_balances, after_balances)
        assert result == [
            {
                "local_balance": 20010000,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
            {
                "local_balance": -10010000,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
            {
                "local_balance": -10000000,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
        ]

    def test_rebalance_auto_route_invoice(self):
        """Method 1 with invoice: fiber1 creates invoice for itself, pays with allow_self_payment."""
        rebalance_amount = 100 * 100000000
        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(rebalance_amount),
                "currency": "Fibd",
                "description": "rebalance invoice",
                "payment_preimage": self.generate_random_preimage(),
                "hash_algorithm": "sha256",
            }
        )
        before_balances = self.get_fibers_balance()
        payment = self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
                "allow_self_payment": True,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

        result = self.fiber1.get_client().get_payment(
            {"payment_hash": payment["payment_hash"]}
        )
        assert result["status"] == "Success"
        after_balances = self.get_fibers_balance()
        result = self.get_channel_balance_change(before_balances, after_balances)
        assert result == [
            {
                "local_balance": 20010000,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
            {
                "local_balance": -10010000,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
            {
                "local_balance": -10000000,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
        ]

    def test_rebalance_auto_route_dry_run(self):
        """dry_run 检查可行性与手续费，不产生真实 payment session。"""
        rebalance_amount = 100 * 100000000
        dry_run_result = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber1.get_client().node_info()["pubkey"],
                "amount": hex(rebalance_amount),
                "keysend": True,
                "allow_self_payment": True,
                "dry_run": True,
            }
        )
        print("dry_run result:", dry_run_result)
        assert dry_run_result["fee"] is not None
        fee = int(dry_run_result["fee"], 16)
        assert fee > 0, f"Expected fee > 0, got {fee}"
        assert fee == 20010000, f"Expected fee 20010000, got {fee}"
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().get_payment(
                {"payment_hash": dry_run_result["payment_hash"]}
            )
        assert "Payment session not found" in exc_info.value.args[0]

    def test_rebalance_auto_route_max_fee_amount(self):
        """max_fee_amount 低于实际费率失败，等于费率时成功。"""
        rebalance_amount = 100 * 100000000

        dry_run_result = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber1.get_client().node_info()["pubkey"],
                "amount": hex(rebalance_amount),
                "keysend": True,
                "allow_self_payment": True,
                "dry_run": True,
            }
        )
        fee = int(dry_run_result["fee"], 16)
        assert fee > 0

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber1.get_client().node_info()["pubkey"],
                    "amount": hex(rebalance_amount),
                    "keysend": True,
                    "allow_self_payment": True,
                    "max_fee_amount": hex(fee - 1),
                }
            )
        assert (
            "no path found" in exc_info.value.args[0].lower()
            or "Failed to build route" in exc_info.value.args[0]
        )

        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber1.get_client().node_info()["pubkey"],
                "amount": hex(rebalance_amount),
                "keysend": True,
                "allow_self_payment": True,
                "max_fee_amount": hex(fee),
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

    def test_rebalance_no_allow_self_payment(self):
        """未开启 allow_self_payment 时应报错。"""
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber1.get_client().node_info()["pubkey"],
                    "amount": hex(100 * 100000000),
                    "keysend": True,
                }
            )
        assert "allow_self_payment is not enable" in exc_info.value.args[0]

    def test_rebalance_multiple_rounds(self):
        """多轮 rebalance，每轮 50 CKB。"""
        rebalance_amount = 20 * 100000000
        for _i in range(5):
            payment = self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber1.get_client().node_info()["pubkey"],
                    "amount": hex(rebalance_amount),
                    "keysend": True,
                    "allow_self_payment": True,
                }
            )
            self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
            time.sleep(1)

        channels = self.fiber1.get_client().list_channels({})
        for ch in channels["channels"]:
            print(
                f"Channel to {ch['pubkey']}: local={ch['local_balance']}, remote={ch['remote_balance']}"
            )

    # --- Method 2: manual route (build_router + send_payment_with_router) ---

    def test_rebalance_manual_route_3_node_ring(self):
        """Manual: fiber1 -> fiber2 -> fiber3 -> fiber1，校验余额偏移。"""
        rebalance_amount = 100 * 100000000

        f1_to_f2_outpoint = self._get_channel_outpoint(self.fiber1, self.fiber2)
        f2_to_f3_outpoint = self._get_channel_outpoint(self.fiber2, self.fiber3)
        f3_to_f1_outpoint = self._get_channel_outpoint(self.fiber3, self.fiber1)

        channels_before = self.fiber1.get_client().list_channels({})

        router = self.fiber1.get_client().build_router(
            {
                "amount": hex(rebalance_amount),
                "hops_info": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["pubkey"],
                        "channel_outpoint": f1_to_f2_outpoint,
                    },
                    {
                        "pubkey": self.fiber3.get_client().node_info()["pubkey"],
                        "channel_outpoint": f2_to_f3_outpoint,
                    },
                    {
                        "pubkey": self.fiber1.get_client().node_info()["pubkey"],
                        "channel_outpoint": f3_to_f1_outpoint,
                    },
                ],
            }
        )
        print("router_hops:", router)
        assert len(router["router_hops"]) == 3
        before_balance = self.get_fibers_balance()
        payment = self.fiber1.get_client().send_payment_with_router(
            {
                "keysend": True,
                "dry_run": False,
                "router": router["router_hops"],
            }
        )
        assert payment["status"] == "Created"
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

        channels_after = self.fiber1.get_client().list_channels({})
        f1_to_f2_before = None
        f1_to_f2_after = None
        f1_from_f3_before = None
        f1_from_f3_after = None

        for ch in channels_before["channels"]:
            if ch["pubkey"] == self.fiber2.get_pubkey():
                f1_to_f2_before = int(ch["local_balance"], 16)
            if ch["pubkey"] == self.fiber3.get_pubkey():
                f1_from_f3_before = int(ch["local_balance"], 16)

        for ch in channels_after["channels"]:
            if ch["pubkey"] == self.fiber2.get_pubkey():
                f1_to_f2_after = int(ch["local_balance"], 16)
            if ch["pubkey"] == self.fiber3.get_pubkey():
                f1_from_f3_after = int(ch["local_balance"], 16)

        assert f1_to_f2_after < f1_to_f2_before
        assert f1_from_f3_after > f1_from_f3_before
        after_balance = self.get_fibers_balance()
        result = self.get_channel_balance_change(before_balance, after_balance)
        assert result == [
            {
                "local_balance": 20010000,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
            {
                "local_balance": -10010000,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
            {
                "local_balance": -10000000,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
        ]

    def test_rebalance_manual_route_dry_run(self):
        """Manual route 的 dry_run 后再真实支付。"""
        rebalance_amount = 100 * 100000000

        f1_f2_outpoint = self._get_channel_outpoint(self.fiber1, self.fiber2)
        f2_f3_outpoint = self._get_channel_outpoint(self.fiber2, self.fiber3)
        f3_f1_outpoint = self._get_channel_outpoint(self.fiber3, self.fiber1)

        router = self.fiber1.get_client().build_router(
            {
                "amount": hex(rebalance_amount),
                "hops_info": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["pubkey"],
                        "channel_outpoint": f1_f2_outpoint,
                    },
                    {
                        "pubkey": self.fiber3.get_client().node_info()["pubkey"],
                        "channel_outpoint": f2_f3_outpoint,
                    },
                    {
                        "pubkey": self.fiber1.get_client().node_info()["pubkey"],
                        "channel_outpoint": f3_f1_outpoint,
                    },
                ],
            }
        )

        dry_result = self.fiber1.get_client().send_payment_with_router(
            {
                "keysend": True,
                "dry_run": True,
                "router": router["router_hops"],
            }
        )
        print("dry_run result:", dry_result)
        assert dry_result["fee"] is not None
        fee = int(dry_result["fee"], 16)
        assert fee >= 0

        before_balances = self.get_fibers_balance()
        payment = self.fiber1.get_client().send_payment_with_router(
            {
                "keysend": True,
                "dry_run": False,
                "router": router["router_hops"],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
        after_balances = self.get_fibers_balance()
        result = self.get_channel_balance_change(before_balances, after_balances)
        assert result == [
            {
                "local_balance": 20010000,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
            {
                "local_balance": -10010000,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
            {
                "local_balance": -10000000,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
        ]

    def test_rebalance_manual_route_with_invoice(self):
        """Manual route + invoice 自支付。"""
        rebalance_amount = 100 * 100000000

        f1_f2_outpoint = self._get_channel_outpoint(self.fiber1, self.fiber2)
        f2_f3_outpoint = self._get_channel_outpoint(self.fiber2, self.fiber3)
        f3_f1_outpoint = self._get_channel_outpoint(self.fiber3, self.fiber1)

        invoice = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(rebalance_amount),
                "currency": "Fibd",
                "description": "manual rebalance invoice",
                "expiry": "0xe10",
                "final_cltv": "0x28",
                "payment_preimage": self.generate_random_preimage(),
                "hash_algorithm": "sha256",
            }
        )

        router = self.fiber1.get_client().build_router(
            {
                "amount": hex(rebalance_amount),
                "hops_info": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["pubkey"],
                        "channel_outpoint": f1_f2_outpoint,
                    },
                    {
                        "pubkey": self.fiber3.get_client().node_info()["pubkey"],
                        "channel_outpoint": f2_f3_outpoint,
                    },
                    {
                        "pubkey": self.fiber1.get_client().node_info()["pubkey"],
                        "channel_outpoint": f3_f1_outpoint,
                    },
                ],
            }
        )

        payment = self.fiber1.get_client().send_payment_with_router(
            {
                "invoice": invoice["invoice_address"],
                "keysend": False,
                "dry_run": False,
                "router": router["router_hops"],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

        self.wait_invoice_state(self.fiber1, payment["payment_hash"], "Paid")

    def test_rebalance_verify_fee_deducted(self):
        """总 local 减少量应等于 dry_run 给出的路由费。"""
        channels_before = self.fiber1.get_client().list_channels({})
        total_local_before = sum(
            int(ch["local_balance"], 16) for ch in channels_before["channels"]
        )

        rebalance_amount = 100 * 100000000

        dry_run = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber1.get_client().node_info()["pubkey"],
                "amount": hex(rebalance_amount),
                "keysend": True,
                "allow_self_payment": True,
                "dry_run": True,
            }
        )
        expected_fee = int(dry_run["fee"], 16)

        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber1.get_client().node_info()["pubkey"],
                "amount": hex(rebalance_amount),
                "keysend": True,
                "allow_self_payment": True,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

        channels_after = self.fiber1.get_client().list_channels({})
        total_local_after = sum(
            int(ch["local_balance"], 16) for ch in channels_after["channels"]
        )

        fee_paid = total_local_before - total_local_after
        print(f"total_local_before: {total_local_before}")
        print(f"total_local_after: {total_local_after}")
        print(f"fee_paid: {fee_paid}, expected_fee: {expected_fee}")

        assert (
            fee_paid == expected_fee
        ), f"Fee mismatch: paid {fee_paid}, expected {expected_fee}"

    def _get_channel_outpoint(self, from_fiber, to_fiber):
        channels = from_fiber.get_client().list_channels(
            {"pubkey": to_fiber.get_pubkey()}
        )
        assert (
            len(channels["channels"]) > 0
        ), f"No channel found between {from_fiber.get_pubkey()} and {to_fiber.get_pubkey()}"
        return channels["channels"][0]["channel_outpoint"]


class TestRebalancingRing4(SharedFiberTest):
    """共享 4 节点环：auto 与 manual 各一则用例共用拓扑。"""

    fiber3: Fiber
    fiber4: Fiber

    def setUp(self):
        if getattr(TestRebalancingRing4, "_channel_inited", False):
            return
        TestRebalancingRing4._channel_inited = True

        self.__class__.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber4 = self.start_new_fiber(self.generate_account(10000))
        self.fiber3.connect_peer(self.fiber2)
        self.fiber4.connect_peer(self.fiber3)
        self.fiber4.connect_peer(self.fiber1)

        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0)
        self.open_channel(self.fiber3, self.fiber4, 1000 * 100000000, 0)
        self.open_channel(self.fiber4, self.fiber1, 1000 * 100000000, 0)
        time.sleep(1)

    def test_rebalance_4_node_ring(self):
        """4 节点环上 keysend self-payment。"""
        rebalance_amount = 100 * 100000000
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber1.get_client().node_info()["pubkey"],
                "amount": hex(rebalance_amount),
                "keysend": True,
                "allow_self_payment": True,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

        result = self.fiber1.get_client().get_payment(
            {"payment_hash": payment["payment_hash"]}
        )
        assert result["status"] == "Success"

    def test_rebalance_manual_route_4_node_ring(self):
        """Manual 4-hop: fiber1 -> fiber2 -> fiber3 -> fiber4 -> fiber1。"""
        rebalance_amount = 100 * 100000000

        f1_f2_outpoint = self._get_channel_outpoint(self.fiber1, self.fiber2)
        f2_f3_outpoint = self._get_channel_outpoint(self.fiber2, self.fiber3)
        f3_f4_outpoint = self._get_channel_outpoint(self.fiber3, self.fiber4)
        f4_f1_outpoint = self._get_channel_outpoint(self.fiber4, self.fiber1)

        router = self.fiber1.get_client().build_router(
            {
                "amount": hex(rebalance_amount),
                "hops_info": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["pubkey"],
                        "channel_outpoint": f1_f2_outpoint,
                    },
                    {
                        "pubkey": self.fiber3.get_client().node_info()["pubkey"],
                        "channel_outpoint": f2_f3_outpoint,
                    },
                    {
                        "pubkey": self.fiber4.get_client().node_info()["pubkey"],
                        "channel_outpoint": f3_f4_outpoint,
                    },
                    {
                        "pubkey": self.fiber1.get_client().node_info()["pubkey"],
                        "channel_outpoint": f4_f1_outpoint,
                    },
                ],
            }
        )
        assert len(router["router_hops"]) == 4

        payment = self.fiber1.get_client().send_payment_with_router(
            {
                "keysend": True,
                "dry_run": False,
                "router": router["router_hops"],
            }
        )
        assert payment["status"] == "Created"
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

    def _get_channel_outpoint(self, from_fiber, to_fiber):
        channels = from_fiber.get_client().list_channels(
            {"pubkey": to_fiber.get_pubkey()}
        )
        assert (
            len(channels["channels"]) > 0
        ), f"No channel found between {from_fiber.get_pubkey()} and {to_fiber.get_pubkey()}"
        return channels["channels"][0]["channel_outpoint"]


class TestRebalancingLineNoLoop(SharedFiberTest):
    """仅 fiber1–fiber2 单边通道，无环路。"""

    def setUp(self):
        if getattr(TestRebalancingLineNoLoop, "_channel_inited", False):
            return
        TestRebalancingLineNoLoop._channel_inited = True
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        time.sleep(1)

    def test_rebalance_no_circular_path(self):
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber1.get_client().node_info()["pubkey"],
                    "amount": hex(100 * 100000000),
                    "keysend": True,
                    "allow_self_payment": True,
                }
            )
        assert "Failed to build route" in exc_info.value.args[0]


class TestRebalancingLowOutboundFirstHop(SharedFiberTest):
    """首跳 fiber1->fiber2 仅 200 CKB，用于超额金额失败场景。"""

    fiber3: Fiber

    def setUp(self):
        if getattr(TestRebalancingLowOutboundFirstHop, "_channel_inited", False):
            return
        TestRebalancingLowOutboundFirstHop._channel_inited = True

        self.__class__.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber3.connect_peer(self.fiber1)
        self.fiber3.connect_peer(self.fiber2)

        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0)
        self.open_channel(self.fiber3, self.fiber1, 1000 * 100000000, 0)
        time.sleep(1)

    def test_rebalance_amount_exceeds_channel_capacity(self):
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber1.get_client().node_info()["pubkey"],
                    "amount": hex(300 * 100000000),
                    "keysend": True,
                    "allow_self_payment": True,
                }
            )
        assert (
            "Failed to build route" in exc_info.value.args[0]
            or "no path found" in exc_info.value.args[0].lower()
        )


class TestRebalancingManualPinChannel(SharedFiberTest):
    """fiber1–fiber2 双通道，pinned outbound。"""

    fiber3: Fiber

    def setUp(self):
        if getattr(TestRebalancingManualPinChannel, "_channel_inited", False):
            return
        TestRebalancingManualPinChannel._channel_inited = True

        self.__class__.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber3.connect_peer(self.fiber1)
        self.fiber3.connect_peer(self.fiber2)

        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        self.open_channel(self.fiber1, self.fiber2, 500 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0)
        self.open_channel(self.fiber3, self.fiber1, 1000 * 100000000, 0)
        time.sleep(1)

    def test_rebalance_manual_route_pin_specific_channel(self):
        channels_f1 = self.fiber1.get_client().list_channels(
            {"pubkey": self.fiber2.get_pubkey()}
        )
        assert (
            len(channels_f1["channels"]) == 2
        ), "Expected 2 channels between fiber1 and fiber2"

        channel_b_outpoint = None
        channel_b_local_before = None
        for ch in channels_f1["channels"]:
            local_bal = int(ch["local_balance"], 16)
            if local_bal < 600 * 100000000:
                channel_b_outpoint = ch["channel_outpoint"]
                channel_b_local_before = local_bal
                break
        assert channel_b_outpoint is not None, "Channel B not found"

        f2_f3_outpoint = self._get_channel_outpoint(self.fiber2, self.fiber3)
        f3_f1_outpoint = self._get_channel_outpoint(self.fiber3, self.fiber1)

        rebalance_amount = 50 * 100000000
        router = self.fiber1.get_client().build_router(
            {
                "amount": hex(rebalance_amount),
                "hops_info": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["pubkey"],
                        "channel_outpoint": channel_b_outpoint,
                    },
                    {
                        "pubkey": self.fiber3.get_client().node_info()["pubkey"],
                        "channel_outpoint": f2_f3_outpoint,
                    },
                    {
                        "pubkey": self.fiber1.get_client().node_info()["pubkey"],
                        "channel_outpoint": f3_f1_outpoint,
                    },
                ],
            }
        )

        payment = self.fiber1.get_client().send_payment_with_router(
            {
                "keysend": True,
                "dry_run": False,
                "router": router["router_hops"],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

        channels_f1_after = self.fiber1.get_client().list_channels(
            {"pubkey": self.fiber2.get_pubkey()}
        )
        channel_b_local_after = None
        for ch in channels_f1_after["channels"]:
            if ch["channel_outpoint"] == channel_b_outpoint:
                channel_b_local_after = int(ch["local_balance"], 16)
                break
        assert channel_b_local_after is not None
        assert (
            channel_b_local_after < channel_b_local_before
        ), f"Expected Channel B local balance to decrease: {channel_b_local_before} -> {channel_b_local_after}"

    def _get_channel_outpoint(self, from_fiber, to_fiber):
        channels = from_fiber.get_client().list_channels(
            {"pubkey": to_fiber.get_pubkey()}
        )
        assert (
            len(channels["channels"]) > 0
        ), f"No channel found between {from_fiber.get_pubkey()} and {to_fiber.get_pubkey()}"
        return channels["channels"][0]["channel_outpoint"]


class TestRebalancingManualInsufficientRemote(SharedFiberTest):
    """中间段 fiber2->fiber3 容量不足。"""

    fiber3: Fiber

    def setUp(self):
        if getattr(TestRebalancingManualInsufficientRemote, "_channel_inited", False):
            return
        TestRebalancingManualInsufficientRemote._channel_inited = True

        self.__class__.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber3.connect_peer(self.fiber1)
        self.fiber3.connect_peer(self.fiber2)

        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 200 * 100000000, 0)
        self.open_channel(self.fiber3, self.fiber1, 1000 * 100000000, 0)
        time.sleep(1)

    def test_rebalance_manual_route_insufficient_remote_balance(self):
        rebalance_amount = 500 * 100000000

        f1_f2_outpoint = self._get_channel_outpoint(self.fiber1, self.fiber2)
        f2_f3_outpoint = self._get_channel_outpoint(self.fiber2, self.fiber3)
        f3_f1_outpoint = self._get_channel_outpoint(self.fiber3, self.fiber1)

        router = self.fiber1.get_client().build_router(
            {
                "amount": hex(rebalance_amount),
                "hops_info": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["pubkey"],
                        "channel_outpoint": f1_f2_outpoint,
                    },
                    {
                        "pubkey": self.fiber3.get_client().node_info()["pubkey"],
                        "channel_outpoint": f2_f3_outpoint,
                    },
                    {
                        "pubkey": self.fiber1.get_client().node_info()["pubkey"],
                        "channel_outpoint": f3_f1_outpoint,
                    },
                ],
            }
        )
        with pytest.raises(Exception) as exc_info:
            payment = self.fiber1.get_client().send_payment_with_router(
                {
                    "keysend": True,
                    "dry_run": False,
                    "router": router["router_hops"],
                }
            )
        expected_error_message = "no path found"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

    def _get_channel_outpoint(self, from_fiber, to_fiber):
        channels = from_fiber.get_client().list_channels(
            {"pubkey": to_fiber.get_pubkey()}
        )
        assert (
            len(channels["channels"]) > 0
        ), f"No channel found between {from_fiber.get_pubkey()} and {to_fiber.get_pubkey()}"
        return channels["channels"][0]["channel_outpoint"]


class TestRebalancingBidirectionalReverse(SharedFiberTest):
    """双向注资环，连续两次 self-payment。"""

    fiber3: Fiber

    def setUp(self):
        if getattr(TestRebalancingBidirectionalReverse, "_channel_inited", False):
            return
        TestRebalancingBidirectionalReverse._channel_inited = True

        self.__class__.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber3.connect_peer(self.fiber1)
        self.fiber3.connect_peer(self.fiber2)

        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 500 * 100000000)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 500 * 100000000)
        self.open_channel(self.fiber3, self.fiber1, 1000 * 100000000, 500 * 100000000)
        time.sleep(1)

    def test_rebalance_manual_reverse_direction(self):
        self.fiber1.get_client().list_channels({})

        payment1 = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber1.get_client().node_info()["pubkey"],
                "amount": hex(200 * 100000000),
                "keysend": True,
                "allow_self_payment": True,
            }
        )
        self.wait_payment_state(self.fiber1, payment1["payment_hash"], "Success")

        channels_mid = self.fiber1.get_client().list_channels({})
        print("After forward rebalance:", channels_mid)

        payment2 = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber1.get_client().node_info()["pubkey"],
                "amount": hex(200 * 100000000),
                "keysend": True,
                "allow_self_payment": True,
            }
        )
        self.wait_payment_state(self.fiber1, payment2["payment_hash"], "Success")

        channels_final = self.fiber1.get_client().list_channels({})
        print("After reverse rebalance:", channels_final)
