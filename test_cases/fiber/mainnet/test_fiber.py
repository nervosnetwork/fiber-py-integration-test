import os
import random
import time

from framework.basic import CkbTest
from framework.basic_fiber import FiberTest
from framework.fiber_rpc import FiberRPCClient
from framework.rpc import RPCClient
from framework.test_fiber import Fiber, FiberConfigPath
from framework.util import generate_random_preimage
import logging

from test_cases.fiber.devnet.settle_invoice.test_settle_invoice import sha256_hex

LOGGER = logging.getLogger(__name__)


# ckt1qzda0cr08m85hc8jlnfp3zer7xulejywt49kt2rr0vthywaa50xwsqt2yg5ctyv59wsrqk2d634rj6k7c8kdjycft39my
# ckt1qzda0cr08m85hc8jlnfp3zer7xulejywt49kt2rr0vthywaa50xwsq0n4lwpc3k24hnt75pmgpmg2hgack50wdgnlsp6m


class TestFiber(CkbTest):
    # cryptapeFiber1 = FiberRPCClient("http://18.163.221.211:8227")
    # cryptapeFiber2 = FiberRPCClient("http://18.162.235.225:8227")
    ckbClient = RPCClient("https://mainnet.ckb.dev")

    ACCOUNT_PRIVATE_1 = os.getenv("ACCOUNT_PRIVATE_1")
    ACCOUNT_PRIVATE_2 = os.getenv("ACCOUNT_PRIVATE_2")

    fiber1: Fiber
    fiber2: Fiber

    @classmethod
    def setup_class(cls):
        print("\nSetup TestClass2")
        cls.fiber1 = Fiber.init_by_port(
            FiberConfigPath.CURRENT_MAINNET,
            cls.ACCOUNT_PRIVATE_1,
            "fiber/node1",
            "8228",
            "8227",
        )

        cls.fiber2 = Fiber.init_by_port(
            FiberConfigPath.CURRENT_MAINNET,
            cls.ACCOUNT_PRIVATE_2,
            "fiber/node2",
            "8229",
            "8230",
        )

        cls.fiber1.prepare()
        cls.fiber1.start()

        cls.fiber2.prepare()
        cls.fiber2.start()

        cls.fiber1.get_client().connect_peer(
            {"address": cls.fiber2.get_client().node_info()["addresses"][0]}
        )

        time.sleep(10)

    @classmethod
    def teardown_class(cls):
        channels = cls.fiber1.get_client().list_channels({})
        for i in range(len(channels["channels"])):
            channel = channels["channels"][i]
            if channel["state"]["state_name"] != "CHANNEL_READY":
                continue
            cls.fiber1.get_client().shutdown_channel(
                {
                    "channel_id": channel["channel_id"],
                    "close_script": {
                        "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                        "hash_type": "type",
                        "args": cls.fiber1.get_account()["lock_arg"],
                    },
                    "fee_rate": "0x3FC",
                }
            )
            wait_for_channel_state(
                cls.fiber1.get_client(), cls.fiber2.get_peer_id(), "CLOSED", 360
            )

        channels = cls.fiber2.get_client().list_channels({})
        for i in range(len(channels["channels"])):
            channel = channels["channels"][i]
            if channel["state"]["state_name"] != "CHANNEL_READY":
                continue
            cls.fiber2.get_client().shutdown_channel(
                {
                    "channel_id": channel["channel_id"],
                    "close_script": {
                        "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
                        "hash_type": "type",
                        "args": cls.fiber2.get_account()["lock_arg"],
                    },
                    "fee_rate": "0x3FC",
                }
            )
            wait_for_channel_state(
                cls.fiber2.get_client(), cls.fiber2.get_peer_id(), "CLOSED", 120
            )

        cls.fiber1.stop()
        cls.fiber1.clean()
        cls.fiber2.stop()
        cls.fiber2.clean()

    # def test_settle_tx(self):
    #     # temporary_channel_id = self.fiber1.get_client().open_channel(
    #     #     {
    #     #         "peer_id": self.fiber2.get_peer_id(),
    #     #         "funding_amount": hex(1000 * 100000000),
    #     #         "public": True,
    #     #         # "tlc_fee_proportional_millionths": "0x4B0",
    #     #     }
    #     # )
    #     # time.sleep(10)
    #     # wait_for_channel_state(
    #     #     self.fiber1.get_client(),
    #     #     self.fiber2.get_peer_id(),
    #     #     "CHANNEL_READY",
    #     #     360,
    #     # )
    #     #
    #     # begin = time.time()
    #     # # wait dry_run success
    #     # send_payment(
    #     #     self.fiber1.get_client(), self.fiber2.get_client(), 1000, None, 20 * 60
    #     # )
    #     # fiber1_to_fiber2_time = time.time()
    #     # send_payment(
    #     #     self.fiber2.get_client(), self.fiber1.get_client(), 1000, None, 20 * 60
    #     # )
    #     # fiber2_to_fiber1_time = time.time()
    #     # LOGGER.info(f"fiber1_to_fiber2 cost time: {fiber1_to_fiber2_time - begin}")
    #     # LOGGER.info(
    #     #     f"fiber2_to_fiber1 cost time: {fiber2_to_fiber1_time - fiber1_to_fiber2_time}"
    #     # )
    #
    #     # settle tx
    #     preimage = generate_random_preimage()
    #     payment_hash = sha256_hex(preimage)
    #     print("payment_hash", payment_hash)
    #     print("preimage", preimage)
    #     invoice = self.fiber2.get_client().new_invoice(
    #         {
    #             "amount": hex(1 * 100000000),
    #             "currency": "Fibb",
    #             "description": "open invoice settle should fail",
    #             "payment_hash": payment_hash,
    #             "hash_algorithm": "sha256",
    #         }
    #     )
    #     payment = self.fiber1.get_client().send_payment({
    #         "invoice": invoice["invoice_address"],
    #
    #     })
    #     time.sleep(10)
    #     # check payment is receive
    #     # force shutdown
    #     channel = self.fiber1.get_client().list_channels({})['channels'][0]
    #     self.fiber1.get_client().shutdown_channel(
    #         {
    #             "channel_id": channel["channel_id"],
    #             "force": True,
    #         }
    #     )
    #     # wait tx submit
    #     time.sleep(60)
    #     # settle tx
    #     self.fiber2.get_client().settle_invoice({
    #         "payment_hash": payment["payment_hash"],
    #         "payment_preimage": preimage,
    #     })

    def test_ckb_01(self):
        # open_channel
        temporary_channel_id = self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(200 * 100000000),
                "public": True,
                # "tlc_fee_proportional_millionths": "0x4B0",
            }
        )
        time.sleep(10)
        wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            "CHANNEL_READY",
            360,
        )

        begin = time.time()
        # wait dry_run success
        send_payment(
            self.fiber1.get_client(), self.fiber2.get_client(), 1000, None, 20 * 60
        )
        fiber1_to_fiber2_time = time.time()
        send_payment(
            self.fiber2.get_client(), self.fiber1.get_client(), 1000, None, 20 * 60
        )
        fiber2_to_fiber1_time = time.time()
        LOGGER.info(f"fiber1_to_fiber2 cost time: {fiber1_to_fiber2_time - begin}")
        LOGGER.info(
            f"fiber2_to_fiber1 cost time: {fiber2_to_fiber1_time - fiber1_to_fiber2_time}"
        )

    def test_shutdown(self):
        self.fiber2.stop()
        self.fiber2.start()
        # {"jsonrpc": "2.0", "id": 42, "result": {"channels": [{"channel_id": "0xb915bfebdeb4cfeac11441ae499c3aafa4d3a8c9d01201142cd135af98c3139a", "is_public": true, "channel_outpoint": "0xd7fa60876cb82e16c12224d64c4dd2f25a6f246c71e6de8e47ae3496b9b5015800000000", "peer_id": "QmZk1M6eWyvqKkGqNSYbXSS6hYsTji6xze56TbGUY77kif", "funding_udt_type_script": null, "state": {"state_name": "CLOSED", "state_flags": "UNCOOPERATIVE_LOCAL | WAITING_ONCHAIN_SETTLEMENT"}, "local_balance": "0x14fa60e500", "offered_tlc_balance": "0x5f5e100", "remote_balance": "0x0", "received_tlc_balance": "0x0", "pending_tlcs": [{"id": "0x1", "amount": "0x5f5e100", "payment_hash": "0x29a7fe1b16ea74e5f66b0dac17a9f8cf6f2605ae159e12a7976314c89df28191", "expiry": "0x19bdd814303", "forwarding_channel_id": null, "forwarding_tlc_id": null, "status": {"Outbound": "Committed"}}], "latest_commitment_transaction_hash": "0xdc1b3e23e3ee3402dbe4534e43ffb64a06f54a2781db72b2716261dbf3a06496", "created_at": "0x19bbb71fe3d", "enabled": true, "tlc_expiry_delta": "0xdbba00", "tlc_fee_proportional_millionths": "0x3e8", "shutdown_transaction_hash": "0xf938924e8f4a099983be2613a4f144297b8607b2e2203ff7bac8a08d61f1e18e"}, {"channel_id": "0x8b69f59b1327be3486f5009f3ea3b7be6b392d288748a2d61c73a40bd832bfe4", "is_public": true, "channel_outpoint": "0xa5b4f462899c2e378576b41a46999eb33a686bcfe1eeab5a4634f8c82fd1d5dc00000000", "peer_id": "QmZk1M6eWyvqKkGqNSYbXSS6hYsTji6xze56TbGUY77kif", "funding_udt_type_script": null, "state": {"state_name": "CLOSED", "state_flags": "COOPERATIVE"}, "local_balance": "0x14fa60e500", "offered_tlc_balance": "0x0", "remote_balance": "0x0", "received_tlc_balance": "0x0", "pending_tlcs": [], "latest_commitment_transaction_hash": "0x4ce07e4a4d1f6995c99bfeb49910d677563d1627eb627f79d6686b518e106cc7", "created_at": "0x19bbb5be1dc", "enabled": true, "tlc_expiry_delta": "0xdbba00", "tlc_fee_proportional_millionths": "0x3e8", "shutdown_transaction_hash": "0x67f6e219efee67740f896d2eaa52b1a87ba46f1cbabfc5077718585ba55e43fa"}]}}


def send_payment(
    fiber1: FiberRPCClient, fiber2: FiberRPCClient, amount, udt=None, wait_times=300
):
    try_times = 0
    payment = None
    for i in range(wait_times):
        try:
            payment = fiber1.send_payment(
                {
                    "amount": hex(amount),
                    "target_pubkey": fiber2.node_info()["node_id"],
                    "keysend": True,
                    "udt_type_script": udt,
                }
            )
            break
        except Exception as e:
            print(e)
            print(f"send try count: {i}")
            time.sleep(1)
            continue
    for i in range(wait_times):
        time.sleep(1)
        try:
            payment = fiber1.get_payment({"payment_hash": payment["payment_hash"]})
            if payment["status"] == "Failed":
                return send_payment(fiber1, fiber2, amount, udt, wait_times - i)
            if payment["status"] == "Success":
                print("payment success")
                return payment
        except Exception as e:
            print(e)
            print(f"wait try count: {i}")
            continue
    raise TimeoutError("payment timeout")


def generate_random_preimage():
    hash_str = "0x"
    for _ in range(64):
        hash_str += hex(random.randint(0, 15))[2:]
    return hash_str


def wait_for_channel_state(client, peer_id, expected_state, timeout=120):
    """Wait for a channel to reach a specific state."""
    for _ in range(timeout):
        channels = client.list_channels({"peer_id": peer_id, "include_closed": True})
        if channels["channels"][0]["state"]["state_name"] == expected_state:
            print(f"Channel reached expected state: {expected_state}")
            return channels["channels"][0]["channel_id"]
        print(
            f"Waiting for channel state: {expected_state}, current state: {channels['channels'][0]['state']['state_name']}"
        )
        time.sleep(1)
    raise TimeoutError(
        f"Channel did not reach state {expected_state} within timeout period."
    )
