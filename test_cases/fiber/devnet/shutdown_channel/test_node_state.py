"""
Test cases for shutdown_channel when node is in send_payment (in-flight payments).
Covers: shutdown during multi-hop send_payment; balance and received_tlc_balance assertion.
"""
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.constants import Amount, Timeout, TLCFeeRate


class TestNodeState(FiberTest):
    """
    Test shutdown_channel during send_payment: multi-hop payment in flight; cooperative shutdown; balance check.
    """

    def test_shutdown_in_send_payment(self):
        """
        Shutdown channel in the middle of multi-hop send_payment; assert balance and received_tlc_balance.
        Step 1: Build topology fiber1-fiber2-fiber3-fiber4, open channels (fiber1-2, 2-3, 3-4).
        Step 2: Send many keysend payments from fiber1 to fiber4 (do not wait).
        Step 3: Shutdown channel N3-N4 with close_script and fee_rate; wait close tx committed.
        Step 4: Wait pending TLC 0; assert fiber1 sent balance equals fiber4 received balance and received_tlc_balance 0.
        """
        # Step 1: Build topology and open channels
        account_private_3 = self.generate_account(10000)
        account_private_4 = self.generate_account(10000)
        self.fiber3 = self.start_new_fiber(account_private_3)
        self.fiber4 = self.start_new_fiber(account_private_4)
        self.fiber2.connect_peer(self.fiber3)
        self.fiber3.connect_peer(self.fiber4)
        self.fiber4.connect_peer(self.fiber1)
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(2000),
            fiber2_balance=Amount.ckb(1),
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(2000),
            fiber2_balance=Amount.ckb(1),
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )
        self.open_channel(
            self.fiber3, self.fiber4,
            fiber1_balance=Amount.ckb(2000),
            fiber2_balance=Amount.ckb(1),
            fiber1_fee=TLCFeeRate.ZERO,
            fiber2_fee=TLCFeeRate.ZERO,
        )

        time.sleep(3)
        # Step 2: Send keysend payments from fiber1 to fiber4 (do not wait)
        node4_info = self.fiber4.get_client().node_info()
        fiber4_pub = node4_info["node_id"]
        for i in range(30):
            payment = self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": fiber4_pub,
                    "amount": hex(Amount.ckb(10)),
                    "keysend": True,
                }
            )

        channel_id_n3n4 = self.fiber4.get_client().list_channels({})["channels"][0][
            "channel_id"
        ]
        self.get_fibers_balance_message()
        fiber4_before_ckb_balance = self.Ckb_cli.wallet_get_capacity(
            self.fiber4.get_account()["address"]["testnet"]
        )
        # Step 3: Shutdown channel N3-N4 (retry until success)
        for i in range(10):
            try:
                self.fiber3.get_client().shutdown_channel(
                    {
                        "channel_id": channel_id_n3n4,
                        "close_script": {
                            "code_hash": "0x1bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                            "hash_type": "type",
                            "args": self.fiber3.get_account()["lock_arg"],
                        },
                        "fee_rate": "0x3FC",
                    }
                )
                break
            except Exception:
                time.sleep(1)
        tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx_hash)
        fiber4_after_ckb_balance = self.Ckb_cli.wallet_get_capacity(
            self.fiber4.get_account()["address"]["testnet"]
        )

        msg = self.get_tx_message(tx_hash)
        if msg["output_cells"][0]["args"] == self.fibers[3].get_account()["lock_arg"]:
            fiber4_balance = msg["output_cells"][0]["capacity"]
        else:
            fiber4_balance = msg["output_cells"][1]["capacity"]
        self.wait_fibers_pending_tlc_eq0(self.fiber1, Timeout.CHANNEL_READY)
        fiber_balance = self.get_fiber_balance(self.fiber1)
        fiber1_send_balance = Amount.ckb(2000) - fiber_balance["ckb"]["local_balance"]
        fiber4_receive_balance = fiber4_balance - DEFAULT_MIN_DEPOSIT_CKB - 1
        channels = self.fibers[3].get_client().list_channels({"include_closed": True})
        assert channels["channels"][0]["received_tlc_balance"] == "0x0"
        assert fiber1_send_balance == fiber4_receive_balance

        # payment = self.fiber1.get_client().send_payment(
        #     {
        #         "target_pubkey": fiber4_pub,
        #         "amount": hex(1 * 100000000),
        #         "keysend": True,
        #         # "invoice": "0x123",
        #     }
        # )
        # tx_hash = self.wait_and_check_tx_pool_fee(1000, False, 120)
        # tx_message = self.get_tx_message(tx_hash)
        # time.sleep(1)
        # payment = self.fiber1.get_client().get_payment(
        #     {"payment_hash": payment["payment_hash"]}
        # )
        # print("payment:", payment)
        # self.wait_payment_state(self.fiber1, payment["payment_hash"], "Failed", 120)
        # assert {
        #     "args": self.fiber4.get_account()["lock_arg"],
        #     "capacity": 6300000000,
        # } in tx_message["output_cells"]
        # payment = self.fiber1.get_client().send_payment(
        #     {
        #         "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
        #         "amount": hex(1 * 100000000),
        #         "keysend": True,
        #         # "invoice": "0x123",
        #     }
        # )
        # self.wait_payment_state(self.fiber1, payment["payment_hash"])
