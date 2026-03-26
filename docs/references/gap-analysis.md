# Fiber Test Coverage Gap Analysis

Complete gap analysis comparing Bitcoin LND integration tests with Fiber's current test coverage, plus Fiber-specific untested features identified from source code analysis.

## Table of Contents

- [Methodology](#methodology)
- [P0: Critical Gaps with Recommended Tests](#p0-critical-gaps)
- [P1: High Priority Gaps](#p1-high-priority-gaps)
- [P2: Medium Priority Gaps](#p2-medium-priority-gaps)
- [P3: Low Priority / Nice to Have](#p3-low-priority)
- [Fiber-Specific Untested Features](#fiber-specific-untested-features)
- [Existing Test Quality Issues](#existing-test-quality-issues)
- [Current Coverage Summary](#current-coverage-summary)

---

## Methodology

**LND source**: `lightningnetwork/lnd/itest/list_on_test.go` - 160+ integration test cases across 17 sub-categories (multihop force close, watchtower, psbt, channel backup, utxo selection, zero conf, channel fee policy, funding, send to route, channel force close, wallet, coop close, peer conn, etc.)

**Fiber source**: `fiber/fiber-lib/src/` - Rust source code analysis of all modules (channel.rs, payment.rs, network.rs, graph.rs, gossip.rs, invoice.rs, watchtower/, cch/, rpc/)

**Fiber tests**: `test_cases/fiber/devnet/` - 500+ test methods across 40+ directories

---

## P0: Critical Gaps

### 1. Cooperative Close with Pending TLCs

**LND**: `testCoopCloseWithHtlcs`, `testCoopCloseWithHtlcsWithRestart`
**Fiber**: `shutdown_channel/test_pending_tlc.py` - ALL CODE COMMENTED OUT
**Risk**: Funds locked or lost when closing channel with in-flight payments

```python
# Recommended: test_cases/fiber/devnet/shutdown_channel/test_coop_close_with_tlc.py

class TestCoopCloseWithTlc(FiberTest):
    def test_coop_close_with_pending_payment(self):
        """Close channel while payment is in-flight; payment should complete or be cleanly canceled."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        # Create hold invoice to keep TLC pending
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        invoice = self.fiber2.get_client().new_invoice({
            "amount": hex(10 * 100000000), "currency": "Fibd",
            "description": "hold", "payment_hash": payment_hash,
            "hash_algorithm": "sha256",
        })
        payment = self.fiber1.get_client().send_payment({"invoice": invoice["invoice_address"]})
        self.wait_invoice_state(self.fiber2, payment_hash, "Received")
        # Now try cooperative close with pending TLC
        channels = self.fiber1.get_client().list_channels({})
        self.fiber1.get_client().shutdown_channel({
            "channel_id": channels["channels"][0]["channel_id"], "force": False,
        })
        # Verify: channel should wait for TLC resolution or return error
        # Then settle invoice and verify close completes

    def test_coop_close_with_pending_tlc_restart(self):
        """Restart node during coop close with pending TLC."""
        # Similar setup, restart fiber1 during shutdown, verify recovery
```

### 2. Channel Update Tests

**LND**: `testUpdateChanStatus`, `testSendUpdateDisableChannel`, `testUpdateChannelPolicy*` (5+ tests)
**Fiber**: `update_channel/` directory has NO test files
**Risk**: Channel routing policy changes not verified

```python
# Recommended: test_cases/fiber/devnet/update_channel/test_update_channel.py

class TestUpdateChannel(FiberTest):
    def test_update_enabled_flag(self):
        """Disable and re-enable channel, verify routing behavior."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        channels = self.fiber1.get_client().list_channels({"peer_id": self.fiber2.get_peer_id()})
        channel_id = channels["channels"][0]["channel_id"]
        # Disable channel
        self.fiber1.get_client().update_channel({"channel_id": channel_id, "enabled": False})
        time.sleep(2)
        # Verify disabled in list_channels
        channels = self.fiber1.get_client().list_channels({"peer_id": self.fiber2.get_peer_id()})
        assert channels["channels"][0]["enabled"] == False
        # Verify payment fails through disabled channel (multi-hop)
        # Re-enable and verify payment succeeds

    def test_update_fee_rate(self):
        """Update fee rate, verify new fee applied to payments."""

    def test_update_tlc_expiry_delta(self):
        """Update TLC expiry delta, verify routing uses new value."""

    def test_update_tlc_min_value(self):
        """Update TLC min value, verify small payments rejected."""

    def test_update_nonexistent_channel(self):
        """Update non-existent channel_id, expect error."""

    def test_update_closed_channel(self):
        """Update already-closed channel, expect error."""

    def test_update_propagates_via_gossip(self):
        """Verify channel updates propagate to remote peers via gossip."""
```

### 3. Offline Payment Delivery

**LND**: `testSwitchOfflineDelivery`, `testSwitchOfflineDeliveryPersistence`, `testSwitchOfflineDeliveryOutgoingOffline`
**Fiber**: `send_payment/offline/` ALL commented out
**Risk**: Payments lost when intermediate nodes go offline

```python
# Recommended: test_cases/fiber/devnet/send_payment/offline/test_offline_delivery.py

class TestOfflineDelivery(FiberTest):
    def test_intermediate_node_offline_then_online(self):
        """A->B->C: B goes offline during payment, comes back, payment completes."""
        account3 = self.generate_account(1000)
        fiber3 = self.start_new_fiber(account3)
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 200 * 100000000)
        fiber3.connect_peer(self.fiber2)
        self.open_channel(self.fiber2, fiber3, 200 * 100000000, 200 * 100000000)
        time.sleep(3)
        # Stop fiber2 (intermediate)
        self.fiber2.stop()
        # Send payment (should fail or queue)
        # Restart fiber2
        self.fiber2.start()
        self.fiber2.connect_peer(self.fiber1)
        self.fiber2.connect_peer(fiber3)
        # Verify payment eventually completes or properly fails

    def test_receiver_offline_then_online(self):
        """Receiver goes offline, comes back, payment completes."""

    def test_sender_offline_after_sending(self):
        """Sender goes offline after initiating payment."""
```

### 4. Payment Error Propagation

**LND**: `testHtlcErrorPropagation`, `testSendToRouteErrorPropagation`
**Fiber**: No dedicated multi-hop error propagation test
**Risk**: Errors silently swallowed, funds stuck

```python
# Recommended: test_cases/fiber/devnet/send_payment/module/test_error_propagation.py

class TestErrorPropagation(FiberTest):
    def test_final_hop_error_propagates_to_sender(self):
        """A->B->C: C rejects payment, error propagates back to A with correct reason."""
        # Setup 3-node topology
        # Send payment that C will reject (e.g., wrong payment_hash)
        # Verify A gets specific error reason (not generic failure)

    def test_intermediate_hop_error_propagates(self):
        """A->B->C: B cannot forward (insufficient balance), error propagates to A."""

    def test_error_updates_network_graph(self):
        """When error received, sender updates local graph (disable channel, etc.)."""
```

### 5. Channel Reestablishment

**LND**: `testDataLossProtection`
**Fiber**: No channel reestablishment test after disconnect
**Risk**: State corruption after disconnection

```python
# Recommended: test_cases/fiber/devnet/connect_peer/test_channel_reestablish.py

class TestChannelReestablish(FiberTest):
    def test_reconnect_with_active_channel(self):
        """Disconnect and reconnect peers with active channel, verify channel still works."""
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        self.send_payment(self.fiber1, self.fiber2, 10 * 100000000)
        # Disconnect
        self.fiber1.get_client().disconnect_peer({"peer_id": self.fiber2.get_peer_id()})
        time.sleep(2)
        # Reconnect
        self.fiber1.connect_peer(self.fiber2)
        time.sleep(3)
        # Payment should still work
        self.send_payment(self.fiber1, self.fiber2, 10 * 100000000)

    def test_reconnect_with_stale_state(self):
        """Simulate node falling behind in commitment number, verify data loss protection."""
```

---

## P1: High Priority Gaps

### 6. Gossip Protocol Validation

**LND**: `testGraphTopologyNotifications`, `testNodeAnnouncement`, `testSelfNodeAnnouncementPersistence`
**Fiber source**: gossip.rs has complex message ordering, stale detection, cursor sync
**Current**: No dedicated gossip tests

```python
# Recommended tests:
# - test_gossip_channel_announcement_propagation: New channel announced to all nodes
# - test_gossip_channel_update_propagation: Fee change propagates to network
# - test_gossip_node_announcement_update: Node info change propagates
# - test_gossip_stale_message_rejected: Old messages discarded
# - test_gossip_after_reconnect: Missed messages synced on reconnect
```

### 7. Payment Retry Logic

**Fiber source**: DEFAULT_PAYMENT_TRY_LIMIT=5, DEFAULT_PAYMENT_MPP_ATTEMPT_TRY_LIMIT=3
**Current**: No explicit retry behavior test

```python
# Recommended tests:
# - test_payment_retries_on_transient_failure: Verify retry happens
# - test_payment_fails_after_max_retries: Verify gives up after limit
# - test_payment_retry_selects_different_path: Verify path rotation
# - test_mpp_attempt_retry_limit: Test MPP-specific retry limit
```

### 8. Max Pending Channels

**LND**: `testMaxPendingChannels`
**Current**: No test

```python
# - test_max_pending_channels: Open many channels simultaneously, verify limit
```

### 9. Channel Balance Accuracy

**LND**: `testChannelBalance`, `testChannelUnsettledBalance`
**Current**: Balance checked incidentally, no dedicated test

```python
# - test_channel_balance_after_payment: Exact balance accounting
# - test_channel_unsettled_balance_during_tlc: offered/received TLC tracking
# - test_channel_balance_after_partial_payment: Balance with fees
```

### 10. Connection Timeout

**LND**: `testNetworkConnectionTimeout`
**Current**: No timeout test

```python
# - test_connection_timeout_to_unreachable_peer: Verify timeout behavior
# - test_init_message_timeout: Verify peer dropped if no init message (CHECK_PEER_INIT_INTERVAL=20s)
```

### 11. Reject TLC / HTLC

**LND**: `testRejectHTLC`
**Current**: No explicit TLC rejection test

```python
# - test_reject_tlc_below_min_value: TLC below tlc_min_value rejected
# - test_reject_tlc_above_max_value: TLC above tlc_max_value rejected
# - test_reject_tlc_exceeds_max_in_flight: TLC count limit enforcement
# - test_reject_tlc_exceeds_value_in_flight: TLC value limit enforcement
```

---

## P2: Medium Priority Gaps

### 12. Revoked Close with Pending TLCs

**LND**: `testRevokedCloseRetributionRemoteHodl`
**Current**: `test_revert_tx.py` basic only
**Recommendation**: Test revoked close when there are pending TLCs on both sides.

### 13. Circuit/Payment Persistence

**LND**: `testSwitchCircuitPersistence`
**Current**: No test
**Recommendation**: Test that in-flight payment survives node restart and completes.

### 14. Payment Address Mismatch

**LND**: `testWrongPaymentAddr`
**Current**: No test
**Recommendation**: Send payment with wrong payment_secret/hash, verify proper rejection.

### 15. Funding Expiry Edge Cases

**LND**: `testFundingExpiryBlocksOnPending`, `testFundingManagerFundingTimeout`
**Current**: `test_funding_timeout.py` basic
**Recommendation**: Test various funding timeout scenarios (peer offline, slow confirmation).

### 16. Max Channel Size

**LND**: `testMaxChannelSize`
**Current**: No test
**Recommendation**: Test opening channel larger than maximum allowed.

### 17. Immediate Payment After Channel Open

**LND**: `testPaymentFollowingChannelOpen`
**Current**: Tests wait for CHANNEL_READY, but no immediate-after-open test
**Recommendation**: Send payment immediately after channel becomes ready.

### 18. Fee Estimation Enhancement

**LND**: `testEstimateRouteFee`
**Current**: `test_dry_run.py` basic
**Recommendation**: Multi-hop fee estimation, fee budget too low, fee budget exact boundary.

### 19. Async Bidirectional Payments

**LND**: `testBidirectionalAsyncPayments`
**Current**: `test_send_payment_each_other_2` partial
**Recommendation**: High-throughput concurrent bidirectional payment stress test.

---

## P3: Low Priority / Nice to Have

| Gap | LND Test | Priority | Notes |
|-----|----------|----------|-------|
| Reorg handling | `testReorgNotifications`, `testPendingChannelAfterReorg` | P3 | CKB reorg handling |
| Payment tracking | `testTrackPayments` | P3 | Real-time payment tracking |
| Custom messages | `testCustomMessage` | P3 | P2P custom message sending |
| Blinded routes | `testBlindedRoute*` (10+ tests) | P3 | Not implemented in Fiber yet |
| Quiescence | `testQuiescence` | P3 | Protocol feature |
| Bump fee | `testBumpFee*` | P3 | N/A for CKB (different fee model) |
| PSBT funding | `testPsbt*` | P3 | N/A for CKB |
| Anchor outputs | `testAnchor*` | P3 | N/A for CKB |
| Zero-conf channels | `testZeroConfChannelOpen` | P3 | Not implemented in Fiber |

---

## Fiber-Specific Untested Features

### From channel.rs

| Feature | Constant/Logic | Test Status |
|---------|---------------|-------------|
| Max TLC number enforcement during payment | max 125 per channel, system max 253 | Only open_channel param test, no enforcement during `send_payment` |
| TLC waiting ACK timeout | 30 seconds | No test |
| Commitment delay validation | 1-84 epochs | No range boundary test |
| TLC expiry >= 2/3 commitment_delay | Validation rule | No test |
| Retryable TLC operations | 100ms interval retry | No test |
| One-way channel restrictions | Direction enforcement | ✅ Covered in `one_way/` |
| Reserved CKB amount calculations | Dynamic based on TLC count | No dedicated test |

### From payment.rs

| Feature | Constant/Logic | Test Status |
|---------|---------------|-------------|
| Trampoline max hops | MAX_TRAMPOLINE_HOPS_LIMIT = 5 | No boundary test |
| Trampoline no duplicates | Hop validation | No test |
| Trampoline + MPP restriction | Only 1 trampoline hop with MPP | No test |
| Custom records max size | 2048 bytes total | `test_custom_records.py` tests oversized values but not exact boundary |
| Custom records key range | 0-65535 | No key range boundary test |
| max_parts limit | PAYMENT_MAX_PARTS_LIMIT | `test_max_parts.py` is EMPTY |
| Payment session retry from Failed | Only Failed status can retry | No test |
| Amount + max_fee overflow | Overflow check | No test |
| Keysend validation | No invoice + requires preimage | Partial coverage |
| DEFAULT_MAX_FEE_RATE = 5 (0.5%) | Fee rate default | No test |

### From network.rs

| Feature | Constant/Logic | Test Status |
|---------|---------------|-------------|
| Chain hash mismatch | Peer rejected if different chain | No test |
| Init message timeout | CHECK_PEER_INIT_INTERVAL = 20s | No test |
| Max service protocol data | 130 KB limit | No test |
| Max custom records size | 2 KB network limit | No test |
| CKB tx tracing confirmations | 4 confirmations | No test |
| Maintaining connections interval | 1200s | No test |

### From gossip.rs

| Feature | Constant/Logic | Test Status |
|---------|---------------|-------------|
| Active gossip sync | Pull on connect | No test |
| Passive gossip sync | Subscribe to updates | No test |
| Stale message duration | SOFT_BROADCAST_MESSAGES_CONSIDERED_STALE_DURATION | No test |
| Message dependency ordering | Process in dependency order | No test |
| Cursor-based pagination | Incremental sync | No test |

### From cch/

| Feature | Constant/Logic | Test Status |
|---------|---------------|-------------|
| Order expiry | DEFAULT_ORDER_EXPIRY_DELTA_SECONDS = 36h | No test |
| Order pruning | PRUNE_DELAY_SECONDS = 21 days | No test |
| Fee calculation | base_fee_sats + fee_rate_per_million_sats | No test |
| Invoice expiry validation | > min_outgoing_invoice_expiry_delta | No test |
| CKB invoice hash algorithm | Must be SHA256 for CCH | No test |
| BTC final CLTV validation | < CKB final TLC / 2 | No test |
| Amount too small/large | Boundary validation | No test |

### From rpc/biscuit.rs

| Feature | Test Status |
|---------|-------------|
| Time-based token validation | No test |
| Token revocation list | No test |
| Node ID extraction from token | No test |
| Per-method permission granularity | No test |

---

## Existing Test Quality Issues

### Empty/Commented Test Files

| File | Status |
|------|--------|
| `shutdown_channel/test_shutdown_channel.py` | Class exists, NO test methods |
| `shutdown_channel/test_pending_tlc.py` | ALL code commented out |
| `shutdown_channel/test_mutil_to_one.py` | ALL code commented out |
| `send_payment/offline/test_disconnect1.py` | ALL code commented out |
| `send_payment/offline/test_send_payment_with_stop.py` | Class exists, NO test methods |
| `send_payment/mpp/test_mpp_force_shutdown.py` | ALL code commented out |
| `send_payment/params/test_max_parts.py` | Test method is `pass` |
| `accept_channel/test_tlc_expiry_delta.py` | Class exists, NO test methods |
| `new_invoice/test_fallback_address.py` | Class exists, NO test methods |
| `wasm/test_wasm.py` | ALL methods commented out |
| `update_channel/` | Directory has NO test files |

### Skipped Tests (May Need Revisiting)

| File | Test | Skip Reason |
|------|------|-------------|
| `settle_invoice/test_settle_invoice.py` | `test_settle_expired_hold_invoice` | Issue #1029 |
| `settle_invoice/test_settle_invoice.py` | `test_settle_expired_invoice_should_fail` | Skipped |
| `send_payment/mpp/test_mpp_bench.py` | `test_bench_self*` | Skipped |
| `backup/test_backup.py` | `test_backup3` | Instability |
| `trampoline_routing/` | `test_trampoline_invoice_sha256` | xfail, pending fix |
| `watch_tower_wit_tlc/` | 5 TLC expiry tests | Skipped |

---

## Current Coverage Summary

### Well-Covered Areas ✅

| Area | Tests | Quality |
|------|-------|---------|
| open_channel parameters | 19 files, 70+ tests | Excellent - thorough param validation |
| send_payment (basic) | 20+ files, 100+ tests | Good - covers keysend, invoice, multi-hop |
| Watchtower (force close) | 4 files, 30+ tests (CKB + UDT) | Excellent - comprehensive scenarios |
| Invoice lifecycle | 10+ files, 40+ tests | Good - create, cancel, settle, hold |
| Graph queries | 2 files, 10+ tests | Good - pagination, consistency |
| Trampoline routing | 1 file, 8 tests | Good - success and failure scenarios |
| One-way channels | 1 file, 7 tests | Good - direction enforcement |
| Watchtower with TLC | 5+ files, 20+ tests | Good - pending TLC handling |
| MPP and Atomic MPP | 5+ files, 10+ tests | Moderate - basic flows covered |

### Partially Covered Areas ⚠️

| Area | Tests | Gap |
|------|-------|-----|
| Channel shutdown | 1 empty class | No cooperative close tests |
| Channel update | 0 tests | No tests at all |
| Offline delivery | 0 active tests | All commented out |
| Payment retry | Implicit (in helpers) | No explicit behavior test |
| Balance accounting | Incidental checks | No dedicated tests |
| Error propagation | Some error assertions | No multi-hop error flow |
| Gossip sync | Indirect (via graph) | No protocol-level tests |
| CCH | Basic flow only | No edge cases |

### Not Covered Areas ❌

| Area | Tests |
|------|-------|
| Channel reestablishment | 0 |
| Connection timeout | 0 |
| TLC enforcement during payment (count/value limits) | 0 |
| Payment max_parts limit | 0 (empty test) |
| Gossip stale message handling | 0 |
| Circuit persistence through restart | 0 |
| Payment address mismatch | 0 |
| Max channel size | 0 |
| CCH order expiry/pruning | 0 |
| Biscuit time-based auth | 0 |
| Trampoline + MPP constraint | 0 |
