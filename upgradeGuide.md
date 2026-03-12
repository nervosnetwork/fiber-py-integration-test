# Fiber RPC Upgrade Guide: PeerId → Pubkey

> **Related PR**: [#1154](https://github.com/nervosnetwork/fiber/pull/1154)
>
> **Core Change**: All `peer_id` / `node_id` fields in RPC interfaces are unified and replaced with `pubkey` (secp256k1 compressed public key, 66-character hex string, without `0x` prefix).

---

## Field Change Quick Reference

| RPC Method | Location | Old Field | New Field |
|-----------|----------|-----------|-----------|
| `connect_peer` | Params | `address` (required) | `address` (optional) or `pubkey` (optional), one of the two |
| `disconnect_peer` | Params | `peer_id` (base58) | `pubkey` (hex) |
| `open_channel` | Params | `peer_id` (base58) | `pubkey` (hex) |
| `list_channels` | Params | `peer_id` (base58) | `pubkey` (hex) |
| `list_channels` | Response Channel | `peer_id` (base58) | `pubkey` (hex) |
| `list_peers` | Response PeerInfo | `peer_id` removed | only `pubkey` retained |
| `node_info` | Response | `node_id` | `pubkey` |
| `graph_nodes` | Response NodeInfo | `node_id` | `pubkey` |

---

## Migration Examples

### connect_peer (New pubkey-based connection method)

The old version only supported connecting via `address`:

```json
{
  "jsonrpc": "2.0",
  "method": "connect_peer",
  "params": [{ "address": "/ip4/127.0.0.1/tcp/8119/p2p/QmWJih5..." }]
}
```

The new version supports two methods, **choose one**:

**Method 1: Connect via address** (behavior unchanged)

```json
{
  "jsonrpc": "2.0",
  "method": "connect_peer",
  "params": [{
    "address": "/ip4/127.0.0.1/tcp/8119",
    "save": true
  }]
}
```

**Method 2: Connect via pubkey** (new)

```json
{
  "jsonrpc": "2.0",
  "method": "connect_peer",
  "params": [{
    "pubkey": "02a3bb31f957085a3837460d2c18bbb3186a76fce2a563dbed62ec1a0e58cef512"
  }]
}
```

> **Prerequisites**: Connecting via `pubkey` requires that the local node already knows the target node's network address. The node resolves the address from locally synced graph data and saved peer addresses, then automatically initiates the connection.
>
> **Applicable scenarios**:
> - The target node is a **public node** that has broadcast its address via `NodeAnnouncement` gossip messages, and the local node has already synced this information
> - The target node's address was previously saved via `connect_peer` (using `address` + `save: true`)
> - You can use the `graph_nodes` RPC to check whether the target node exists in the local graph
>
> **Not applicable**:
> - The target node is a **new node** being connected for the first time, with no address information in the local graph → use the `address` method instead
> - The target node is a **private node** that has never broadcast a `NodeAnnouncement` and has never been saved → the call will return an address resolution error
>
> **Note**: `address` and `pubkey` are mutually exclusive — exactly one must be provided, otherwise an error is returned.

**Test Cases** (see `test_cases/fiber/devnet/connect_peer/test_connect_peer.py`):
- `test_connect_peer_via_pubkey_success`: Connect via pubkey after address was saved with `save: true`
- `test_connect_peer_via_pubkey_failure`: Connect via unknown pubkey fails with address resolution error

### open_channel

```diff
 {
   "jsonrpc": "2.0",
   "method": "open_channel",
   "params": [{
-    "peer_id": "QmWJih5...",
+    "pubkey": "02a3bb31f957085a3837460d2c18bbb3186a76fce2a563dbed62ec1a0e58cef512",
     "funding_amount": "0x174876e800"
   }]
 }
```

### list_channels

```diff
 // Params
-{ "peer_id": "QmWJih5..." }
+{ "pubkey": "02a3bb31..." }

 // Response Channel object
 {
   "channel_id": "0x...",
-  "peer_id": "QmWJih5...",
+  "pubkey": "02a3bb31...",
   ...
 }
```

### disconnect_peer

```diff
-{ "peer_id": "QmWJih5..." }
+{ "pubkey": "02a3bb31..." }
```

### list_peers response

```diff
 {
-  "pubkey": "02a3bb31...",
-  "peer_id": "QmWJih5...",
+  "pubkey": "02a3bb31...",
   "address": "/ip4/127.0.0.1/tcp/8119"
 }
```

> The `peer_id` field has been removed; only `pubkey` is retained.

### node_info response

```diff
 {
   "version": "0.5.0",
-  "node_id": "02a3bb31...",
+  "pubkey": "02a3bb31...",
   ...
 }
```

### graph_nodes response

```diff
 {
   "node_name": "my-node",
-  "node_id": "02a3bb31...",
+  "pubkey": "02a3bb31...",
   ...
 }
```

---

## How to Obtain the Pubkey

| Method | Description |
|--------|-------------|
| `node_info` | Call the target node to get its `pubkey` |
| `list_peers` | Get the `pubkey` of connected peers |
| `graph_nodes` | Get the `pubkey` of known nodes in the network |

---

## Important Notes

- **Type change**: `peer_id` was a base58 string (PeerId hash), while `pubkey` is a 66-character hex string (secp256k1 compressed public key, **without `0x` prefix**). The two are **not interchangeable**.
- **`connect_peer` changes**: A new `pubkey` parameter has been added — the node resolves the peer's address from locally synced graph data; the `address` field changed from required to optional (mutually exclusive with `pubkey`); a new optional `save` parameter controls whether to persist the peer address.
- **Database migration**: After upgrading, a channel index migration (PeerId → Pubkey) will be executed automatically. No manual action is required.
- **Unchanged RPCs**: `accept_channel`, `abandon_channel`, `shutdown_channel`, `update_channel`, `send_payment`, and other interfaces that use `channel_id` are not affected.