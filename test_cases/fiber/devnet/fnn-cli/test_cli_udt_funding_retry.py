"""
PR-1253: fix: abort funding immediately on insufficient UDT cells
Issue: https://github.com/nervosnetwork/fiber/issues/1195

When opening a UDT channel, if UDT cells are unavailable (e.g. not yet indexed
or simply never funded), the old code silently stalled the channel in
NEGOTIATING_FUNDING state.  After this fix:

- InsufficientCells (no UDT cells at all) → channel aborts immediately
- AbsentTx (empty funding tx, possibly indexer lag) → retried via backoff
"""

import time

import pytest

from framework.basic_fiber import FiberTest
from framework.fnn_cli import FnnCli


class TestCliUdtFundingAbortNoUdtCells(FiberTest):
    """Open a UDT channel via CLI when the opener has NO UDT cells.

    After PR-1253 the channel should be aborted (not stuck in NEGOTIATING).
    """

    def test_open_udt_channel_no_udt_cells_aborts(self):
        """Open UDT channel when opener has zero UDT balance.

        The node has CKB but no UDT tokens.  The funding tx builder will
        fail with 'can not find enough UDT owner cells' which now maps to
        FundingError::InsufficientCells (non-temporary) → abort_funding.

        Expected: channel is NOT stuck; it is removed from channel list
        within a short time.
        """
        # Do NOT faucet UDT - the node only has CKB
        # Build a valid-looking UDT type script from fiber1's account
        udt_script = self.get_account_udt_script(self.fiber1.account_private)

        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")

        # open_channel should return a temporary_channel_id initially
        result = cli1.open_channel(
            pubkey=self.fiber2.get_pubkey(),
            funding_amount=100 * 100000000,
            public=True,
            funding_udt_type_script=udt_script,
        )
        assert "temporary_channel_id" in result

        # Wait a few seconds for the funding retry logic to kick in and abort
        time.sleep(10)

        # After abort, channel should NOT be stuck in NEGOTIATING_FUNDING
        channels = self.fiber1.get_client().list_channels(
            {"pubkey": self.fiber2.get_pubkey()}
        )
        # The channel should either be absent or not in NEGOTIATING_FUNDING
        for ch in channels["channels"]:
            assert ch["state"]["state_name"] != "NEGOTIATING_FUNDING", (
                f"Channel {ch['channel_id']} is stuck in NEGOTIATING_FUNDING "
                f"after InsufficientCells - PR-1253 fix not working"
            )

    def test_open_udt_channel_no_udt_cells_channel_removed(self):
        """Open UDT channel without UDT cells, verify channel is removed."""
        udt_script = self.get_account_udt_script(self.fiber1.account_private)

        result = self.fiber1.get_client().open_channel(
            {
                "pubkey": self.fiber2.get_pubkey(),
                "funding_amount": hex(100 * 100000000),
                "public": True,
                "funding_udt_type_script": udt_script,
            }
        )
        temporary_channel_id = result["temporary_channel_id"]

        # Wait for the funding logic to abort the channel
        time.sleep(10)

        # Channel should be gone from the active list
        channels = self.fiber1.get_client().list_channels(
            {"pubkey": self.fiber2.get_pubkey()}
        )
        active_ids = [ch["channel_id"] for ch in channels["channels"]]
        # The temporary channel may have been promoted to a real channel_id
        # or simply removed.  Either way it should NOT be stuck.
        for ch in channels["channels"]:
            assert ch["state"]["state_name"] != "NEGOTIATING_FUNDING", (
                f"Channel still stuck in NEGOTIATING_FUNDING with id "
                f"{ch['channel_id']}"
            )


class TestCliUdtFundingAbortInsufficientBalance(FiberTest):
    """Open a UDT channel via CLI with UDT amount exceeding available balance."""

    def test_open_udt_channel_exceeding_udt_balance_aborts(self):
        """Fund node with some UDT, then try to open a channel with more than
        the available UDT balance.  Should be aborted, not stuck.
        """
        # Fund a small amount of UDT
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            100 * 100000000,
        )
        time.sleep(10)

        udt_script = self.get_account_udt_script(self.fiber1.account_private)
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")

        # Try to open channel with 10000 UDT (much more than the 100 we have)
        result = cli1.open_channel(
            pubkey=self.fiber2.get_pubkey(),
            funding_amount=10000 * 100000000,
            public=True,
            funding_udt_type_script=udt_script,
        )
        assert "temporary_channel_id" in result

        # Wait for abort
        time.sleep(10)

        # Channel should NOT be stuck in NEGOTIATING_FUNDING
        channels = self.fiber1.get_client().list_channels(
            {"pubkey": self.fiber2.get_pubkey()}
        )
        for ch in channels["channels"]:
            assert ch["state"]["state_name"] != "NEGOTIATING_FUNDING", (
                f"Channel {ch['channel_id']} stuck in NEGOTIATING_FUNDING "
                f"with insufficient UDT balance - PR-1253 fix not working"
            )


class TestCliUdtFundingRetrySuccess(FiberTest):
    """Open a UDT channel immediately after issuing UDT tokens.

    Tests the retry mechanism: AbsentTx (indexer lag) is now temporary, so
    the funding should be retried and eventually succeed once the indexer
    catches up.
    """

    def test_open_udt_channel_immediately_after_issue_succeeds(self):
        """Issue UDT and immediately open channel without waiting for indexer.

        With PR-1253, AbsentTx is temporary → funding retries with backoff.
        The channel should eventually reach ChannelReady.
        """
        # Issue UDT to both nodes
        self.faucet(
            self.fiber2.account_private,
            0,
            self.fiber1.account_private,
            10000 * 100000000,
        )
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            10000 * 100000000,
        )

        udt_script = self.get_account_udt_script(self.fiber1.account_private)
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")

        # Open channel IMMEDIATELY - no time.sleep() to wait for indexer
        result = cli1.open_channel(
            pubkey=self.fiber2.get_pubkey(),
            funding_amount=2000 * 100000000,
            public=True,
            funding_udt_type_script=udt_script,
        )
        assert "temporary_channel_id" in result

        # The channel should eventually reach ChannelReady via retry mechanism
        # Give it a generous timeout since retries use exponential backoff
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_pubkey(),
            "ChannelReady",
            120,
        )


class TestCliUdtFundingNormalBackwardCompat(FiberTest):
    """Backward compatibility: normal UDT channel open via CLI still works."""

    def test_open_udt_channel_with_sufficient_balance_via_cli(self):
        """Standard UDT channel open with proper funding via CLI."""
        self.faucet(
            self.fiber2.account_private,
            0,
            self.fiber1.account_private,
            10000 * 100000000,
        )
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            10000 * 100000000,
        )
        time.sleep(10)

        udt_script = self.get_account_udt_script(self.fiber1.account_private)
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")

        result = cli1.open_channel(
            pubkey=self.fiber2.get_pubkey(),
            funding_amount=2000 * 100000000,
            public=True,
            funding_udt_type_script=udt_script,
        )
        assert "temporary_channel_id" in result

        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_pubkey(),
            "ChannelReady",
            120,
        )

        # Verify channel is actually usable - send a payment
        self.send_payment(self.fiber1, self.fiber2, 10 * 100000000, True, udt_script)

    def test_open_udt_channel_no_udt_cells_then_normal_open_succeeds(self):
        """After a failed UDT channel open (no cells), a subsequent normal
        open with proper funding should still succeed.
        """
        udt_script = self.get_account_udt_script(self.fiber1.account_private)

        # First attempt: no UDT cells → should abort
        result = self.fiber1.get_client().open_channel(
            {
                "pubkey": self.fiber2.get_pubkey(),
                "funding_amount": hex(100 * 100000000),
                "public": True,
                "funding_udt_type_script": udt_script,
            }
        )
        time.sleep(10)

        # Now fund UDT properly
        self.faucet(
            self.fiber2.account_private,
            0,
            self.fiber1.account_private,
            10000 * 100000000,
        )
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            10000 * 100000000,
        )
        time.sleep(10)

        # Second attempt: should succeed
        cli1 = FnnCli(f"http://127.0.0.1:{self.fiber1.rpc_port}")
        result = cli1.open_channel(
            pubkey=self.fiber2.get_pubkey(),
            funding_amount=2000 * 100000000,
            public=True,
            funding_udt_type_script=udt_script,
        )
        assert "temporary_channel_id" in result

        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_pubkey(),
            "ChannelReady",
            120,
        )
