"""
Test CKB and UDT mixed payment: a=b=c=a (ckb, udt1, udt2).
Requirement: https://github.com/nervosnetwork/fiber/pull/681, https://github.com/nervosnetwork/fiber/pull/683
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, PaymentStatus, TLCFeeRate


class TestCkbWithUDT(FiberTest):
    """
    Test CKB/UDT ring: a=b=c=a with ckb, udt1, udt2. Self-payments CKB and udt1; udt2 unchanged.
    Mixed-hop routers (ckb/udt1/udt2) must be rejected by send_payment_with_router.
    """

    def test_ckb_with_udt(self):
        """
        Ring a=b=c=a (ckb, udt1, udt2). Self-pay CKB and udt1; assert udt2 balance unchanged.
        Then assert mixed-hop routers (ckb-udt1-udt2, etc.) fail send_payment_with_router.
        Step 1: Build CKB and UDT channels; faucet; open channels.
        Step 2: Send 30 self-payments CKB and 30 udt1; assert udt2 (fiber1 UDT) balance unchanged.
        Step 3: Build ckb, udt1, udt2 routers; send_payment_with_router with mixed hops fails.
        Step 4: Same mixed-hop with amount 1; expect "max_fee_amount is too low" or payment Failed.
        """
        # Step 1: Build topology and UDT channels
        self.start_new_fiber(
            self.generate_account(10000, self.fiber1.account_private, Amount.udt(1000))
        )
        self.faucet(
            self.fibers[1].account_private,
            10000,
            self.fiber1.account_private,
            Amount.udt(10000),
        )
        self.faucet(
            self.fibers[2].account_private,
            0,
            self.fiber1.account_private,
            Amount.udt(10000),
        )
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            Amount.udt(10000),
        )

        self.open_channel(
            self.fibers[0],
            self.fibers[1],
            Amount.ckb(1000),
            Amount.ckb(1000),
            TLCFeeRate.DEFAULT,
            TLCFeeRate.DEFAULT,
        )
        self.open_channel(
            self.fibers[1],
            self.fibers[2],
            Amount.ckb(1000),
            Amount.ckb(1000),
            TLCFeeRate.DEFAULT,
            TLCFeeRate.DEFAULT,
        )
        self.open_channel(
            self.fibers[2],
            self.fibers[0],
            Amount.ckb(1000),
            Amount.ckb(1000),
            TLCFeeRate.DEFAULT,
            TLCFeeRate.DEFAULT,
        )

        self.open_channel(
            self.fibers[0],
            self.fibers[1],
            Amount.ckb(1000),
            Amount.ckb(1000),
            TLCFeeRate.DEFAULT,
            TLCFeeRate.DEFAULT,
            self.get_account_udt_script(self.fiber1.account_private),
        )
        self.open_channel(
            self.fibers[1],
            self.fibers[2],
            Amount.ckb(1000),
            Amount.ckb(1000),
            TLCFeeRate.DEFAULT,
            TLCFeeRate.DEFAULT,
            self.get_account_udt_script(self.fiber1.account_private),
        )

        self.send_payment(self.fibers[1], self.fibers[2], Amount.ckb(1000))
        self.open_channel(
            self.fibers[2],
            self.fibers[0],
            Amount.ckb(1000),
            Amount.ckb(1000),
            TLCFeeRate.DEFAULT,
            TLCFeeRate.DEFAULT,
            self.get_account_udt_script(self.fiber1.account_private),
        )

        self.faucet(
            self.fibers[2].account_private,
            0,
            self.fiber2.account_private,
            Amount.udt(10000),
        )
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber2.account_private,
            Amount.udt(10000),
        )
        self.faucet(
            self.fibers[1].account_private,
            10000,
            self.fiber2.account_private,
            Amount.udt(10000),
        )
        self.open_channel(
            self.fibers[0],
            self.fibers[1],
            Amount.ckb(1000),
            Amount.ckb(1000),
            TLCFeeRate.DEFAULT,
            TLCFeeRate.DEFAULT,
            self.get_account_udt_script(self.fiber2.account_private),
        )
        self.open_channel(
            self.fibers[1],
            self.fibers[2],
            Amount.ckb(1000),
            Amount.ckb(1000),
            TLCFeeRate.DEFAULT,
            TLCFeeRate.DEFAULT,
            self.get_account_udt_script(self.fiber2.account_private),
        )
        self.open_channel(
            self.fibers[2],
            self.fibers[0],
            Amount.ckb(1000),
            Amount.ckb(1000),
            TLCFeeRate.DEFAULT,
            TLCFeeRate.DEFAULT,
            self.get_account_udt_script(self.fiber2.account_private),
        )

        # Step 2: Self-pay CKB and udt1; assert udt2 (fiber1 UDT) unchanged
        before_fibers_balance = self.get_fibers_balance_message()
        for _ in range(30):
            self.send_payment(self.fibers[0], self.fibers[0], 1, False)
            self.send_payment(
                self.fibers[0],
                self.fibers[0],
                Amount.ckb(1),
                False,
                self.get_account_udt_script(self.fiber2.account_private),
            )

        # Allow balance sync after self-payments
        time.sleep(10)
        key = self.get_account_udt_script(self.fiber1.account_private)["args"]
        for fiber in self.fibers:
            fiber_map = self.get_fiber_balance(fiber)
            assert fiber_map[key] == {
                "local_balance": Amount.ckb(2000) + DEFAULT_MIN_DEPOSIT_CKB,
                "offered_tlc_balance": 0,
                "received_tlc_balance": 0,
            }

        self.send_payment(self.fibers[0], self.fibers[0], Amount.ckb(1))
        self.send_payment(
            self.fibers[0],
            self.fibers[0],
            Amount.ckb(1),
            self.get_account_udt_script(self.fiber2.account_private),
        )

        # Step 3: Build routers and assert mixed-hop send_payment_with_router fails
        amount = Amount.ckb(1)
        ckb_router = self.fiber1.get_client().build_router(
            {
                "amount": hex(amount),
                "hops_info": [
                    self.get_node_hops_info(self.fiber1, self.fiber2, amount)[0],
                    self.get_node_hops_info(self.fibers[1], self.fibers[2], amount)[0],
                    self.get_node_hops_info(self.fibers[2], self.fibers[0], amount)[0],
                ],
            }
        )
        udt1_router = self.fiber1.get_client().build_router(
            {
                "amount": hex(amount),
                "udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
                "hops_info": [
                    self.get_node_hops_info(
                        self.fiber1,
                        self.fiber2,
                        amount,
                        self.get_account_udt_script(self.fiber1.account_private),
                    )[0],
                    self.get_node_hops_info(
                        self.fibers[1],
                        self.fibers[2],
                        amount,
                        self.get_account_udt_script(self.fiber1.account_private),
                    )[0],
                    self.get_node_hops_info(
                        self.fibers[2],
                        self.fibers[0],
                        amount,
                        self.get_account_udt_script(self.fiber1.account_private),
                    )[0],
                ],
            }
        )
        udt2_router = self.fiber1.get_client().build_router(
            {
                "amount": hex(amount),
                "udt_type_script": self.get_account_udt_script(
                    self.fiber2.account_private
                ),
                "hops_info": [
                    self.get_node_hops_info(
                        self.fiber1,
                        self.fiber2,
                        amount,
                        self.get_account_udt_script(self.fiber2.account_private),
                    )[0],
                    self.get_node_hops_info(
                        self.fibers[1],
                        self.fibers[2],
                        amount,
                        self.get_account_udt_script(self.fiber2.account_private),
                    )[0],
                    self.get_node_hops_info(
                        self.fibers[2],
                        self.fibers[0],
                        amount,
                        self.get_account_udt_script(self.fiber2.account_private),
                    )[0],
                ],
            }
        )

        # ckb udt1 udt2 will failed
        router = []
        router.append(ckb_router["router_hops"][0])
        router.append(udt1_router["router_hops"][1])
        router.append(udt2_router["router_hops"][2])

        payment = self.fiber1.get_client().send_payment_with_router(
            {
                "keysend": True,
                "dry_run": False,
                "router": router,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], PaymentStatus.FAILED)

        # udt1 udt1 udt2 will failed
        router = []
        router.append(udt1_router["router_hops"][0])
        router.append(udt1_router["router_hops"][1])
        router.append(udt2_router["router_hops"][2])

        payment = self.fiber1.get_client().send_payment_with_router(
            {
                "keysend": True,
                "dry_run": False,
                "router": router,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], PaymentStatus.FAILED)

        # ckb udt ckb will failed
        router = []
        router.append(ckb_router["router_hops"][0])
        router.append(udt1_router["router_hops"][1])
        router.append(ckb_router["router_hops"][2])

        payment = self.fiber1.get_client().send_payment_with_router(
            {
                "keysend": True,
                "dry_run": False,
                "router": router,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], PaymentStatus.FAILED)

        # udt1 udt2 udt1 will failed
        router = []
        router.append(udt1_router["router_hops"][0])
        router.append(udt2_router["router_hops"][1])
        router.append(udt1_router["router_hops"][2])

        payment = self.fiber1.get_client().send_payment_with_router(
            {
                "keysend": True,
                "dry_run": False,
                "router": router,
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], PaymentStatus.FAILED)

        amount = 1
        ckb_router = self.fiber1.get_client().build_router(
            {
                "amount": hex(amount),
                "hops_info": [
                    self.get_node_hops_info(self.fiber1, self.fiber2, amount)[0],
                    self.get_node_hops_info(self.fibers[1], self.fibers[2], amount)[0],
                    self.get_node_hops_info(self.fibers[2], self.fibers[0], amount)[0],
                ],
            }
        )
        udt1_router = self.fiber1.get_client().build_router(
            {
                "amount": hex(amount),
                "udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
                "hops_info": [
                    self.get_node_hops_info(
                        self.fiber1,
                        self.fiber2,
                        amount,
                        self.get_account_udt_script(self.fiber1.account_private),
                    )[0],
                    self.get_node_hops_info(
                        self.fibers[1],
                        self.fibers[2],
                        amount,
                        self.get_account_udt_script(self.fiber1.account_private),
                    )[0],
                    self.get_node_hops_info(
                        self.fibers[2],
                        self.fibers[0],
                        amount,
                        self.get_account_udt_script(self.fiber1.account_private),
                    )[0],
                ],
            }
        )
        udt2_router = self.fiber1.get_client().build_router(
            {
                "amount": hex(amount),
                "udt_type_script": self.get_account_udt_script(
                    self.fiber2.account_private
                ),
                "hops_info": [
                    self.get_node_hops_info(
                        self.fiber1,
                        self.fiber2,
                        amount,
                        self.get_account_udt_script(self.fiber2.account_private),
                    )[0],
                    self.get_node_hops_info(
                        self.fibers[1],
                        self.fibers[2],
                        amount,
                        self.get_account_udt_script(self.fiber2.account_private),
                    )[0],
                    self.get_node_hops_info(
                        self.fibers[2],
                        self.fibers[0],
                        amount,
                        self.get_account_udt_script(self.fiber2.account_private),
                    )[0],
                ],
            }
        )

        # # ckb udt1 udt2 will failed
        router = []
        router.append(ckb_router["router_hops"][0])
        router.append(udt1_router["router_hops"][1])
        router.append(udt2_router["router_hops"][2])

        with pytest.raises(Exception) as exc_info:
            payment = self.fiber1.get_client().send_payment_with_router(
                {
                    "keysend": True,
                    "dry_run": False,
                    "router": router,
                }
            )

        expected_error_message = "max_fee_amount is too low for selected route"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        # udt1 udt1 udt2 will failed
        router = []
        router.append(udt1_router["router_hops"][0])
        router.append(udt1_router["router_hops"][1])
        router.append(udt2_router["router_hops"][2])

        with pytest.raises(Exception) as exc_info:
            payment = self.fiber1.get_client().send_payment_with_router(
                {
                    "keysend": True,
                    "dry_run": False,
                    "router": router,
                }
            )
        expected_error_message = "max_fee_amount is too low for selected route"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        # ckb udt ckb will failed
        router = []
        router.append(ckb_router["router_hops"][0])
        router.append(udt1_router["router_hops"][1])
        router.append(ckb_router["router_hops"][2])

        with pytest.raises(Exception) as exc_info:
            payment = self.fiber1.get_client().send_payment_with_router(
                {
                    "keysend": True,
                    "dry_run": False,
                    "router": router,
                }
            )
        expected_error_message = "max_fee_amount is too low for selected route"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )

        # udt1 udt2 udt1 will failed
        router = []
        router.append(udt1_router["router_hops"][0])
        router.append(udt2_router["router_hops"][1])
        router.append(udt1_router["router_hops"][2])

        with pytest.raises(Exception) as exc_info:
            payment = self.fiber1.get_client().send_payment_with_router(
                {
                    "keysend": True,
                    "dry_run": False,
                    "router": router,
                }
            )
        expected_error_message = "max_fee_amount is too low for selected route"
        assert expected_error_message in exc_info.value.args[0], (
            f"Expected substring '{expected_error_message}' "
            f"not found in actual string '{exc_info.value.args[0]}'"
        )
