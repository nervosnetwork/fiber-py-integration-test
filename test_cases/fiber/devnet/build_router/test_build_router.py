import pytest
from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout, ChannelState, TLCFeeRate
from framework.config import DEFAULT_MIN_DEPOSIT_CKB


class TestBuildRouter(FiberTest):
    """
    Test build_router RPC functionality.
    Requirement: https://github.com/nervosnetwork/fiber/blob/main/rpc/README.md#build_router
    """

    def test_base_build_router(self):
        """
        Test basic router building for a private channel.
        Step 1: Start new fiber nodes and connect them.
        Step 2: Open a private channel between fiber3 and fiber0.
        Step 3: Wait for channel to be ready.
        Step 4: Build router with specific hops_info.
        Step 5: Assert router hops information is correct.
        """
        # Step 1: Start new fiber nodes and connect them
        self.start_new_fiber(self.generate_account(10000))
        self.start_new_fiber(self.generate_account(10000))

        fiber1_balance = Amount.ckb(1000)
        fiber1_fee = TLCFeeRate.DEFAULT

        self.open_channel(
            self.fibers[1], self.fibers[2],
            Amount.ckb(1000), Amount.ckb(1),
            fiber1_fee=fiber1_fee, fiber2_fee=fiber1_fee,
        )  # b-c
        self.open_channel(
            self.fibers[2], self.fibers[3],
            Amount.ckb(1000), Amount.ckb(1),
            fiber1_fee=fiber1_fee, fiber2_fee=fiber1_fee,
        )  # c-d

        self.fibers[3].connect_peer(self.fibers[0])  # d-a

        # Step 2: Open a private channel between fiber3 and fiber0
        self.fibers[3].get_client().open_channel(
            {
                "peer_id": self.fibers[0].get_peer_id(),
                "funding_amount": hex(fiber1_balance + DEFAULT_MIN_DEPOSIT_CKB),
                "tlc_fee_proportional_millionths": hex(fiber1_fee),
                "public": False,
            }
        )

        # Step 3: Wait for channel to be ready
        self.wait_for_channel_state(
            self.fibers[3].get_client(), self.fibers[0].get_peer_id(), ChannelState.CHANNEL_READY
        )

        # Step 4: Build router with specific hops_info
        channels = (
            self.fibers[3]
            .get_client()
            .list_channels({"peer_id": self.fibers[0].get_peer_id()})
        )
        da_channel_outpoint = channels["channels"][0]["channel_outpoint"]

        router_hops = (
            self.fibers[3]
            .get_client()
            .build_router(
                {
                    "amount": hex(1 + DEFAULT_MIN_DEPOSIT_CKB),
                    "udt_type_script": None,
                    "hops_info": [
                        {
                            "pubkey": self.fibers[0].get_client().node_info()["node_id"],
                            "channel_outpoint": da_channel_outpoint,
                        },
                    ],
                    "final_tlc_expiry_delta": None,
                }
            )
        )

        # Step 5: Assert router hops information is correct
        assert "router_hops" in router_hops
        hop = router_hops["router_hops"][0]
        assert hop["channel_outpoint"] == da_channel_outpoint
        assert hop["target"] == self.fibers[0].get_client().node_info()["node_id"]
        assert hop["amount_received"] == hex(1 + DEFAULT_MIN_DEPOSIT_CKB)

    def test_amount_invalid(self):
        """
        Test build_router validation for amount parameter.
        Step 1: Setup network a-b and open channel.
        Step 2: Test amount=0 should be rejected.
        Step 3: Test amount exceeding balance should be rejected.
        Step 4: Test normal amount should succeed.
        """
        # Step 1: Setup network a-b and open channel
        self.start_new_fiber(self.generate_account(10000))
        self.start_new_fiber(self.generate_account(10000))

        channel_balance = Amount.ckb(1000)
        channel_fee = TLCFeeRate.DEFAULT

        self.fibers[0].connect_peer(self.fibers[1])
        self.fibers[0].get_client().open_channel(
            {
                "peer_id": self.fibers[1].get_peer_id(),
                "funding_amount": hex(channel_balance),
                "tlc_fee_proportional_millionths": hex(channel_fee),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fibers[0].get_client(), self.fibers[1].get_peer_id(), ChannelState.CHANNEL_READY
        )

        channels = (
            self.fibers[0]
            .get_client()
            .list_channels({"peer_id": self.fibers[1].get_peer_id()})
        )
        channel_outpoint = channels["channels"][0]["channel_outpoint"]

        # Step 2: Test amount=0 should be rejected
        with pytest.raises(Exception) as exc_info:
            self.fibers[0].get_client().build_router(
                {
                    "amount": hex(0),
                    "udt_type_script": None,
                    "hops_info": [
                        {
                            "pubkey": self.fibers[1].get_client().node_info()["node_id"],
                            "channel_outpoint": channel_outpoint,
                        },
                    ],
                    "final_tlc_expiry_delta": None,
                }
            )
        err = str(exc_info.value).lower()
        assert "amount must be greater than 0" in err or "amount" in err

        # Step 3: Test amount exceeding balance should be rejected
        with pytest.raises(Exception) as exc_info:
            self.fibers[0].get_client().build_router(
                {
                    "amount": hex(channel_balance + Amount.ckb(100)),
                    "udt_type_script": None,
                    "hops_info": [
                        {
                            "pubkey": self.fibers[1].get_client().node_info()["node_id"],
                            "channel_outpoint": channel_outpoint,
                        },
                    ],
                    "final_tlc_expiry_delta": None,
                }
            )
        err = str(exc_info.value).lower()
        assert "no path found" in err

        # Step 4: Test normal amount should succeed
        router_hops = (
            self.fibers[0]
            .get_client()
            .build_router(
                {
                    "amount": hex(Amount.ckb(1)),
                    "udt_type_script": None,
                    "hops_info": [
                        {
                            "pubkey": self.fibers[1].get_client().node_info()["node_id"],
                            "channel_outpoint": channel_outpoint,
                        },
                    ],
                    "final_tlc_expiry_delta": None,
                }
            )
        )

        assert "router_hops" in router_hops
        assert len(router_hops["router_hops"]) == 1
        hop = router_hops["router_hops"][0]
        assert hop["channel_outpoint"] == channel_outpoint
        assert hop["target"] == self.fibers[1].get_client().node_info()["node_id"]
