# Fiber RPC API Reference

Complete API reference for Fiber Network Node JSON-RPC 2.0 interface. All calls go through `FiberRPCClient` at `framework/fiber_rpc.py`.

## Table of Contents

- [Channel Module](#channel-module)
- [Payment Module](#payment-module)
- [Invoice Module](#invoice-module)
- [Peer Module](#peer-module)
- [Graph Module](#graph-module)
- [Info Module](#info-module)
- [Cross-Chain Hub (CCH) Module](#cross-chain-hub-cch-module)
- [Watchtower Module](#watchtower-module)
- [Dev Module](#dev-module)

---

## Channel Module

### open_channel

Open a payment channel with a peer.

```python
result = fiber.get_client().open_channel({
    "peer_id": "QmaQSn11js...",                   # Required: peer's P2P ID
    "funding_amount": "0x2540be400",               # Required: total funding in hex Shannon
    "public": True,                                 # Optional: announce to network (default: False)
    "funding_udt_type_script": None,               # Optional: UDT script for token channels
    "commitment_fee_rate": "0x3e8",                # Optional: fee rate for commitment tx
    "commitment_delay_epoch": "0x06",              # Optional: delay epochs for disputes
    "funding_fee_rate": "0x3e8",                   # Optional: fee rate for funding tx
    "tlc_expiry_delta": "0x5265c00",              # Optional: TLC expiry delta in ms
    "tlc_min_value": "0x0",                        # Optional: min TLC value
    "tlc_max_value": "0x0",                        # Optional: max TLC value (0 = unlimited)
    "tlc_fee_proportional_millionths": "0x3e8",   # Optional: fee rate (1000 = 0.1%)
    "max_tlc_value_in_flight": "0x0",             # Optional: max total TLC value
    "max_tlc_number_in_flight": "0x0",            # Optional: max concurrent TLCs
    "shutdown_script": {...},                       # Optional: custom close script
})
# Returns: {"temporary_channel_id": "0x..."}
```

**Auto-accept behavior**: If `funding_amount` exceeds peer's `open_channel_auto_accept_min_ckb_funding_amount`, channel is auto-accepted. Otherwise, peer must call `accept_channel`.

### accept_channel

Accept an incoming channel open request.

```python
fiber.get_client().accept_channel({
    "temporary_channel_id": "0x...",   # From open_channel notification
    "funding_amount": "0x...",          # Peer's contribution
    "tlc_fee_proportional_millionths": "0x3e8",  # Optional
})
```

### list_channels

List channels, optionally filtered.

```python
channels = fiber.get_client().list_channels({
    "peer_id": "Qm...",          # Optional: filter by peer
    "include_closed": False,      # Optional: include closed channels
})
# Returns: {"channels": [{
#   "channel_id": "0x...",
#   "peer_id": "Qm...",
#   "state": {"state_name": "CHANNEL_READY", "state_flags": "..."},
#   "local_balance": "0x...",
#   "remote_balance": "0x...",
#   "offered_tlc_balance": "0x...",
#   "received_tlc_balance": "0x...",
#   "funding_udt_type_script": null | {...},
#   "created_at": "0x...",
#   "channel_outpoint": "0x...",
#   "enabled": true,
#   "pending_tlcs": [...],
#   "tlc_fee_proportional_millionths": "0x3e8",
# }]}
```

### shutdown_channel

Close a channel (cooperative or forced).

```python
fiber.get_client().shutdown_channel({
    "channel_id": "0x...",
    "close_script": {...},    # Optional: custom close script
    "force": False,            # Optional: force unilateral close
    "fee_rate": "0x3e8",      # Optional: fee rate for close tx
})
```

### update_channel

Update channel parameters after opening.

```python
fiber.get_client().update_channel({
    "channel_id": "0x...",
    "enabled": True,                                # Optional: enable/disable routing
    "tlc_fee_proportional_millionths": "0x3e8",    # Optional
    "tlc_expiry_delta": "0x5265c00",              # Optional
    "tlc_min_value": "0x0",                        # Optional
    "tlc_max_value": "0x0",                        # Optional
})
```

### abandon_channel

Remove a channel that hasn't reached CHANNEL_READY state.

```python
fiber.get_client().abandon_channel({
    "channel_id": "0x...",
})
```

---

## Payment Module

### send_payment

Send a payment with automatic route finding.

```python
# Keysend (no invoice)
payment = fiber.get_client().send_payment({
    "target_pubkey": "02a10c20...",     # Recipient's node public key
    "amount": "0x2540be400",             # Amount in hex Shannon
    "keysend": True,                      # Spontaneous payment
    "allow_self_payment": True,          # Allow payment to self via route
    "udt_type_script": None,             # Optional: for UDT payments
    "max_fee_amount": "0x...",           # Optional: max routing fee
    "final_tlc_expiry_delta": "0x...",  # Optional: final hop expiry
    "tlc_expiry_limit": "0x...",        # Optional: max total expiry
    "timeout": "0x...",                  # Optional: payment timeout
    "max_parts": "0xc",                 # Optional: max MPP parts
    "dry_run": False,                    # Optional: simulate only
})
# Returns: {"payment_hash": "0x...", "status": "Created", ...}

# Invoice payment
payment = fiber.get_client().send_payment({
    "invoice": "fibd11p...",             # Encoded invoice address
    "allow_self_payment": True,
    "max_parts": "0xc",                  # For MPP
})

# Atomic MPP
payment = fiber.get_client().send_payment({
    "invoice": "fibd11p...",
    "allow_self_payment": True,
    "amp": True,                          # Atomic multi-path payment
})
```

### get_payment

Get payment status and details.

```python
result = fiber.get_client().get_payment({"payment_hash": "0x..."})
# Returns: {
#   "payment_hash": "0x...",
#   "status": "Success",          # Created | Inflight | Success | Failed
#   "created_at": "0x...",
#   "last_updated_at": "0x...",
#   "failed_error": null | "error message",
#   "fee": "0x...",               # Actual routing fee paid
# }
```

### build_router

Build a payment route manually.

```python
route = fiber.get_client().build_router({
    "target_pubkey": "02...",
    "amount": "0x...",
    "payment_hash": "0x...",
    "udt_type_script": None,
})
```

### send_payment_with_router

Send payment using a pre-built route.

```python
payment = fiber.get_client().send_payment_with_router({
    "target_pubkey": "02...",
    "amount": "0x...",
    "payment_hash": "0x...",
    "router": route,     # From build_router
})
```

---

## Invoice Module

### new_invoice

Create a new invoice.

```python
# Standard invoice (with preimage → auto-settles)
invoice = fiber.get_client().new_invoice({
    "amount": hex(100 * 100000000),
    "currency": "Fibd",                              # Fibd (devnet) | Fibt (testnet) | Fib (mainnet)
    "description": "test invoice",
    "payment_preimage": "0x...",                      # 32-byte hex preimage
    "hash_algorithm": "sha256",                       # "sha256" or "ckb_hash"
    "expiry": "0xe10",                                # Optional: expiry in seconds (default: 3600)
    "final_cltv": "0x28",                             # Optional: final CLTV delta
    "udt_type_script": None,                          # Optional: for UDT invoices
})
# Returns: {"invoice_address": "fibd11p...", "invoice": {...}}

# Hold invoice (only payment_hash → manual settle required)
invoice = fiber.get_client().new_invoice({
    "amount": hex(1 * 100000000),
    "currency": "Fibd",
    "description": "hold invoice",
    "payment_hash": "0x...",                          # Only hash, no preimage
    "hash_algorithm": "sha256",
})
```

### parse_invoice

Parse an encoded invoice string.

```python
parsed = fiber.get_client().parse_invoice({"invoice": "fibd11p..."})
# Returns: {"invoice": {
#   "currency": "Fibd",
#   "amount": "0x...",
#   "data": {
#     "payment_hash": "0x...",
#     "timestamp": "0x...",
#     "attrs": [
#       {"Description": "..."},
#       {"ExpiryTime": {"secs": 3600, "nanos": 0}},
#       {"HashAlgorithm": "sha256"},
#       {"PayeePublicKey": "02..."},
#       {"UdtScript": "0x..."}, // if UDT
#     ]
#   }
# }}
```

### get_invoice

Get invoice by payment hash.

```python
inv = fiber.get_client().get_invoice({"payment_hash": "0x..."})
# Returns: {"invoice_address": "...", "invoice": {...}, "status": "Paid"}
# Status: Open | Cancelled | Expired | Received | Paid
```

### cancel_invoice

Cancel an open invoice.

```python
fiber.get_client().cancel_invoice({"payment_hash": "0x..."})
```

### settle_invoice

Settle a hold invoice with preimage. Invoice must be in "Received" state.

```python
fiber.get_client().settle_invoice({
    "payment_hash": "0x...",
    "payment_preimage": "0x...",  # 32-byte preimage matching the hash
})
```

---

## Peer Module

### connect_peer

```python
fiber.get_client().connect_peer({"address": "/ip4/127.0.0.1/tcp/8229/p2p/Qm..."})
# Or use helper: fiber1.connect_peer(fiber2)
```

### disconnect_peer

```python
fiber.get_client().disconnect_peer({"peer_id": "Qm..."})
```

### list_peers

```python
peers = fiber.get_client().list_peers()
```

---

## Graph Module

### graph_nodes

```python
nodes = fiber.get_client().graph_nodes({
    "limit": "0x10",           # Optional: pagination limit
    "after": "0x...",          # Optional: cursor for pagination
})
```

### graph_channels

```python
channels = fiber.get_client().graph_channels({
    "limit": "0x10",
    "after": "0x...",
})
# Returns: {"channels": [...], "last_cursor": "0x..."}
```

---

## Info Module

### node_info

```python
info = fiber.get_client().node_info()
# Returns: {
#   "version": "0.1.0",
#   "commit_hash": "07174b5",
#   "node_id": "02...",                  # Node public key
#   "peer_id": "Qm...",                  # P2P peer ID
#   "addresses": ["/ip4/.../tcp/.../p2p/Qm..."],
#   "chain_hash": "0x...",
#   "open_channel_auto_accept_min_ckb_funding_amount": "0x...",
#   "auto_accept_channel_ckb_funding_amount": "0x...",
#   "tlc_expiry_delta": "0x5265c00",
#   "tlc_min_value": "0x0",
#   "tlc_fee_proportional_millionths": "0x3e8",
#   "channel_count": "0x0",
#   "pending_channel_count": "0x0",
#   "peers_count": "0x0",
#   "network_sync_status": "Running",
#   "udt_cfg_infos": [...],
# }
```

---

## Cross-Chain Hub (CCH) Module

Requires `FiberCchTest` base class with BTC + LND nodes.

### send_btc

Create order to pay a BTC Lightning invoice via Fiber.

```python
order = fiber.get_client().send_btc({"btc_pay_req": "lnbc..."})
```

### receive_btc

Create order to receive BTC via Lightning into Fiber.

```python
order = fiber.get_client().receive_btc({
    "amount": "0x...",
    "currency": "Fibd",
})
```

### get_cch_order

```python
order = fiber.get_client().get_cch_order({"payment_hash": "0x..."})
```

---

## Watchtower Module

### remove_watch_channel

```python
fiber.get_client().remove_watch_channel({"channel_id": "0x..."})
```

---

## Dev Module

For testing/debugging only.

### add_tlc

```python
fiber.get_client().add_tlc({
    "channel_id": "0x...",
    "amount": "0x...",
    "payment_hash": "0x...",
    "expiry": "0x...",
})
```

### remove_tlc

```python
fiber.get_client().remove_tlc({
    "channel_id": "0x...",
    "tlc_id": "0x...",
    "reason": {"payment_preimage": "0x..."},  # or error code
})
```

---

## Common Response Patterns

### Hex Values

All numeric values in Fiber RPC are hex-encoded strings:
```python
# Reading hex values
balance_int = int(channel["local_balance"], 16)
balance_ckb = balance_int / 100000000

# Writing hex values
amount_hex = hex(100 * 100000000)  # "0x2540be400"
```

### Error Handling

```python
# Fiber RPC errors raise Exception with error message
try:
    result = fiber.get_client().open_channel({...})
except Exception as e:
    error_msg = e.args[0]  # "Error: The funding amount (0) should be..."
```
