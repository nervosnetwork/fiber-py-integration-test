# Lightning Network Concepts in Fiber

## Architecture Comparison

| Concept | Bitcoin Lightning | Fiber Network |
|---------|------------------|---------------|
| Base Layer | Bitcoin | Nervos CKB |
| Channel Contract | 2-of-2 multisig | CKB FundingLock + CommitmentLock |
| Hash Lock | HTLC | TLC (Time-Locked Contract) |
| Invoice Format | BOLT11 (`lnbc...`) | CKB Invoice (`fibd/fibt/fib...`) |
| Token Support | BTC only | CKB + UDTs (User Defined Tokens) |
| Routing | Source routing | Source + Trampoline routing |
| Implementation | LND/CLN/Eclair (Go/C/Scala) | FNN (Rust, Actor-based) |

## Channel Lifecycle Mapping

**Bitcoin LN**: funding_created → funding_signed → funding_locked → normal → shutdown → closing_signed

**Fiber**: NEGOTIATING_FUNDING → COLLABORATING_FUNDING_TX → SIGNING_COMMITMENT → AWAITING_TX_SIGNATURES → AWAITING_CHANNEL_READY → CHANNEL_READY → SHUTTING_DOWN → CLOSED

## TLC Parameters (Fiber's HTLC equivalent)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `tlc_expiry_delta` | 86400000ms (1 day) | Per-hop time added |
| `tlc_min_value` | 0 | Min TLC amount |
| `tlc_max_value` | 0 (unlimited) | Max TLC amount |
| `tlc_fee_proportional_millionths` | 1000 (0.1%) | Routing fee |
| `max_tlc_number_in_flight` | 125 (system max 253) | Concurrent TLCs |
| `max_tlc_value_in_flight` | u128::MAX | Total TLC value |
| `commitment_delay_epoch` | 1 (range 1-84) | Dispute timeout |

## Key Differences from Bitcoin LN

1. **Multi-Asset**: CKB + UDT channels (vs BTC only)
2. **Cell Model**: CKB's generalized UTXO with `capacity`, `lock_script`, `type_script`, `data`
3. **Epoch Timelocks**: CKB epochs + ms timestamps (vs block height/Unix time)
4. **Trampoline Routing**: Sender delegates route-finding to intermediate node (max 5 hops)
5. **Actor Architecture**: Ractor actors (NetworkActor, ChannelActor, PaymentActor, CkbChainActor, CchActor)
6. **WASM Client**: Browser-based Fiber client via WebAssembly
7. **Biscuit Auth**: Token-based RPC authentication (vs Macaroons in LND)
8. **Cross-Chain Hub (CCH)**: Native BTC Lightning ↔ CKB Fiber bridge

## Gossip Protocol

- **Active sync**: Pull missed messages from peers on connect
- **Passive sync**: Subscribe to peer updates via filters
- Messages: NodeAnnouncement, ChannelAnnouncement, ChannelUpdate
- Cursor-based pagination for incremental sync

## Watchtower

- **Built-in**: Each node monitors its own channels
- **Standalone**: External watchtower via `standalone_watchtower_rpc_url`
- Check interval: `watchtower_check_interval_seconds` (default 60s)
- Dispute flow: Force close → timelock → watchtower detects → penalty/settlement tx

## Cross-Chain Hub (CCH)

```
Bitcoin LN ←→ CCH (LND RPC) ←→ Fiber Network
```
- `send_btc`: Pay BTC Lightning invoice using CKB Fiber
- `receive_btc`: Receive BTC Lightning payment into Fiber
- Order lifecycle: Pending → IncomingAccepted → OutgoingInFlight → Succeeded/Failed
- Hash algorithm must be SHA256 for CCH compatibility
