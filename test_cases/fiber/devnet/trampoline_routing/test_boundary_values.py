import time
from mimetypes import inited

import pytest

from framework.basic_share_fiber import SharedFiberTest
from framework.test_fiber import Fiber


class TestBoundaryValues(SharedFiberTest):
    """
    测试 trampoline routing 的边界值场景
    包括最大 hops、最小金额、最大金额等
    """

    fiber3: Fiber
    fiber4: Fiber
    fiber5: Fiber
    fiber6: Fiber
    fiber7: Fiber
    fiber8: Fiber

    def setUp(self):
        if getattr(TestBoundaryValues, "_channel_inited", False):
            return
        TestBoundaryValues._channel_inited = True
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
        # #
        # # # 建立通道链（支持最多7个hops）
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0)
        self.open_channel(self.fiber3, self.fiber4, 1000 * 100000000, 0)
        self.open_channel(self.fiber4, self.fiber5, 1000 * 100000000, 0)
        self.open_channel(self.fiber5, self.fiber6, 1000 * 100000000, 0)
        self.open_channel(self.fiber6, self.fiber7, 1000 * 100000000, 0)
        self.open_channel(self.fiber7, self.fiber8, 1000 * 100000000, 0)

    def test_max_trampoline_hops(self):
        # 测试1: 使用最大数量的 trampoline hops（5个）
        before_balance = self.get_fibers_balance()

        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber7.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                "dry_run": True,
                # "max_fee_amount": hex(1 * 100000000),
                "trampoline_hops": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["node_id"],
                    },
                    {
                        "pubkey": self.fiber3.get_client().node_info()["node_id"],
                    },
                    {
                        "pubkey": self.fiber4.get_client().node_info()["node_id"],
                    },
                    {
                        "pubkey": self.fiber5.get_client().node_info()["node_id"],
                    },
                    {
                        "pubkey": self.fiber6.get_client().node_info()["node_id"],
                    },
                ],
            }
        )
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber7.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                "max_fee_amount": payment["fee"],
                "trampoline_hops": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["node_id"],
                    },
                    {
                        "pubkey": self.fiber3.get_client().node_info()["node_id"],
                    },
                    {
                        "pubkey": self.fiber4.get_client().node_info()["node_id"],
                    },
                    {
                        "pubkey": self.fiber5.get_client().node_info()["node_id"],
                    },
                    {
                        "pubkey": self.fiber6.get_client().node_info()["node_id"],
                    },
                ],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
        after_balance = self.get_fibers_balance()
        result = self.get_channel_balance_change(before_balance, after_balance)
        print("get_channel_balance_change:", result)
        payment = self.fiber1.get_client().get_payment(
            {
                "payment_hash": payment["payment_hash"],
            }
        )
        assert payment["fee"] == hex(1509034)
        # todo 函数 验证 trampoline routing 余额计算

        assert result == [
            {
                "local_balance": 101509034,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
            {
                "local_balance": -706630,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
            {
                "local_balance": -201203,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
            {
                "local_balance": -200801,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
            {
                "local_balance": -200400,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
            {
                "local_balance": -200000,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
            {
                "local_balance": -100000000,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            },
            {"local_balance": 0, "offered_tlc_balance": 0, "received_tlc_balance": 0},
        ]

    def test_exceed_max_trampoline_hops(self):
        # 测试2: 尝试使用超过最大数量的 trampoline hops（6个，超过限制5个）
        with pytest.raises(Exception) as exc_info:
            payment = self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber8.get_client().node_info()["node_id"],
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
                        {
                            "pubkey": self.fiber4.get_client().node_info()["node_id"],
                        },
                        {
                            "pubkey": self.fiber5.get_client().node_info()["node_id"],
                        },
                        {
                            "pubkey": self.fiber6.get_client().node_info()["node_id"],
                        },
                        {
                            "pubkey": self.fiber7.get_client().node_info()[
                                "node_id"
                            ],  # 第6个，超过限制
                        },
                    ],
                }
            )
            self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
        # 应该因为超过最大 hops 而失败
        assert "too many" in exc_info.value.args[0].lower() or "Failed" in str(
            exc_info.value
        )

    def test_minimum_amount(self):
        # 测试1: 最小金额支付（1 satoshi）
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1),  # 最小金额
                "keysend": True,
                "trampoline_hops": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["node_id"],
                    },
                ],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

    def test_large_amount(self):
        """
        # 测试2: 大金额支付
        """

        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(50 * 100000000),  # 大金额
                "keysend": True,
                "trampoline_hops": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["node_id"],
                    },
                ],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

    def test_zero_fee_rate(self):
        # 测试3: fee_rate 为 0 的场景
        before_balance = self.get_fibers_balance()
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                "trampoline_hops": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["node_id"],
                        "fee_rate": hex(0),  # 零费率
                    },
                ],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
        after_balance = self.get_fibers_balance()
        result = self.get_channel_balance_change(before_balance, after_balance)
        print(result)

    def test_very_high_fee_rate(self):
        # 测试4: 极高的 fee_rate（接近上限）
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                "trampoline_hops": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["node_id"],
                        "fee_rate": hex(1000000),  # 高费率
                    },
                ],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

    def test_minimum_max_fee_amount(self):
        # 测试5: 最小 max_fee_amount
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "currency": "Fibd",
                "amount": hex(1 * 100000000),
                "keysend": True,
                "max_fee_amount": hex(200000),  # 最小费用预算
                "trampoline_hops": [
                    {
                        "pubkey": self.fiber2.get_client().node_info()["node_id"],
                        "fee_rate": hex(0),  # 零费率以确保费用最小
                    },
                ],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
