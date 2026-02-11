# Lightning Network Concepts in Fiber

How Bitcoin Lightning Network concepts map to Fiber Network on CKB.

## Table of Contents

- [Architecture Comparison](#architecture-comparison)
- [Payment Channels](#payment-channels)
- [HTLC vs TLC](#htlc-vs-tlc)
- [Routing and Path Finding](#routing-and-path-finding)
- [Invoice System](#invoice-system)
- [Multi-Path Payments](#multi-path-payments)
- [Trampoline Routing](#trampoline-routing)
- [Watchtower](#watchtower)
- [Cross-Chain Interoperability](#cross-chain-interoperability)
- [Key Differences from Bitcoin LN](#key-differences-from-bitcoin-ln)

---

## Architecture Comparison

| Concept | Bitcoin Lightning | Fiber Network |
|---------|------------------|---------------|
| Base Layer | Bitcoin | Nervos CKB |
| Channel Contract | 2-of-2 multisig | CKB FundingLock + CommitmentLock |
| Hash Lock | HTLC | TLC (Time-Locked Contract) |
| Invoice Format | BOLT11 | CKB Invoice (Fibd/Fibt/Fib prefix) |
| Token Support | BTC only | CKB + UDTs (User Defined Tokens) |
| Routing | Source routing | Source routing + Trampoline |
| Implementation | LND/CLN/Eclair | FNN (Fiber Network Node) in Rust |
| P2P Protocol | BOLT #8 | tentacle (libp2p-like) |
| Node Software | lnd, c-lightning | fiber-bin (fnn) |

## Payment Channels

### Channel Lifecycle

**Bitcoin LN:**
```
funding_created → funding_signed → funding_locked → channel_normal → shutdown → closing_signed
```

**Fiber:**
```
NEGOTIATING_FUNDING → COLLABORATING_FUNDING_TX → SIGNING_COMMITMENT →
AWAITING_TX_SIGNATURES → AWAITING_CHANNEL_READY → CHANNEL_READY →
SHUTTING_DOWN → CLOSED
```

### Funding Transaction

- **Bitcoin LN**: 2-of-2 multisig output
- **Fiber**: CKB cell with FundingLock script; supports both CKB and UDT (via type script)

### Commitment Transaction

- **Bitcoin LN**: Each party holds their own version, asymmetric
- **Fiber**: Similar pattern using CommitmentLock on CKB; revocation mechanism for old states

### Channel Capacity

- **Bitcoin LN**: Capacity defined by funding tx output
- **Fiber**: `funding_amount` parameter; minimum 99 CKB (`DEFAULT_MIN_DEPOSIT_CKB`) for CKB channels

### Channel Announcement

- **Bitcoin LN**: `channel_announcement` + `channel_update` messages
- **Fiber**: Same concept; `public: true` flag broadcasts channel to network via gossip

---

## HTLC vs TLC

### Bitcoin LN HTLC (Hash Time-Locked Contract)

```
IF
    <remote_key> AND hash_preimage(R) == H
ELSE
    <local_key> AND CLTV_expiry
```

### Fiber TLC (Time-Locked Contract)

Similar concept adapted for CKB:
- Uses `payment_hash` (SHA256 or CKB Hash) and `expiry` (timestamp in ms)
- Settled with `payment_preimage` that hashes to `payment_hash`
- If not settled before `expiry`, can be reclaimed by sender

### TLC Parameters in Fiber

| Parameter | Description | Default |
|-----------|-------------|---------|
| `tlc_expiry_delta` | Time added per hop | 86400000 ms (1 day) |
| `tlc_min_value` | Minimum TLC amount | 0 |
| `tlc_max_value` | Maximum TLC amount | 0 (unlimited) |
| `tlc_fee_proportional_millionths` | Fee rate | 1000 (0.1%) |
| `max_tlc_number_in_flight` | Max concurrent TLCs | Configurable |
| `max_tlc_value_in_flight` | Max total TLC value | Configurable |

### TLC Fee Calculation

```python
# Fee = amount * tlc_fee_proportional_millionths / 1_000_000
# For 0.1% fee (1000 millionths):
fee = amount * 1000 / 1_000_000  # = amount * 0.001

# Multi-hop fee calculation (A → B → C, each with fee_rate):
self.calculate_tx_fee(amount, [fee_rate_b, fee_rate_c])
```

---

## Routing and Path Finding

### Source Routing

Both Bitcoin LN and Fiber use **source routing**:
1. Sender builds complete path from network graph
2. Creates onion-encrypted packet (each hop only sees next hop)
3. Forwards payment through intermediate nodes

### Network Graph

- Built from **gossip protocol** messages:
  - `NodeAnnouncement`: Node info (pubkey, addresses, features)
  - `ChannelAnnouncement`: New channel (node1, node2, capacity)
  - `ChannelUpdate`: Channel params (fees, expiry, enabled)

### Path Finding Algorithm

- Fiber uses **Dijkstra-based** algorithm
- Considers: fees, capacity, channel enabled state, TLC limits
- Query via `build_router` API or automatic in `send_payment`

### Gossip Protocol in Fiber

- **Active sync**: Pull missed messages from peers on connect
- **Passive sync**: Subscribe to updates via filters
- Maintenance intervals configurable:
  - `gossip_network_maintenance_interval_ms` (default: 60s)
  - `gossip_store_maintenance_interval_ms` (default: 20s)

---

## Invoice System

### Bitcoin LN (BOLT11)

```
lnbc10u1p...  (prefix: ln + currency + amount)
```

### Fiber Invoice

```
fibd11p...    (prefix: fib + network + amount)
```

| Network | Prefix |
|---------|--------|
| Mainnet | `fib` |
| Testnet | `fibt` |
| Devnet  | `fibd` |

### Invoice Types

1. **Standard Invoice**: Contains `payment_preimage` → auto-settles on payment receipt
2. **Hold Invoice**: Contains only `payment_hash` → receiver must manually `settle_invoice` with preimage

### Hash Algorithms

- `sha256`: Standard SHA-256 (compatible with Bitcoin LN)
- `ckb_hash`: CKB-native hash algorithm

---

## Multi-Path Payments (MPP)

### Concept

Split a large payment across multiple paths when no single path has sufficient capacity.

### Fiber MPP

```python
# Enable MPP in invoice payment
payment = fiber.get_client().send_payment({
    "invoice": invoice_address,
    "max_parts": hex(12),           # Max number of payment parts
    "allow_self_payment": True,
})
```

### Atomic MPP (AMP)

All parts succeed or all fail atomically:

```python
# Create invoice without preimage (for AMP)
invoice = fiber.get_client().new_invoice({
    "amount": hex(amount),
    "currency": "Fibd",
    "description": "AMP test",
    "hash_algorithm": "sha256",
    # No payment_preimage for AMP
})

# Send with AMP flag
payment = fiber.get_client().send_payment({
    "invoice": invoice["invoice_address"],
    "amp": True,
})
```

---

## Trampoline Routing

### Concept

Sender delegates route-finding to an intermediate "trampoline" node:
1. Sender routes to trampoline node
2. Trampoline node finds route to destination
3. Reduces sender's need for full network graph

### Fiber Implementation

```python
# Trampoline payment (sender only knows route to trampoline)
payment = fiber.get_client().send_payment({
    "target_pubkey": destination_node_id,
    "amount": hex(amount),
    "keysend": True,
    "max_fee_amount": hex(max_fee),        # Budget for trampoline fees
    "allow_self_payment": True,
})
```

### Test Scenarios

- Successful trampoline routing through intermediate node
- Max fee amount too low (should fail)
- TLC expiry limit exceeded (should fail)
- Multi-hop trampoline routing

---

## Watchtower

### Purpose

Monitors channels for cheating attempts (old commitment transactions).

### Bitcoin LN Watchtower

- External service monitors blockchain for revoked commitments
- Broadcasts penalty transaction if old state detected

### Fiber Watchtower

- **Built-in**: Each node runs its own watchtower
- **Standalone**: External watchtower service (configurable URL)
- Configurable check interval: `watchtower_check_interval_seconds`

### Dispute Resolution Flow

```
1. Node A force-closes with commitment tx
2. Commitment tx has timelock (commitment_delay_epoch)
3. During timelock, watchtower monitors for revoked states
4. If old state detected → penalty tx submitted
5. After timelock expires → settlement tx claims funds
```

### Testing Watchtower

```python
class TestWatchtower(FiberTest):
    start_fiber_config = {"fiber_watchtower_check_interval_seconds": 5}

    def test_dispute(self):
        # Open channel, force close, generate epochs, verify settlement
        ...
```

---

## Cross-Chain Interoperability

### Cross-Chain Hub (CCH)

Bridges Bitcoin Lightning ↔ Fiber Network:

```
Bitcoin LN ←→ CCH ←→ Fiber Network
    LND           FNN (with CCH module)
```

### Operations

1. **send_btc**: Pay a BTC Lightning invoice using Fiber CKB
2. **receive_btc**: Receive BTC Lightning payment into Fiber

### Configuration

```yaml
cch:
  wrapped_btc_type_script_args: "0x..."
  lnd_rpc_url: "https://localhost:10009"
  lnd_cert_path: "/path/to/tls.cert"
```

---

## Key Differences from Bitcoin LN

### 1. Multi-Asset Support

Fiber supports both CKB and UDTs (User Defined Tokens):
- Open channels with `funding_udt_type_script`
- Send UDT payments through UDT channels
- UDT whitelist configurable per node

### 2. CKB Cell Model vs Bitcoin UTXO

- CKB uses a generalized UTXO model (Cell Model)
- Cells have `capacity`, `lock_script`, `type_script`, and `data`
- More flexible scripting than Bitcoin Script

### 3. Epoch-Based Timelocks

- Bitcoin LN uses block height or Unix timestamp for CLTV
- Fiber uses CKB epochs and millisecond timestamps
- `generate_epochs` for advancing time in tests

### 4. WASM Client

Fiber has WebAssembly (WASM) support:
- `fiber-wasm` crate for browser-based clients
- Tested via `test_cases/fiber/devnet/wasm/`

### 5. Actor-Based Architecture

Fiber uses Ractor (Rust actor framework):
- `NetworkActor`: P2P connections, channel management
- `ChannelActor`: Per-channel state machine
- `PaymentActor`: Payment session management
- `CkbChainActor`: Blockchain interaction
- `CchActor`: Cross-chain hub

### 6. Biscuit Authentication

Fiber supports Biscuit tokens for RPC authentication:
- Token-based access control per RPC method
- Configurable per node
