import os
import time

from framework.basic import CkbTest
from framework.fiber_rpc import FiberRPCClient
from framework.test_fiber import Fiber, FiberConfigPath

import logging

LOGGER = logging.getLogger(__name__)


class TestFiber(CkbTest):
    cryptapeFiber1_peer_address = (
        "/ip4/52.52.69.223/tcp/8228/p2p/QmZCfzENZqWrWwifJj9BFDvxQWFyYw5GjdB4vN7Ynd4FxY"
    )
    cryptapeFiber1_peer_id = "QmZCfzENZqWrWwifJj9BFDvxQWFyYw5GjdB4vN7Ynd4FxY"

    cryptapeFiber2_peer_address = (
        "/ip4/54.178.252.1/tcp/8228/p2p/QmZ73KHvZ5GFxf6XhHZ3icPeKFo93rk86kZ8qauox3avJP"
    )
    cryptapeFiber2_peer_id = "QmZ73KHvZ5GFxf6XhHZ3icPeKFo93rk86kZ8qauox3avJP"

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
            {"address": cls.cryptapeFiber1_peer_address}
        )

        cls.fiber2.get_client().connect_peer(
            {"address": cls.cryptapeFiber2_peer_address}
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
                cls.fiber1.get_client(), cls.cryptapeFiber1_peer_id, "CLOSED", 360
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
                cls.fiber2.get_client(), cls.cryptapeFiber2_peer_id, "CLOSED", 360
            )

        # cls.fiber1.stop()
        # cls.fiber1.clean()
        # cls.fiber2.stop()
        # cls.fiber2.clean()

    def test_ckb_01(self):
        # open_channel
        temporary_channel_id = self.fiber1.get_client().open_channel(
            {
                "peer_id": self.cryptapeFiber1_peer_id,
                "funding_amount": hex(500 * 100000000),
                "public": True,
                # "tlc_fee_proportional_millionths": "0x4B0",
            }
        )

        temporary_channel_id = self.fiber2.get_client().open_channel(
            {
                "peer_id": self.cryptapeFiber2_peer_id,
                "funding_amount": hex(500 * 100000000),
                "public": True,
                # "tlc_fee_proportional_millionths": "0x4B0",
            }
        )
        time.sleep(10)
        wait_for_channel_state(
            self.fiber1.get_client(),
            self.cryptapeFiber1_peer_id,
            "CHANNEL_READY",
            360,
        )

        wait_for_channel_state(
            self.fiber2.get_client(),
            self.cryptapeFiber2_peer_id,
            "CHANNEL_READY",
            360,
        )
        # wait graph channel ready
        fiber1_channel_outpoint = self.fiber1.get_client().list_channels({})[
            "channels"
        ][0]["channel_outpoint"]
        fiber2_channel_outpoint = self.fiber2.get_client().list_channels({})[
            "channels"
        ][0]["channel_outpoint"]
        wait_graph_begin = time.time()
        wait_graph_channel_ready(self.fiber1.get_client(), fiber1_channel_outpoint)
        wait_graph_channel_ready(self.fiber1.get_client(), fiber2_channel_outpoint)

        wait_graph_channel_ready(self.fiber2.get_client(), fiber1_channel_outpoint)
        wait_graph_channel_ready(self.fiber2.get_client(), fiber2_channel_outpoint)
        wait_graph_end = time.time()
        time.sleep(10)
        begin = time.time()
        send_payment(
            self.fiber1.get_client(), self.fiber2.get_client(), 1000, None, 20 * 60
        )
        fiber1_to_fiber2_time = time.time()
        send_payment(
            self.fiber2.get_client(), self.fiber1.get_client(), 1000, None, 20 * 60
        )
        fiber2_to_fiber1_time = time.time()
        LOGGER.info(
            f"wait graph channel ready cost time: {wait_graph_end - wait_graph_begin}"
        )
        LOGGER.info(f"fiber1_to_fiber2 cost time: {fiber1_to_fiber2_time - begin}")
        LOGGER.info(
            f"fiber2_to_fiber1 cost time: {fiber2_to_fiber1_time - fiber1_to_fiber2_time}"
        )

    def test_ckb_02(self):
        self.fiber1.stop()
        self.fiber2.stop()
        self.fiber1.start()
        self.fiber2.start()
        time.sleep(15)
        begin = time.time()
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


def send_payment(
    fiber1: FiberRPCClient, fiber2: FiberRPCClient, amount, udt=None, wait_times=300
):
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
            wait_payment_finished(fiber1, payment["payment_hash"])
            payment = fiber1.get_payment({"payment_hash": payment["payment_hash"]})
            if payment["status"] == "Failed":
                print(f"[{i}]payment status: {payment['status']}, retrying...")
                continue
            if payment["status"] == "Success":
                print("payment success")
                return payment
            break
        except Exception as e:
            print(e)
            print(f"send try count: {i}")
            time.sleep(1)
            continue
    raise TimeoutError("payment timeout")


def wait_graph_channel_ready(client, channel_outpoint, timeout=3600):
    for i in range(timeout):
        try:
            graph = client.graph_channels({"limit": "0xffff"})
            for channel in graph["channels"]:
                if channel["channel_outpoint"] == channel_outpoint:
                    print(f"Channel {channel_outpoint} is ready")
                    return
            print(f"Waiting for channel {channel_outpoint} to be ready, try count: {i}")
            time.sleep(1)
        except Exception as e:
            print(e)
            print(f"wait graph try count: {i}")
            time.sleep(1)
            continue
    raise TimeoutError(
        f"Channel {channel_outpoint} did not become ready within timeout period."
    )


def wait_for_channel_state(client, peer_id, expected_state, timeout=360):
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


def wait_payment_finished(client, payment_hash, timeout=300):
    for i in range(timeout):
        try:
            payment = client.get_payment({"payment_hash": payment_hash})
            if payment["status"] in ["Failed", "Success"]:
                return payment
            time.sleep(1)
        except Exception as e:
            print(e)
            print(f"wait payment try count: {i}")
            time.sleep(1)
            continue
    raise TimeoutError("payment status did not become final within timeout period.")
