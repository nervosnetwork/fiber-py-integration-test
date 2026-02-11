# Fiber Test Patterns Reference

Comprehensive patterns for writing integration tests in the Fiber test suite.

## Table of Contents

- [Test File Organization](#test-file-organization)
- [Channel Lifecycle Tests](#channel-lifecycle-tests)
- [Payment Tests](#payment-tests)
- [Invoice Tests](#invoice-tests)
- [UDT Channel Tests](#udt-channel-tests)
- [Multi-Path Payment Tests](#multi-path-payment-tests)
- [Watchtower Tests](#watchtower-tests)
- [Error Testing Patterns](#error-testing-patterns)
- [Balance Verification](#balance-verification)
- [Time Manipulation Tests](#time-manipulation-tests)
- [Node Restart Tests](#node-restart-tests)
- [Cross-Chain Hub Tests](#cross-chain-hub-tests)
- [CI/CD Pipeline](#cicd-pipeline)

---

## Test File Organization

### Directory Structure

```
test_cases/fiber/devnet/<feature>/<test_file>.py
```

### Naming Convention

- Test files: `test_<feature_aspect>.py`
- Test classes: `class Test<Feature>(FiberTest)` or `class <FeatureName>(FiberTest)`
- Test methods: `def test_<scenario_description>(self)`

### Class-Level Config Override

```python
class TestMyFeature(FiberTest):
    # Override startup config for all tests in this class
    start_fiber_config = {
        "fiber_auto_accept_amount": "0",
        "fiber_watchtower_check_interval_seconds": 5,
    }
    # Override Fiber version
    # fiber_version = FiberConfigPath.V0_3_0
```

---

## Channel Lifecycle Tests

### Open Channel with Auto-Accept

When funding exceeds peer's auto-accept threshold:

```python
def test_open_channel_auto_accept(self):
    self.fiber1.get_client().open_channel({
        "peer_id": self.fiber2.get_peer_id(),
        "funding_amount": hex(200 * 100000000),
        "public": True,
    })
    channel_id = self.wait_for_channel_state(
        self.fiber1.get_client(),
        self.fiber2.get_peer_id(),
        "CHANNEL_READY",
    )
    # Verify channel properties
    channels = self.fiber1.get_client().list_channels(
        {"peer_id": self.fiber2.get_peer_id()}
    )
    assert len(channels["channels"]) == 1
    assert channels["channels"][0]["state"]["state_name"] == "CHANNEL_READY"
```

### Open Channel with Manual Accept

When funding is below auto-accept threshold:

```python
class TestManualAccept(FiberTest):
    start_fiber_config = {"fiber_auto_accept_amount": "0"}

    def test_open_channel_manual_accept(self):
        temp = self.fiber1.get_client().open_channel({
            "peer_id": self.fiber2.get_peer_id(),
            "funding_amount": hex(200 * 100000000),
            "public": True,
        })
        time.sleep(1)
        self.fiber2.get_client().accept_channel({
            "temporary_channel_id": temp["temporary_channel_id"],
            "funding_amount": hex(100 * 100000000),
        })
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            "CHANNEL_READY",
        )
```

### Shutdown Channel (Cooperative)

```python
def test_cooperative_shutdown(self):
    self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
    channels = self.fiber1.get_client().list_channels(
        {"peer_id": self.fiber2.get_peer_id()}
    )
    channel_id = channels["channels"][0]["channel_id"]

    self.fiber1.get_client().shutdown_channel({
        "channel_id": channel_id,
        "force": False,
    })
    # Wait for close tx to be committed
    tx_hash = self.wait_and_check_tx_pool_fee(1000, False)
    self.Miner.miner_until_tx_committed(self.node, tx_hash)
```

### Shutdown Channel (Force Close)

```python
def test_force_close(self):
    self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
    channels = self.fiber1.get_client().list_channels({})
    channel_id = channels["channels"][0]["channel_id"]

    self.fiber1.get_client().shutdown_channel({
        "channel_id": channel_id,
        "force": True,
    })
    tx = self.wait_and_check_tx_pool_fee(1000, False)
    self.Miner.miner_until_tx_committed(self.node, tx)

    # Generate epochs for timeout period
    self.node.getClient().generate_epochs("0x1", 0)

    # Wait for settlement tx
    settle_tx = self.wait_and_check_tx_pool_fee(1000, False, 1000)
    self.Miner.miner_until_tx_committed(self.node, settle_tx)
```

### Using open_channel Helper

The helper method handles balance distribution:

```python
def test_with_helper(self):
    # Opens channel with fiber1 having 200 CKB and fiber2 having 100 CKB
    self.open_channel(
        self.fiber1, self.fiber2,
        fiber1_balance=200 * 100000000,
        fiber2_balance=100 * 100000000,
        fiber1_fee=1000,     # 0.1% fee
        fiber2_fee=1000,     # 0.1% fee
        udt=None,            # CKB channel (or pass UDT script)
    )
```

---

## Payment Tests

### Keysend Payment

```python
def test_keysend(self):
    self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 0)
    payment_hash = self.send_payment(self.fiber1, self.fiber2, 10 * 100000000)
    # Verify payment
    result = self.fiber1.get_client().get_payment({"payment_hash": payment_hash})
    assert result["status"] == "Success"
```

### Invoice Payment

```python
def test_invoice_payment(self):
    self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 0)
    payment_hash = self.send_invoice_payment(
        self.fiber1, self.fiber2, 10 * 100000000
    )
    result = self.fiber1.get_client().get_payment({"payment_hash": payment_hash})
    assert result["status"] == "Success"
```

### Multi-Hop Payment (A → B → C)

```python
def test_multi_hop(self):
    account3 = self.generate_account(1000)
    fiber3 = self.start_new_fiber(account3)

    # Topology: fiber1 -- fiber2 -- fiber3
    self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 200 * 100000000)
    fiber3.connect_peer(self.fiber2)
    time.sleep(1)
    self.open_channel(self.fiber2, fiber3, 200 * 100000000, 200 * 100000000)
    time.sleep(3)  # Wait for gossip propagation

    # Payment fiber1 → fiber3 (routed through fiber2)
    payment_hash = self.send_payment(self.fiber1, fiber3, 10 * 100000000)
    assert self.fiber1.get_client().get_payment(
        {"payment_hash": payment_hash}
    )["status"] == "Success"
```

### Dry Run Payment

```python
def test_dry_run(self):
    self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 0)
    payment = self.fiber1.get_client().send_payment({
        "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
        "amount": hex(10 * 100000000),
        "keysend": True,
        "dry_run": True,
    })
    # Dry run returns route info but doesn't execute
    assert payment is not None
```

### Self-Payment (Circular Route)

```python
def test_self_payment(self):
    account3 = self.generate_account(1000)
    fiber3 = self.start_new_fiber(account3)

    # A -- B -- C -- A (circular)
    self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 200 * 100000000)
    fiber3.connect_peer(self.fiber2)
    self.open_channel(self.fiber2, fiber3, 200 * 100000000, 200 * 100000000)
    fiber3.connect_peer(self.fiber1)
    self.open_channel(fiber3, self.fiber1, 200 * 100000000, 200 * 100000000)
    time.sleep(3)

    payment = self.fiber1.get_client().send_payment({
        "target_pubkey": self.fiber1.get_client().node_info()["node_id"],
        "amount": hex(1 * 100000000),
        "keysend": True,
        "allow_self_payment": True,
    })
    self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
```

---

## Invoice Tests

### Standard Invoice

```python
def test_standard_invoice(self):
    self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 0)

    preimage = self.generate_random_preimage()
    invoice = self.fiber2.get_client().new_invoice({
        "amount": hex(10 * 100000000),
        "currency": "Fibd",
        "description": "test invoice",
        "payment_preimage": preimage,
        "hash_algorithm": "sha256",
    })

    payment = self.fiber1.get_client().send_payment({
        "invoice": invoice["invoice_address"],
    })
    self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

    # Verify invoice paid
    inv = self.fiber2.get_client().get_invoice(
        {"payment_hash": payment["payment_hash"]}
    )
    assert inv["status"] == "Paid"
```

### Hold Invoice with Settle

```python
import hashlib

def sha256_hex(preimage_hex: str) -> str:
    raw = bytes.fromhex(preimage_hex.replace("0x", ""))
    return "0x" + hashlib.sha256(raw).hexdigest()

def test_hold_invoice(self):
    self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 0)

    preimage = self.generate_random_preimage()
    payment_hash = sha256_hex(preimage)

    # Create hold invoice (only hash, no preimage)
    invoice = self.fiber2.get_client().new_invoice({
        "amount": hex(1 * 100000000),
        "currency": "Fibd",
        "description": "hold invoice",
        "payment_hash": payment_hash,
        "hash_algorithm": "sha256",
    })

    # Send payment - held at receiver
    payment = self.fiber1.get_client().send_payment({
        "invoice": invoice["invoice_address"],
    })
    self.wait_invoice_state(self.fiber2, payment_hash, "Received")

    # Settle with preimage
    self.fiber2.get_client().settle_invoice({
        "payment_hash": payment_hash,
        "payment_preimage": preimage,
    })
    self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
    inv = self.fiber2.get_client().get_invoice({"payment_hash": payment_hash})
    assert inv["status"] == "Paid"
```

### Cancel Invoice

```python
def test_cancel_invoice(self):
    preimage = self.generate_random_preimage()
    invoice = self.fiber1.get_client().new_invoice({
        "amount": hex(10 * 100000000),
        "currency": "Fibd",
        "description": "will cancel",
        "payment_preimage": preimage,
        "hash_algorithm": "sha256",
    })
    parsed = self.fiber1.get_client().parse_invoice(
        {"invoice": invoice["invoice_address"]}
    )
    payment_hash = parsed["invoice"]["data"]["payment_hash"]

    self.fiber1.get_client().cancel_invoice({"payment_hash": payment_hash})
    inv = self.fiber1.get_client().get_invoice({"payment_hash": payment_hash})
    assert inv["status"] == "Cancelled"
```

---

## UDT Channel Tests

### Open UDT Channel

```python
def test_udt_channel(self):
    udt_script = self.get_account_udt_script(self.fiber1.account_private)

    self.fiber1.get_client().open_channel({
        "peer_id": self.fiber2.get_peer_id(),
        "funding_amount": hex(200 * 100000000),
        "public": True,
        "funding_udt_type_script": udt_script,
    })
    self.wait_for_channel_state(
        self.fiber1.get_client(), self.fiber2.get_peer_id(), "CHANNEL_READY"
    )
```

### UDT Payment

```python
def test_udt_payment(self):
    udt_script = self.get_account_udt_script(self.fiber1.account_private)
    self.open_channel(
        self.fiber1, self.fiber2,
        200 * 100000000, 100 * 100000000,
        udt=udt_script,
    )
    self.send_payment(self.fiber1, self.fiber2, 10 * 100000000, udt=udt_script)
```

---

## Multi-Path Payment Tests

### MPP with Invoice

```python
def test_mpp(self):
    # Create multiple channels for parallel paths
    account3 = self.generate_account(1000, self.fiber1.account_private)
    fiber3 = self.start_new_fiber(account3)

    # fiber1 -- fiber2 -- fiber3 (path 1)
    # fiber1 -- fiber3 (path 2, direct)
    self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 200 * 100000000)
    fiber3.connect_peer(self.fiber2)
    self.open_channel(self.fiber2, fiber3, 200 * 100000000, 200 * 100000000)
    fiber3.connect_peer(self.fiber1)
    self.open_channel(self.fiber1, fiber3, 200 * 100000000, 200 * 100000000)
    time.sleep(3)

    # Invoice payment with MPP enabled
    payment_hash = self.send_invoice_payment(
        self.fiber1, fiber3, 300 * 100000000,  # Larger than single channel capacity
        other_options={"allow_mpp": True},
    )
```

### Atomic MPP

```python
def test_atomic_mpp(self):
    # ... setup multi-path topology ...
    payment_hash = self.send_invoice_payment(
        self.fiber1, fiber3, 300 * 100000000,
        other_options={"allow_atomic_mpp": True},
    )
```

---

## Watchtower Tests

### Force Close with Watchtower

```python
class TestWatchTower(FiberTest):
    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 5}

    def test_watchtower_detects_old_state(self):
        before_balances = self.get_fibers_balance()

        self.fiber1.get_client().open_channel({
            "peer_id": self.fiber2.get_peer_id(),
            "funding_amount": hex(200 * 100000000),
            "public": True,
        })
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), "CHANNEL_READY"
        )

        # Force close
        channels = self.fiber1.get_client().list_channels({})
        self.fiber1.get_client().shutdown_channel({
            "channel_id": channels["channels"][0]["channel_id"],
            "force": True,
        })

        # Commit force-close tx
        tx = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx)
        for i in range(5):
            self.Miner.miner_with_version(self.node, "0x0")

        # Stop one node
        self.fiber1.stop()

        # Generate epochs for dispute timeout
        self.node.getClient().generate_epochs("0x1", 0)

        # Watchtower on fiber2 should create settlement tx
        settle_tx = self.wait_and_check_tx_pool_fee(1000, False, 1000)
        self.Miner.miner_until_tx_committed(self.node, settle_tx)

        # Verify settlement
        tx_message = self.get_tx_message(settle_tx)
        print("Settlement tx:", tx_message)
```

---

## Error Testing Patterns

### Expected RPC Error

```python
def test_invalid_parameter(self):
    with pytest.raises(Exception) as exc_info:
        self.fiber1.get_client().open_channel({
            "peer_id": self.fiber2.get_peer_id(),
            "funding_amount": hex(0),
            "public": True,
        })
    expected_error_message = "should be greater than or equal to"
    assert expected_error_message in exc_info.value.args[0], (
        f"Expected '{expected_error_message}' not found in '{exc_info.value.args[0]}'"
    )
```

### Payment Failure

```python
def test_payment_should_fail(self):
    self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 0)
    # Send more than available
    payment = self.fiber1.get_client().send_payment({
        "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
        "amount": hex(300 * 100000000),  # More than channel balance
        "keysend": True,
    })
    self.wait_payment_state(self.fiber1, payment["payment_hash"], "Failed")
```

---

## Balance Verification

### Track Balance Changes

```python
def test_balance_accounting(self):
    before_balances = self.get_fibers_balance()

    self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
    self.send_payment(self.fiber1, self.fiber2, 50 * 100000000)

    after_balances = self.get_fibers_balance()
    changes = self.get_balance_change(before_balances, after_balances)
    # changes[i] = {"ckb": delta_ckb, "udt": delta_udt}
```

### Verify Channel Balances

```python
def test_channel_balance(self):
    self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
    channels = self.fiber1.get_client().list_channels(
        {"peer_id": self.fiber2.get_peer_id()}
    )
    ch = channels["channels"][0]
    local_balance = int(ch["local_balance"], 16)
    remote_balance = int(ch["remote_balance"], 16)
    assert local_balance == 200 * 100000000
    assert remote_balance == 100 * 100000000
```

---

## Time Manipulation Tests

For testing TLC expiry, invoice expiry, etc.:

```python
from framework.util import change_time, restore_time

def test_time_based_expiry(self):
    try:
        # Advance system time by N hours
        change_time(2)  # +2 hours

        # Generate blocks with new time
        self.add_time_and_generate_epoch(1, 1)

        # ... perform time-sensitive operations ...
    finally:
        # Always restore time
        self.restore_time()
```

---

## Node Restart Tests

```python
def test_payment_after_restart(self):
    self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)

    # Stop and restart fiber1
    self.fiber1.stop()
    time.sleep(2)
    self.fiber1.start()
    self.fiber1.connect_peer(self.fiber2)
    time.sleep(3)

    # Payment should still work
    self.send_payment(self.fiber1, self.fiber2, 10 * 100000000)
```

---

## Cross-Chain Hub Tests

Requires `FiberCchTest` base class:

```python
from framework.basic_fiber_with_cch import FiberCchTest

class TestCCH(FiberCchTest):
    def test_send_btc_via_fiber(self):
        # Setup includes BTC node + LND nodes
        # ... cross-chain payment flow ...
        order = self.fiber1.get_client().send_btc({
            "btc_pay_req": lnd_invoice,
        })
```

---

## CI/CD Pipeline

### GitHub Actions Structure

```
fiber.yml (main CI):
├── prepare (build Fiber, create artifacts)
└── parallel test jobs:
    ├── fiber_test_open_channel
    ├── fiber_test_send_payment_module_offline
    ├── fiber_test_send_payment_params_path
    ├── fiber_test_shutdown_channel_update_channel
    ├── fiber_test_watch_tower
    ├── fiber_test_send_payment_mpp
    ├── fiber_test_cch
    └── ... (13+ parallel jobs)
```

### Makefile Targets

```bash
make prepare              # Setup environment
make fiber_test           # Run all devnet tests
make fiber_testnet_test   # Run testnet tests
make fiber_mainnet_test   # Run mainnet tests
```

### Test Report

On failure, HTML reports are saved under `report/` directory with node logs for debugging.

---

## Constants Reference

```python
from framework.config import DEFAULT_MIN_DEPOSIT_CKB  # 99 * 100000000 (99 CKB)

# Currencies
"Fibd"   # devnet
"Fibt"   # testnet
"Fib"    # mainnet

# Channel states
"NEGOTIATING_FUNDING"
"COLLABORATING_FUNDING_TX"
"SIGNING_COMMITMENT"
"AWAITING_TX_SIGNATURES"
"AWAITING_CHANNEL_READY"
"CHANNEL_READY"
"SHUTTING_DOWN"
"CLOSED"

# Payment states
"Created"
"Inflight"
"Success"
"Failed"

# Invoice states
"Open"
"Received"
"Paid"
"Cancelled"
"Expired"
```
