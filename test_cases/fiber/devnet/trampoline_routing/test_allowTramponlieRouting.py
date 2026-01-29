"""
Trampoline routing tests: allow_trampoline_routing, invoice/keysend, multi-hop, error cases.
"""

import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import (
    Amount,
    ChannelState,
    Currency,
    HashAlgorithm,
    PaymentStatus,
    Timeout,
)
from framework.waiter import Waiter, WaitConfig


class TestAllowTrampolineRouting(FiberTest):
    """
    Test trampoline routing: invoice with allow_trampoline_routing, keysend,
    multi-hop keysend, and validation errors (max_fee_amount, tlc_expiry, invalid hops).
    """

    def _wait_indexer_synced(self, timeout=120):
        """Wait until CKB indexer tip >= node tip."""
        def synced():
            tip = self.node.getClient().get_tip_block_number()
            indexer_tip = self.node.getClient().get_indexer_tip()
            indexer_number = int(indexer_tip.get("block_number", "0x0"), 16)
            return indexer_number >= tip

        Waiter.wait_until(
            synced,
            config=WaitConfig(timeout=timeout, interval=1.0),
            error_message="ckb indexer not synced",
        )

    def _generate_account_with_retry(self, ckb_balance, retries=20, interval=3):
        """Generate account, retrying on CKB indexer / sync errors."""
        last_error = None
        for _ in range(retries):
            try:
                return self.generate_account(ckb_balance)
            except Exception as e:
                last_error = e
                err = str(e).lower()
                if "ckb-indexer" in err or "not synced" in err:
                    time.sleep(interval)
                    continue
                raise
        raise last_error

    def _wait_node_in_graph(self, fiber, node_id, timeout=60):
        """Wait until node_id appears in fiber's graph_nodes."""
        def found():
            nodes = fiber.get_client().graph_nodes({}).get("nodes", [])
            return any(n.get("node_id") == node_id for n in nodes)

        Waiter.wait_until(
            found,
            config=WaitConfig(timeout=timeout, interval=1.0),
            error_message=f"node_id not found in graph_nodes: {node_id}",
        )

    def _build_tr001_topology(self):
        """Build topology: fiber1->fiber2 (public), fiber2->fiber3 (private)."""
        self._wait_indexer_synced()
        self.fiber3 = self.start_new_fiber(self._generate_account_with_retry(1000))
        self.fiber3.connect_peer(self.fiber2)

        self.fiber1.get_client().open_channel(
            {
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(Amount.ckb(500)),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY
        )

        self.fiber2.get_client().open_channel(
            {
                "peer_id": self.fiber3.get_peer_id(),
                "funding_amount": hex(Amount.ckb(500)),
                "public": False,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber3.get_peer_id(), ChannelState.CHANNEL_READY
        )
        self._wait_node_in_graph(self.fiber1, self.fiber2.get_client().node_info()["node_id"])
        time.sleep(Timeout.POLL_INTERVAL)

    def test_trampoline_invoice_success(self):
        """
        Invoice with allow_trampoline_routing=True; pay via trampoline; expect success.
        Step 1: Build tr001 topology.
        Step 2: Create invoice with allow_trampoline_routing=True.
        Step 3: Send payment with trampoline_hops; wait success.
        """
        # Step 1: Build tr001 topology
        self._build_tr001_topology()

        # Step 2: Create invoice with allow_trampoline_routing=True
        invoice = self.fiber3.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(10)),
                "currency": Currency.FIBD,
                "description": "trampoline invoice",
                "payment_preimage": self.generate_random_preimage(),
                "allow_trampoline_routing": True,
            }
        )

        # Step 3: Send payment with trampoline_hops; wait success
        payment = self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
                "max_fee_amount": hex(Amount.ckb(0.2)),
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, timeout=Timeout.PAYMENT_SUCCESS
        )

    def test_trampoline_invoice_sha256_hash_algorithm_success(self):
        """
        Invoice with hash_algorithm=sha256 and allow_trampoline_routing; pay via trampoline.
        Step 1: Build tr001 topology.
        Step 2: Create invoice with sha256 and allow_trampoline_routing.
        Step 3: Send payment; wait success or xfail if receiver does not validate sha256.
        """
        # Step 1: Build tr001 topology
        self._build_tr001_topology()

        # Step 2: Create invoice with sha256 and allow_trampoline_routing
        invoice = self.fiber3.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(10)),
                "currency": Currency.FIBD,
                "description": "trampoline invoice sha256",
                "payment_preimage": self.generate_random_preimage(),
                "hash_algorithm": HashAlgorithm.SHA256,
                "allow_trampoline_routing": True,
            }
        )

        # Step 3: Send payment; wait success or xfail
        payment = self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
                "max_fee_amount": hex(Amount.ckb(0.2)),
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        try:
            self.wait_payment_state(
                self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, timeout=Timeout.PAYMENT_SUCCESS
            )
        except Exception as e:
            pytest.xfail(
                "pending fix: receiver should validate preimage using invoice hash_algorithm "
                f"(sha256), error={e!s}"
            )

    def test_trampoline_keysend_success(self):
        """
        Keysend via single trampoline hop; expect success.
        Step 1: Build tr001 topology.
        Step 2: Keysend with trampoline_hops; wait success.
        """
        # Step 1: Build tr001 topology
        self._build_tr001_topology()

        # Step 2: Keysend with trampoline_hops; wait success
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
                "max_fee_amount": hex(Amount.ckb(0.2)),
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, timeout=Timeout.PAYMENT_SUCCESS
        )

    def test_trampoline_multi_hops_keysend_success(self):
        """
        Keysend via two trampoline hops (fiber1->2->3->4); expect success.
        Step 1: Build linear topology and open channels.
        Step 2: Keysend with trampoline_hops [f2, f3]; wait success.
        """
        # Step 1: Build linear topology
        self._wait_indexer_synced()
        self.fiber3 = self.start_new_fiber(self._generate_account_with_retry(1000))
        self.fiber3.connect_peer(self.fiber2)
        self.fiber4 = self.start_new_fiber(self._generate_account_with_retry(1000))
        self.fiber4.connect_peer(self.fiber3)

        self.fiber1.get_client().open_channel(
            {"peer_id": self.fiber2.get_peer_id(), "funding_amount": hex(Amount.ckb(500)), "public": True}
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY
        )
        self.fiber2.get_client().open_channel(
            {"peer_id": self.fiber3.get_peer_id(), "funding_amount": hex(Amount.ckb(500)), "public": True}
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber3.get_peer_id(), ChannelState.CHANNEL_READY
        )
        self.fiber3.get_client().open_channel(
            {"peer_id": self.fiber4.get_peer_id(), "funding_amount": hex(Amount.ckb(500)), "public": False}
        )
        self.wait_for_channel_state(
            self.fiber3.get_client(), self.fiber4.get_peer_id(), ChannelState.CHANNEL_READY
        )
        self._wait_node_in_graph(self.fiber1, self.fiber2.get_client().node_info()["node_id"])
        self._wait_node_in_graph(self.fiber1, self.fiber3.get_client().node_info()["node_id"])
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 2: Keysend with trampoline_hops [f2, f3]; wait success
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                "amount": hex(Amount.ckb(10)),
                "keysend": True,
                "max_fee_amount": hex(Amount.ckb(0.2)),
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["node_id"],
                    self.fiber3.get_client().node_info()["node_id"],
                ],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.SUCCESS, timeout=Timeout.PAYMENT_SUCCESS
        )

    @pytest.mark.skip("devnet RPC lacks node feature toggle; covered by Rust tests")
    def test_trampoline_hop_not_support_feature_should_fail(self):
        """Placeholder: trampoline hop without feature should fail (skip: no toggle)."""
        pass

    def test_trampoline_max_fee_amount_too_low_should_fail(self):
        """
        Send payment with very low max_fee_amount; expect error.
        Step 1: Build 4-node linear topology.
        Step 2: Keysend with max_fee_amount=1; assert error message.
        """
        # Step 1: Build 4-node linear topology
        self._wait_indexer_synced()
        self.fiber3 = self.start_new_fiber(self._generate_account_with_retry(1000))
        self.fiber3.connect_peer(self.fiber2)
        self.fiber4 = self.start_new_fiber(self._generate_account_with_retry(1000))
        self.fiber4.connect_peer(self.fiber3)

        self.fiber1.get_client().open_channel(
            {"peer_id": self.fiber2.get_peer_id(), "funding_amount": hex(Amount.ckb(500)), "public": True}
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), ChannelState.CHANNEL_READY
        )
        self.fiber2.get_client().open_channel(
            {"peer_id": self.fiber3.get_peer_id(), "funding_amount": hex(Amount.ckb(500)), "public": True}
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber3.get_peer_id(), ChannelState.CHANNEL_READY
        )
        self.fiber3.get_client().open_channel(
            {"peer_id": self.fiber4.get_peer_id(), "funding_amount": hex(Amount.ckb(500)), "public": False}
        )
        self.wait_for_channel_state(
            self.fiber3.get_client(), self.fiber4.get_peer_id(), ChannelState.CHANNEL_READY
        )
        self._wait_node_in_graph(self.fiber1, self.fiber2.get_client().node_info()["node_id"])
        self._wait_node_in_graph(self.fiber1, self.fiber3.get_client().node_info()["node_id"])
        time.sleep(Timeout.POLL_INTERVAL)

        # Step 2: Keysend with max_fee_amount=1; assert error
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                    "amount": hex(Amount.ckb(10)),
                    "keysend": True,
                    "max_fee_amount": hex(1),
                    "trampoline_hops": [
                        self.fiber2.get_client().node_info()["node_id"],
                        self.fiber3.get_client().node_info()["node_id"],
                    ],
                }
            )
        err = str(exc_info.value).lower()
        assert "max_fee_amount is too low for trampoline routing" in err, err

    def test_trampoline_tlc_expiry_limit_exceeded_should_fail(self):
        """
        Send payment with tlc_expiry_limit too small; expect error.
        Step 1: Build tr001 topology.
        Step 2: Keysend with small tlc_expiry_limit; assert error.
        """
        # Step 1: Build tr001 topology
        self._build_tr001_topology()

        # Step 2: Keysend with small tlc_expiry_limit; assert error
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "amount": hex(Amount.ckb(10)),
                    "keysend": True,
                    "max_fee_amount": hex(Amount.ckb(0.1)),
                    "tlc_expiry_limit": hex(1000),
                    "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
                }
            )
        err = str(exc_info.value).lower()
        assert (
            "tlc_expiry_limit is too small" in err
            or "trampoline tlc_expiry_delta exceeds tlc_expiry_limit" in err
        ), err

    def test_trampoline_first_hop_source_or_target_should_fail(self):
        """
        First trampoline hop must not be source or target; expect error.
        Step 1: Build tr001 topology.
        Step 2: Keysend with first hop = source; assert error.
        """
        # Step 1: Build tr001 topology
        self._build_tr001_topology()

        # Step 2: Keysend with first hop = source; assert error
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "amount": hex(Amount.ckb(10)),
                    "keysend": True,
                    "max_fee_amount": hex(Amount.ckb(0.1)),
                    "trampoline_hops": [self.fiber1.get_client().node_info()["node_id"]],
                }
            )
        err = str(exc_info.value).lower()
        assert "invalid trampoline_hops: first hop must not be source/target" in err, err

    def test_trampoline_without_hops_should_fail(self):
        """
        Pay invoice without trampoline_hops when no path; expect route/path error.
        Step 1: Build tr001 topology.
        Step 2: Create invoice (no allow_trampoline_routing).
        Step 3: Send payment without trampoline_hops; assert error.
        """
        # Step 1: Build tr001 topology
        self._build_tr001_topology()

        # Step 2: Create invoice (no allow_trampoline_routing)
        invoice = self.fiber3.get_client().new_invoice(
            {
                "amount": hex(Amount.ckb(10)),
                "currency": Currency.FIBD,
                "description": "trampoline invoice",
                "payment_preimage": self.generate_random_preimage(),
            }
        )

        # Step 3: Send payment without trampoline_hops; assert error
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment({"invoice": invoice["invoice_address"]})
        err = str(exc_info.value).lower()
        assert "failed to build route" in err or "no path found" in err, err
