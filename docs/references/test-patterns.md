# Fiber Test Patterns Reference

## Channel Lifecycle Patterns

### Open with Auto-Accept (funding > threshold)

```python
self.fiber1.get_client().open_channel({
    "pubkey": self.fiber2.get_pubkey(),
    "funding_amount": hex(200 * 100000000),
    "public": True,
})
self.wait_for_channel_state(self.fiber1.get_client(), self.fiber2.get_pubkey(), "CHANNEL_READY")
```

### Open with Manual Accept (low funding or auto_accept=0)

```python
class TestManualAccept(FiberTest):
    start_fiber_config = {"fiber_auto_accept_amount": "0"}

    def test_manual(self):
        temp = self.fiber1.get_client().open_channel({...})
        time.sleep(1)
        self.fiber2.get_client().accept_channel({
            "temporary_channel_id": temp["temporary_channel_id"],
            "funding_amount": hex(100 * 100000000),
        })
        self.wait_for_channel_state(...)
```

### Force Close + Watchtower Settlement

```python
class TestForceClose(FiberTest):
    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 5}

    def test_force_close(self):
        self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000)
        channels = self.fiber1.get_client().list_channels({})
        self.fiber1.get_client().shutdown_channel({"channel_id": channels["channels"][0]["channel_id"], "force": True})
        tx = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx)
        self.node.getClient().generate_epochs("0x1", 0)
        settle_tx = self.wait_and_check_tx_pool_fee(1000, False, 1000)
        self.Miner.miner_until_tx_committed(self.node, settle_tx)
```

## Multi-Node Topology Pattern (FiberTest)

```python
def test_multi_hop(self):
    account3 = self.generate_account(1000)
    fiber3 = self.start_new_fiber(account3)
    # A -- B -- C
    self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 200 * 100000000)
    fiber3.connect_peer(self.fiber2)
    time.sleep(1)
    self.open_channel(self.fiber2, fiber3, 200 * 100000000, 200 * 100000000)
    time.sleep(3)  # Gossip propagation
    self.send_payment(self.fiber1, fiber3, 10 * 100000000)
```

## SharedFiberTest - Shared Topology Pattern

When multiple test methods share the same multi-node topology (e.g. routing, fee, boundary value tests), use `SharedFiberTest` to avoid repeated setup overhead.

### Basic Structure

```python
from framework.basic_share_fiber import SharedFiberTest
from framework.test_fiber import Fiber

class TestMyFeature(SharedFiberTest):
    fiber3: Fiber
    fiber4: Fiber

    def setUp(self):
        if getattr(TestMyFeature, "_channel_inited", False):
            return
        TestMyFeature._channel_inited = True

        self.__class__.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.__class__.fiber4 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 0)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 0)
        self.open_channel(self.fiber3, self.fiber4, 1000 * 100000000, 0)

    def test_scenario_a(self):
        # Reuses the topology above
        pass

    def test_scenario_b(self):
        # Same topology, different test
        pass
```

### Key Differences from FiberTest

| Aspect | FiberTest | SharedFiberTest |
|--------|-----------|-----------------|
| `setup_class` | Starts CKB node only | Starts CKB node + Fiber nodes + UDT + peer connection |
| `setup_method` | Full Fiber env init per test | Calls `CkbTest.setup_method` only (skips Fiber init) |
| `teardown_method` | Stops + cleans all Fibers | Calls `CkbTest.teardown_method` only (keeps Fibers) |
| `teardown_class` | Stops CKB node | Stops all Fibers + CKB node |

### One-Time Channel Init Guard

The `setUp()` method (unittest convention, auto-called before each test) uses a class-level `_channel_inited` flag to ensure topology is built only once:

```python
def setUp(self):
    if getattr(ClassName, "_channel_inited", False):
        return
    ClassName._channel_inited = True
    # ... build channels here ...
```

### Storing Extra Nodes

Extra Fiber nodes must be stored on the class (not instance) to persist across methods:

```python
self.__class__.fiber3 = self.start_new_fiber(self.generate_account(10000))
```

### When to Use SharedFiberTest

- Routing tests with complex topologies (5+ nodes, multiple paths)
- Fee calculation tests across different parameter combinations
- Boundary value tests for payment amounts, hops, etc.
- Any scenario where building the topology once and running many assertions is efficient

### When NOT to Use SharedFiberTest

- Tests that perform destructive operations (force close, revoked commit)
- Tests requiring clean channel state (balance verification from zero)
- Tests that modify Fiber config or restart nodes

## Hold Invoice Pattern

```python
import hashlib
def sha256_hex(preimage_hex):
    raw = bytes.fromhex(preimage_hex.replace("0x", ""))
    return "0x" + hashlib.sha256(raw).hexdigest()

def test_hold_invoice(self):
    self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 0)
    preimage = self.generate_random_preimage()
    payment_hash = sha256_hex(preimage)
    invoice = self.fiber2.get_client().new_invoice({
        "amount": hex(1 * 100000000), "currency": "Fibd",
        "description": "hold", "payment_hash": payment_hash, "hash_algorithm": "sha256",
    })
    payment = self.fiber1.get_client().send_payment({"invoice": invoice["invoice_address"]})
    self.wait_invoice_state(self.fiber2, payment_hash, "Received")
    self.fiber2.get_client().settle_invoice({"payment_hash": payment_hash, "payment_preimage": preimage})
    self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
```

## UDT Channel Pattern

```python
udt_script = self.get_account_udt_script(self.fiber1.account_private)
self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 100 * 100000000, udt=udt_script)
self.send_payment(self.fiber1, self.fiber2, 10 * 100000000, udt=udt_script)
```

## Balance Verification Pattern

```python
before = self.get_fibers_balance()
# ... operations ...
after = self.get_fibers_balance()
changes = self.get_balance_change(before, after)
# changes[i] = {"ckb": delta, "udt": delta}
```

## Node Restart Pattern

```python
self.fiber1.stop()
time.sleep(2)
self.fiber1.start()
self.fiber1.connect_peer(self.fiber2)
time.sleep(3)
self.send_payment(self.fiber1, self.fiber2, 10 * 100000000)
```

## Config Override Pattern

```python
class TestCustom(FiberTest):
    start_fiber_config = {
        "fiber_auto_accept_amount": "0",
        "fiber_watchtower_check_interval_seconds": 5,
        "fiber_tlc_expiry_delta": "86400000",
        "fiber_tlc_fee_proportional_millionths": "1000",
    }
```

## Constants Reference

```python
from framework.config import DEFAULT_MIN_DEPOSIT_CKB  # 99 * 100000000

# Currencies: "Fibd" (devnet), "Fibt" (testnet), "Fib" (mainnet)
# Channel states: NEGOTIATING_FUNDING, CHANNEL_READY, SHUTTING_DOWN, CLOSED
# Payment states: Created, Inflight, Success, Failed
# Invoice states: Open, Received, Paid, Cancelled, Expired
```

## CI/CD

```bash
pytest test_cases/fiber/devnet/path/to/test.py -v -s          # Single file
pytest test_cases/fiber/devnet/path/to/test.py::Class::method  # Single method
make fiber_test                                                 # All devnet
```

GitHub Actions: `fiber.yml` runs 13+ parallel test jobs after prepare step.
