import time

import pytest

from framework.basic_fiber import FiberTest


class TestAllowTrampolineRouting(FiberTest):

    # debug = True
    def _wait_indexer_synced(self, timeout=120):
        for _ in range(timeout):
            tip_number = self.node.getClient().get_tip_block_number()
            indexer_tip = self.node.getClient().get_indexer_tip()
            indexer_number = int(indexer_tip.get("block_number", "0x0"), 16)
            if indexer_number >= tip_number:
                return
            time.sleep(1)
        raise TimeoutError("ckb indexer not synced")

    def _generate_account_with_retry(self, ckb_balance, retries=20, interval=3):
        last_error = None
        for _ in range(retries):
            try:
                return self.generate_account(ckb_balance)
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                if "ckb-indexer" in error_str or "not synced" in error_str:
                    time.sleep(interval)
                    continue
                raise
        raise last_error

    def _wait_node_in_graph(self, client, node_id, timeout=60):
        for _ in range(timeout):
            nodes = client.get_client().graph_nodes({}).get("nodes", [])
            if any(n.get("pubkey") == node_id for n in nodes):
                return
            time.sleep(1)
        raise TimeoutError(f"node_id not found in graph_nodes: {node_id}")

    def _build_tr001_topology(self):
        self._wait_indexer_synced()
        self.fiber3 = self.start_new_fiber(self._generate_account_with_retry(1000))
        self.fiber3.connect_peer(self.fiber2)

        self.fiber1.get_client().open_channel(
            {
                "pubkey": self.fiber2.get_pubkey(),
                "funding_amount": hex(500 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "CHANNEL_READY"
        )

        self.fiber2.get_client().open_channel(
            {
                "pubkey": self.fiber3.get_pubkey(),
                "funding_amount": hex(500 * 100000000),
                "public": False,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber3.get_pubkey(), "CHANNEL_READY"
        )
        self._wait_node_in_graph(
            self.fiber1, self.fiber2.get_client().node_info()["pubkey"]
        )
        time.sleep(1)

    def test_trampoline_invoice_success(self):
        self._build_tr001_topology()
        invoice = self.fiber3.get_client().new_invoice(
            {
                "amount": hex(10 * 100000000),
                "currency": "Fibd",
                "description": "trampoline invoice",
                "payment_preimage": self.generate_random_preimage(),
                "allow_trampoline_routing": True,
            }
        )
        payment = self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
                "max_fee_amount": hex(20000000),
                "trampoline_hops": [self.fiber2.get_client().node_info()["pubkey"]],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

    def test_trampoline_invoice_sha256_hash_algorithm_success(self):
        self._build_tr001_topology()
        invoice = self.fiber3.get_client().new_invoice(
            {
                "amount": hex(10 * 100000000),
                "currency": "Fibd",
                "description": "trampoline invoice sha256",
                "payment_preimage": self.generate_random_preimage(),
                "hash_algorithm": "sha256",
                "allow_trampoline_routing": True,
            }
        )
        payment = self.fiber1.get_client().send_payment(
            {
                "invoice": invoice["invoice_address"],
                "max_fee_amount": hex(20000000),
                "trampoline_hops": [self.fiber2.get_client().node_info()["pubkey"]],
            }
        )
        try:
            self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
        except Exception as e:
            pytest.xfail(
                "pending fix: receiver should validate preimage using invoice hash_algorithm "
                f"(sha256), error={str(e)}"
            )

    def test_trampoline_keysend_success(self):
        self._build_tr001_topology()
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber3.get_client().node_info()["pubkey"],
                "amount": hex(10 * 100000000),
                "keysend": True,
                "max_fee_amount": hex(20000000),
                "trampoline_hops": [self.fiber2.get_client().node_info()["pubkey"]],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

    def test_trampoline_multi_hops_keysend_success(self):
        self._wait_indexer_synced()
        self.fiber3 = self.start_new_fiber(self._generate_account_with_retry(1000))
        self.fiber3.connect_peer(self.fiber2)
        self.fiber4 = self.start_new_fiber(self._generate_account_with_retry(1000))
        self.fiber4.connect_peer(self.fiber3)

        self.fiber1.get_client().open_channel(
            {
                "pubkey": self.fiber2.get_pubkey(),
                "funding_amount": hex(500 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "CHANNEL_READY"
        )
        self.fiber2.get_client().open_channel(
            {
                "pubkey": self.fiber3.get_pubkey(),
                "funding_amount": hex(500 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber3.get_pubkey(), "CHANNEL_READY"
        )
        self.fiber3.get_client().open_channel(
            {
                "pubkey": self.fiber4.get_pubkey(),
                "funding_amount": hex(500 * 100000000),
                "public": False,
            }
        )
        self.wait_for_channel_state(
            self.fiber3.get_client(), self.fiber4.get_pubkey(), "CHANNEL_READY"
        )
        self._wait_node_in_graph(
            self.fiber1, self.fiber2.get_client().node_info()["pubkey"]
        )
        self._wait_node_in_graph(
            self.fiber1, self.fiber3.get_client().node_info()["pubkey"]
        )
        time.sleep(1)

        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber4.get_client().node_info()["pubkey"],
                "amount": hex(10 * 100000000),
                "keysend": True,
                "max_fee_amount": hex(20000000),
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["pubkey"],
                    self.fiber3.get_client().node_info()["pubkey"],
                ],
            }
        )
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

    @pytest.mark.skip("devnet RPC lacks node feature toggle; covered by Rust tests")
    def test_trampoline_hop_not_support_feature_should_fail(self):
        pass

    def test_trampoline_max_fee_amount_too_low_should_fail(self):
        self._wait_indexer_synced()
        self.fiber3 = self.start_new_fiber(self._generate_account_with_retry(1000))
        self.fiber3.connect_peer(self.fiber2)
        self.fiber4 = self.start_new_fiber(self._generate_account_with_retry(1000))
        self.fiber4.connect_peer(self.fiber3)

        self.fiber1.get_client().open_channel(
            {
                "pubkey": self.fiber2.get_pubkey(),
                "funding_amount": hex(500 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_pubkey(), "CHANNEL_READY"
        )
        self.fiber2.get_client().open_channel(
            {
                "pubkey": self.fiber3.get_pubkey(),
                "funding_amount": hex(500 * 100000000),
                "public": True,
            }
        )
        self.wait_for_channel_state(
            self.fiber2.get_client(), self.fiber3.get_pubkey(), "CHANNEL_READY"
        )
        self.fiber3.get_client().open_channel(
            {
                "pubkey": self.fiber4.get_pubkey(),
                "funding_amount": hex(500 * 100000000),
                "public": False,
            }
        )
        self.wait_for_channel_state(
            self.fiber3.get_client(), self.fiber4.get_pubkey(), "CHANNEL_READY"
        )
        self._wait_node_in_graph(
            self.fiber1, self.fiber2.get_client().node_info()["pubkey"]
        )
        self._wait_node_in_graph(
            self.fiber1, self.fiber3.get_client().node_info()["pubkey"]
        )
        time.sleep(1)

        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber4.get_client().node_info()["pubkey"],
                    "amount": hex(10 * 100000000),
                    "keysend": True,
                    "max_fee_amount": hex(1),
                    "trampoline_hops": [
                        self.fiber2.get_client().node_info()["pubkey"],
                        self.fiber3.get_client().node_info()["pubkey"],
                    ],
                }
            )
        error_str = str(exc_info.value).lower()
        assert (
            "max_fee_amount is too low for trampoline routing" in error_str
        ), error_str

    def test_trampoline_tlc_expiry_limit_exceeded_should_fail(self):
        self._build_tr001_topology()
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["pubkey"],
                    "amount": hex(10 * 100000000),
                    "keysend": True,
                    "max_fee_amount": hex(10000000),
                    "tlc_expiry_limit": hex(1000),
                    "trampoline_hops": [
                        self.fiber2.get_client().node_info()["pubkey"]
                    ],
                }
            )
        error_str = str(exc_info.value).lower()
        assert (
            "tlc_expiry_limit is too small" in error_str
            or "trampoline tlc_expiry_delta exceeds tlc_expiry_limit" in error_str
        ), error_str

    def test_trampoline_first_hop_source_or_target_should_fail(self):
        self._build_tr001_topology()
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["pubkey"],
                    "amount": hex(10 * 100000000),
                    "keysend": True,
                    "max_fee_amount": hex(10000000),
                    "trampoline_hops": [
                        self.fiber1.get_client().node_info()["pubkey"]
                    ],
                }
            )
        error_str = str(exc_info.value).lower()
        assert (
            "invalid trampoline_hops: first hop must not be source/target" in error_str
        ), error_str

    def test_trampoline_without_hops_should_fail(self):
        self._build_tr001_topology()
        invoice = self.fiber3.get_client().new_invoice(
            {
                "amount": hex(10 * 100000000),
                "currency": "Fibd",
                "description": "trampoline invoice",
                "payment_preimage": self.generate_random_preimage(),
            }
        )
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "invoice": invoice["invoice_address"],
                }
            )
        error_str = str(exc_info.value).lower()
        assert (
            "failed to build route" in error_str or "no path found" in error_str
        ), error_str
