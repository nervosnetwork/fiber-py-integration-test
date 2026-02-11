# Fiber RPC API Reference

## Channel Module

```python
# open_channel - Open payment channel
fiber.get_client().open_channel({
    "peer_id": "Qm...",                    # Required
    "funding_amount": "0x2540be400",        # Required (hex Shannon)
    "public": True,                          # Optional (announce to network)
    "funding_udt_type_script": None,        # Optional (UDT channels)
    "commitment_fee_rate": "0x3e8",         # Optional
    "commitment_delay_epoch": "0x06",       # Optional (1-84 epochs)
    "funding_fee_rate": "0x3e8",            # Optional
    "tlc_expiry_delta": "0x5265c00",        # Optional (ms)
    "tlc_min_value": "0x0",                 # Optional
    "tlc_max_value": "0x0",                 # Optional (0=unlimited)
    "tlc_fee_proportional_millionths": "0x3e8",  # Optional (1000=0.1%)
    "max_tlc_value_in_flight": "0x0",       # Optional
    "max_tlc_number_in_flight": "0x0",      # Optional (max 253)
    "shutdown_script": {...},                # Optional
    "one_way": False,                        # Optional
})
# Returns: {"temporary_channel_id": "0x..."}

# accept_channel
fiber.get_client().accept_channel({
    "temporary_channel_id": "0x...",
    "funding_amount": "0x...",
    "tlc_fee_proportional_millionths": "0x3e8",
})

# list_channels
channels = fiber.get_client().list_channels({
    "peer_id": "Qm...",           # Optional filter
    "include_closed": False,       # Optional
})
# Returns: {"channels": [{channel_id, peer_id, state, local_balance, remote_balance,
#   offered_tlc_balance, received_tlc_balance, funding_udt_type_script, created_at,
#   channel_outpoint, enabled, pending_tlcs, tlc_fee_proportional_millionths, ...}]}

# shutdown_channel
fiber.get_client().shutdown_channel({
    "channel_id": "0x...",
    "force": False,           # True for unilateral close
    "close_script": {...},    # Optional
    "fee_rate": "0x3e8",      # Optional
})

# update_channel
fiber.get_client().update_channel({
    "channel_id": "0x...",
    "enabled": True,                                # Optional
    "tlc_fee_proportional_millionths": "0x3e8",    # Optional
    "tlc_expiry_delta": "0x5265c00",               # Optional
    "tlc_min_value": "0x0",                         # Optional
    "tlc_max_value": "0x0",                         # Optional
})

# abandon_channel (only before CHANNEL_READY)
fiber.get_client().abandon_channel({"channel_id": "0x..."})
```

## Payment Module

```python
# send_payment (keysend)
payment = fiber.get_client().send_payment({
    "target_pubkey": "02...",           # Required for keysend
    "amount": "0x2540be400",            # Required for keysend
    "keysend": True,                     # Required for keysend
    "allow_self_payment": True,         # Optional
    "udt_type_script": None,            # Optional
    "max_fee_amount": "0x...",          # Optional
    "final_tlc_expiry_delta": "0x...",  # Optional
    "tlc_expiry_limit": "0x...",        # Optional
    "max_parts": "0xc",                 # Optional (for MPP)
    "dry_run": False,                    # Optional
    "custom_records": {...},            # Optional (max 2KB)
})

# send_payment (invoice)
payment = fiber.get_client().send_payment({
    "invoice": "fibd11p...",
    "allow_self_payment": True,
    "max_parts": "0xc",
    "amp": True,                # Optional (atomic MPP)
})
# Returns: {"payment_hash": "0x...", "status": "Created"}

# get_payment
result = fiber.get_client().get_payment({"payment_hash": "0x..."})
# Returns: {payment_hash, status (Created|Inflight|Success|Failed), fee, ...}

# build_router / send_payment_with_router
route = fiber.get_client().build_router({...})
payment = fiber.get_client().send_payment_with_router({...})
```

## Invoice Module

```python
# new_invoice (standard - auto-settles)
invoice = fiber.get_client().new_invoice({
    "amount": hex(100 * 100000000),
    "currency": "Fibd",                    # Fibd|Fibt|Fib
    "description": "test",
    "payment_preimage": "0x...",           # 32-byte hex
    "hash_algorithm": "sha256",            # sha256|ckb_hash
    "expiry": "0xe10",                     # Optional (seconds)
    "udt_type_script": None,               # Optional
})

# new_invoice (hold - manual settle required)
invoice = fiber.get_client().new_invoice({
    "amount": hex(1 * 100000000),
    "currency": "Fibd",
    "description": "hold",
    "payment_hash": "0x...",               # Only hash, no preimage
    "hash_algorithm": "sha256",
})

# parse_invoice / get_invoice / cancel_invoice / settle_invoice
parsed = fiber.get_client().parse_invoice({"invoice": "fibd..."})
inv = fiber.get_client().get_invoice({"payment_hash": "0x..."})
fiber.get_client().cancel_invoice({"payment_hash": "0x..."})
fiber.get_client().settle_invoice({"payment_hash": "0x...", "payment_preimage": "0x..."})
```

## Peer / Graph / Info Module

```python
fiber.get_client().connect_peer({"address": "/ip4/.../tcp/.../p2p/Qm..."})
# Or helper: fiber1.connect_peer(fiber2)
fiber.get_client().disconnect_peer({"peer_id": "Qm..."})
peers = fiber.get_client().list_peers()

nodes = fiber.get_client().graph_nodes({"limit": "0x10", "after": "0x..."})
channels = fiber.get_client().graph_channels({"limit": "0x10", "after": "0x..."})

info = fiber.get_client().node_info()
# Returns: {version, commit_hash, node_id, peer_id, addresses, chain_hash,
#   open_channel_auto_accept_min_ckb_funding_amount, tlc_expiry_delta,
#   tlc_fee_proportional_millionths, channel_count, pending_channel_count,
#   peers_count, network_sync_status, udt_cfg_infos}
```

## CCH Module (requires FiberCchTest)

```python
fiber.get_client().send_btc({"btc_pay_req": "lnbc..."})
fiber.get_client().receive_btc({"amount": "0x...", "currency": "Fibd"})
fiber.get_client().get_cch_order({"payment_hash": "0x..."})
```

## Dev Module (testing only)

```python
fiber.get_client().add_tlc({"channel_id": "0x...", "amount": "0x...", "payment_hash": "0x...", "expiry": "0x..."})
fiber.get_client().remove_tlc({"channel_id": "0x...", "tlc_id": "0x...", "reason": {...}})
```

## Common Patterns

```python
# Hex conversion
balance = int(channel["local_balance"], 16)
amount_hex = hex(100 * 100000000)  # "0x2540be400"

# Error handling
try:
    result = fiber.get_client().open_channel({...})
except Exception as e:
    error_msg = e.args[0]  # "Error: ..."

# SHA256 for hold invoices
import hashlib
def sha256_hex(preimage_hex):
    raw = bytes.fromhex(preimage_hex.replace("0x", ""))
    return "0x" + hashlib.sha256(raw).hexdigest()
```
