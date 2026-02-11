---
name: fiber-test
description: Write, review, and debug integration tests for the Fiber Network (CKB Lightning Network) project. Use when creating new test cases, understanding test patterns, working with Fiber RPC APIs, testing channel operations, payment flows, invoice management, watchtower functionality, or any testing task related to the fiber-py-integration-test project. Also use when the user asks about Fiber architecture, Lightning Network concepts on CKB, or test framework usage.
---

# Fiber Network Integration Test Skill

## Project Overview

Fiber Network Node (FNN) is a Lightning Network implementation on Nervos CKB blockchain. This test project (`fiber-py-integration-test`) provides Python-based integration tests covering channel lifecycle, payments, invoices, watchtower, cross-chain hub (CCH), and more.

**Key Lightning Network concepts in Fiber:**
- Payment channels (open → ready → shutdown → closed)
- HTLC/TLC (Time-Locked Contracts) for atomic multi-hop payments
- Onion routing with encrypted payment paths
- Multi-path payments (MPP) and atomic MPP
- Trampoline routing (partial route delegation)
- Watchtower for dispute resolution
- Cross-chain hub for Lightning ↔ Fiber interoperability

For detailed Lightning Network concepts mapped to Fiber, see [references/lightning-concepts.md](references/lightning-concepts.md).

## Test Framework Architecture

```
framework/
├── basic.py              # CkbTest base class (CKB node management)
├── basic_fiber.py        # FiberTest base class (Fiber node management + helpers)
├── basic_fiber_with_cch.py  # FiberCchTest (adds BTC + LND for cross-chain)
├── fiber_rpc.py          # FiberRPCClient (JSON-RPC 2.0 client)
├── rpc.py                # RPCClient for CKB
├── test_fiber.py         # Fiber node lifecycle management
├── test_node.py          # CKB node lifecycle management
├── config.py             # Constants, keys, default configs
├── util.py               # Utilities (run_command, generate_account, time manipulation)
└── helper/
    ├── miner.py           # Block mining utilities
    ├── ckb_cli.py         # CKB CLI wrappers
    ├── contract.py        # Contract deployment
    ├── udt_contract.py    # UDT (User Defined Token) operations
    ├── tx.py              # Transaction building
    └── node.py            # Node wait utilities
```

### Inheritance Chain

```
unittest.TestCase → CkbTest → FiberTest → FiberCchTest
```

- **CkbTest**: CKB node, miner, CLI, contract helpers
- **FiberTest**: 2 Fiber nodes (fiber1, fiber2), UDT contract, channel/payment/invoice helpers
- **FiberCchTest**: Adds BTC node + LND nodes for cross-chain tests

## Writing Tests

### Minimal Test Template

```python
import time
import pytest
from framework.basic_fiber import FiberTest

class TestMyFeature(FiberTest):
    """Describe what this test class covers."""

    # Optional: override Fiber startup config
    # start_fiber_config = {"fiber_auto_accept_amount": "0"}

    def test_basic_scenario(self):
        # 1. Open channel
        self.fiber1.get_client().open_channel({
            "peer_id": self.fiber2.get_peer_id(),
            "funding_amount": hex(200 * 100000000),
            "public": True,
        })
        self.wait_for_channel_state(
            self.fiber1.get_client(), self.fiber2.get_peer_id(), "CHANNEL_READY"
        )

        # 2. Perform operation (e.g., send payment)
        payment = self.fiber1.get_client().send_payment({
            "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
            "amount": hex(10 * 100000000),
            "keysend": True,
        })
        self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")

        # 3. Verify state
        channels = self.fiber1.get_client().list_channels(
            {"peer_id": self.fiber2.get_peer_id()}
        )
        assert channels["channels"][0]["state"]["state_name"] == "CHANNEL_READY"

    def test_error_scenario(self):
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().open_channel({
                "peer_id": self.fiber2.get_peer_id(),
                "funding_amount": hex(0),
                "public": True,
            })
        expected_error_message = "should be greater than or equal to"
        assert expected_error_message in exc_info.value.args[0]
```

### What `setup_method` Provides Automatically

Each test method starts with:
1. A running CKB dev node (`self.node`)
2. Two Fiber nodes started and connected (`self.fiber1`, `self.fiber2`)
3. UDT tokens issued to fiber1 (`self.udtContract`)
4. Peers already connected (fiber1 ↔ fiber2)

### Key Helper Methods

| Method | Description |
|--------|-------------|
| `self.open_channel(fiber1, fiber2, bal1, bal2)` | Open channel with specified balances |
| `self.send_payment(fiber1, fiber2, amount)` | Keysend payment with retry |
| `self.send_invoice_payment(fiber1, fiber2, amount)` | Invoice-based payment with retry |
| `self.wait_for_channel_state(client, peer_id, state)` | Wait for channel state transition |
| `self.wait_payment_state(fiber, payment_hash, status)` | Wait for payment status (Success/Failed) |
| `self.wait_invoice_state(client, payment_hash, status)` | Wait for invoice status |
| `self.generate_account(ckb_balance)` | Create funded test account |
| `self.start_new_fiber(account_private_key)` | Start additional Fiber node (fiber3, fiber4, ...) |
| `self.generate_random_preimage()` | Generate random 32-byte hex preimage |
| `self.get_fiber_balance(fiber)` | Get fiber node balance (chain + channels) |
| `self.faucet(private_key, ckb_balance)` | Fund an account with CKB/UDT |
| `self.get_account_udt_script(private_key)` | Get UDT type script for account |
| `self.wait_and_check_tx_pool_fee(fee_rate)` | Wait for tx in pool and check fee |
| `self.get_ln_tx_trace(tx_hash)` | Trace Lightning Network transactions on-chain |

### Amount Convention

All amounts use CKB Shannon (1 CKB = 100000000 Shannon):
```python
amount_ckb = 100 * 100000000  # 100 CKB
hex_amount = hex(amount_ckb)   # "0x2540be400"
```

### Channel States

```
NEGOTIATING_FUNDING → COLLABORATING_FUNDING_TX → SIGNING_COMMITMENT →
AWAITING_TX_SIGNATURES → AWAITING_CHANNEL_READY → CHANNEL_READY →
SHUTTING_DOWN → CLOSED
```

### Payment States

```
Created → Inflight → Success | Failed
```

### Invoice States

```
Open → Received → Paid | Cancelled | Expired
```

## Test Categories

| Category | Path | What to Test |
|----------|------|-------------|
| Channel open | `test_cases/fiber/devnet/open_channel/` | Funding amounts, fees, UDT, public/private, TLC params |
| Channel accept | `test_cases/fiber/devnet/accept_channel/` | Accept params, funding, temporary IDs |
| Channel shutdown | `test_cases/fiber/devnet/shutdown_channel/` | Cooperative/force close, restart scenarios |
| Channel update | `test_cases/fiber/devnet/update_channel/` | TLC params, enabled state |
| Payments | `test_cases/fiber/devnet/send_payment/` | Keysend, invoice, multi-hop, MPP, params |
| Invoices | `test_cases/fiber/devnet/new_invoice/` | Create, parse, amount, currency, expiry |
| Settle invoice | `test_cases/fiber/devnet/settle_invoice/` | Hold invoices, preimage, batch, multi-hop |
| Cancel invoice | `test_cases/fiber/devnet/cancel_invoice/` | Cancel flow |
| Watchtower | `test_cases/fiber/devnet/watch_tower/` | Force close disputes, TLC monitoring |
| Network | `test_cases/fiber/devnet/connect_peer/` | Peer connection/disconnection |
| Graph | `test_cases/fiber/devnet/graph_channels/` | Network topology queries |
| Cross-chain | `test_cases/fiber/devnet/cch/` | BTC ↔ CKB via LND |
| Trampoline | `test_cases/fiber/devnet/trampoline_routing/` | Delegated routing |
| TLC timeout | `test_cases/fiber/devnet/tlc_timeout/` | Time-lock expiry scenarios |
| WASM | `test_cases/fiber/devnet/wasm/` | WebAssembly client tests |

## Multi-Node Test Pattern

For tests requiring 3+ nodes (multi-hop routing, trampoline):

```python
def test_multi_hop_payment(self):
    # Create and fund a third node
    account3 = self.generate_account(1000)
    fiber3 = self.start_new_fiber(account3)

    # Build topology: fiber1 -- fiber2 -- fiber3
    self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 200 * 100000000)
    fiber3.connect_peer(self.fiber2)
    time.sleep(1)
    self.open_channel(self.fiber2, fiber3, 200 * 100000000, 200 * 100000000)

    # Wait for gossip propagation
    time.sleep(3)

    # Payment from fiber1 to fiber3 (routed through fiber2)
    payment = self.fiber1.get_client().send_payment({
        "target_pubkey": fiber3.get_client().node_info()["node_id"],
        "amount": hex(10 * 100000000),
        "keysend": True,
        "allow_self_payment": True,
    })
    self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
```

## Hold Invoice Pattern

```python
import hashlib

def sha256_hex(preimage_hex: str) -> str:
    raw = bytes.fromhex(preimage_hex.replace("0x", ""))
    return "0x" + hashlib.sha256(raw).hexdigest()

def test_hold_invoice(self):
    self.open_channel(self.fiber1, self.fiber2, 200 * 100000000, 0)

    # Create hold invoice (only payment_hash, no preimage)
    preimage = self.generate_random_preimage()
    payment_hash = sha256_hex(preimage)
    invoice = self.fiber2.get_client().new_invoice({
        "amount": hex(1 * 100000000),
        "currency": "Fibd",
        "description": "hold invoice test",
        "payment_hash": payment_hash,
        "hash_algorithm": "sha256",
    })

    # Send payment - invoice enters "Received" (held) state
    payment = self.fiber1.get_client().send_payment(
        {"invoice": invoice["invoice_address"]}
    )
    self.wait_invoice_state(self.fiber2, payment_hash, "Received")

    # Settle with preimage
    self.fiber2.get_client().settle_invoice({
        "payment_hash": payment_hash,
        "payment_preimage": preimage,
    })
    self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
```

## Watchtower Test Pattern

```python
class TestWatchtower(FiberTest):
    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 5}

    def test_force_close_dispute(self):
        self.fiber1.get_client().open_channel({...})
        self.wait_for_channel_state(...)

        # Force close
        self.fiber1.get_client().shutdown_channel({
            "channel_id": channel_id, "force": True
        })
        tx = self.wait_and_check_tx_pool_fee(1000, False)
        self.Miner.miner_until_tx_committed(self.node, tx)

        # Generate epochs to trigger watchtower
        self.node.getClient().generate_epochs("0x1", 0)
        # Verify dispute resolution...
```

## Configuration Overrides

Override fiber startup config per test class:

```python
class TestCustomConfig(FiberTest):
    start_fiber_config = {
        "fiber_auto_accept_amount": "0",                    # Disable auto-accept
        "fiber_watchtower_check_interval_seconds": 5,       # Fast watchtower
        "fiber_tlc_expiry_delta": "86400000",               # 1 day in ms
        "fiber_tlc_fee_proportional_millionths": "1000",    # 0.1% fee
    }
```

## Running Tests

```bash
# Run specific test file
pytest test_cases/fiber/devnet/open_channel/test_funding_amount.py -v -s

# Run specific test method
pytest test_cases/fiber/devnet/open_channel/test_funding_amount.py::FundingAmount::test_funding_amount_ckb_is_zero -v -s

# Run all devnet tests
make fiber_test

# Run with HTML report
python -m pytest test_cases/fiber/devnet/ --html=report/report.html
```

## Fiber RPC API Quick Reference

For the complete API reference, see [references/api-reference.md](references/api-reference.md).

**Channel**: `open_channel`, `accept_channel`, `list_channels`, `shutdown_channel`, `update_channel`, `abandon_channel`

**Payment**: `send_payment`, `get_payment`, `build_router`, `send_payment_with_router`

**Invoice**: `new_invoice`, `parse_invoice`, `get_invoice`, `cancel_invoice`, `settle_invoice`

**Peer**: `connect_peer`, `disconnect_peer`, `list_peers`

**Graph**: `graph_nodes`, `graph_channels`

**Info**: `node_info`

**CCH**: `send_btc`, `receive_btc`, `get_cch_order`

**Dev**: `add_tlc`, `remove_tlc`, `commitment_signed`

## Detailed Test Pattern Reference

For comprehensive test patterns including UDT channels, MPP, error testing, balance verification, and CI/CD pipeline details, see [references/test-patterns.md](references/test-patterns.md).
