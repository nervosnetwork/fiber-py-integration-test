# PR #1711：V1 通道重连后对端不发 `ReestablishChannel` 的强关用例评审

范围：Legacy（V1，`session_v2=None`）通道重连后的 reestablish 超时、离线时间不计时、对端已应答（含被拒绝的握手）后停止计时。V2 自身的 reestablish watchdog（#1677）不在本批范围。

依据：[PR #1711](https://github.com/nervosnetwork/fiber/pull/1711)，2026-11-05 合入 develop，merge commit `ab6364f1169bde596a7342f08767e79a4750a8ca`，head `3c8ff0536ad5d720dcc50776504f2002ae558b50`；本仓库 CI 固定的 `v0.10.0-rc2`（`7aa1d5de724fb28b8ddfc663f5da792ff48f1ee9`）已包含该提交。改动集中在 [`channel.rs`](https://github.com/nervosnetwork/fiber/blob/7aa1d5de724fb28b8ddfc663f5da792ff48f1ee9/crates/fiber-lib/src/fiber/channel.rs) 的 `is_reestablish_stalled`、`on_peer_disconnected` / `on_peer_reconnected` 和收到 `ReestablishChannel` 时清空计时。

测试仓库基线：`v0.10.0` 分支 `bd1051d`（PR #110 head）。本批三条用例已于 2026-11-10 确认（G1）；`PR1711-03` 按确认意见只断言“没有超时强关”。

## 变更与现有测试影响

- 修复前：`REESTABLISH_TIMEOUT` 只在 V2 路径生效；V1 对端重连后若一直不发 `ReestablishChannel`，本端保持 `reestablishing=true`，忽略对端其它消息、TLC 移除被阻塞，通道永久停在 `ChannelReady`。
- 修复后：V1 在每次 `MaintainChannelTlcs` 检查 `is_reestablish_stalled`：仅 `ChannelReady`，或尚未广播承诺交易的 `ShuttingDown`；连接状态为 `Syncing`；距重连超过 `REESTABLISH_TIMEOUT`。满足时本端强关。
- 计时从重连开始，掉线时清空；收到对端 `ReestablishChannel` 后无论握手成功与否都清空（握手被拒说明本端承诺可能过期，强关可能广播已撤销的承诺）。
- 非 test 构建：`REESTABLISH_TIMEOUT = 300s`；`CHECK_CHANNELS_INTERVAL` 在 release 构建为 60s、debug 构建为 3s。CI 的 `build_attack_fnn.sh` 用 debug profile 构建（不带 `cfg(test)`），即 300s / 3s，强关发生在重连后约 300–303s。用例上界按 60s 取，release 构建也适用。
- 上游新增 4 条 Rust 用例：withheld 强关、离线不计时、拒绝握手后停表、`is_reestablish_stalled` 状态表。集成侧只能从 RPC 和链上观察，不读取 `reestablish_started_at`。
- 本仓库没有 V1 通道 reestablish 超时的集成用例。可复用 `P2pFiberTest` 与 `compatibility/test_full_hash_bad_preimage.py` 中 old-old 通道的做法：两端 v0.9.1 开 Legacy 通道，再把受害方升级到 `CURRENT_DEV`、攻击方升级到 `ATTACK_FULL_HASH_DEV`（`LEGACY_COUNTERPARTY_ENV`）。攻击方 `set_fiber_message_intercept` 的 `outbound_drop_kinds=["ReestablishChannel"]` 可让它不发握手。

## Spec

### SPEC-01：V1 对端重连后不发握手，超时后本端强关
Condition: V1 通道 `ChannelReady`；对端断开后重连，但从不发送 `ReestablishChannel`。
Expected: 本端在重连后超过 `REESTABLISH_TIMEOUT`、且不晚于其后若干个检查周期内强关；不早于重连后 `REESTABLISH_TIMEOUT`。
Observable: `list_channels` 的通道状态从 `ChannelReady` 变为 `ShuttingDown`（`WAITING_COMMITMENT_CONFIRMATION`）或 `Closed`（`UNCOOPERATIVE_LOCAL`）；本端承诺交易进入交易池并可上链。
Basis: [PR 说明](https://github.com/nervosnetwork/fiber/pull/1711)、[`is_reestablish_stalled`](https://github.com/nervosnetwork/fiber/blob/7aa1d5de724fb28b8ddfc663f5da792ff48f1ee9/crates/fiber-lib/src/fiber/channel.rs)。
Source: explicit
Testing: required

### SPEC-02：离线时间不计入超时，对端回来后正常恢复
Condition: V1 通道 `ChannelReady`；对端进程停止的时间超过 `REESTABLISH_TIMEOUT` 加两个检查周期。
Expected: 离线期间通道保持 `ChannelReady`；对端重启并重连后完成 reestablish，之后再过一个超时窗口仍不强关，通道可继续付款。
Observable: 离线期间及恢复后的通道状态；恢复后一笔付款 `Success`，双方余额按金额变化。
Basis: [PR 说明](https://github.com/nervosnetwork/fiber/pull/1711)、[`on_peer_disconnected` 清空计时](https://github.com/nervosnetwork/fiber/blob/7aa1d5de724fb28b8ddfc663f5da792ff48f1ee9/crates/fiber-lib/src/fiber/channel.rs)。
Source: explicit
Testing: required

### SPEC-03：对端已发握手但被拒绝，计时停止，不强关
Condition: V1 通道重连；对端不发正常握手，改发一条承诺编号超前的 `ReestablishChannel`，本端拒绝。
Expected: 本端不因 reestablish 超时强关，不广播承诺交易。
Observable: 超过超时窗口后通道仍不是 `ShuttingDown(WAITING_COMMITMENT_CONFIRMATION)` / `Closed(UNCOOPERATIVE_LOCAL)`，交易池无本通道承诺交易。按 2026-11-10 确认，只断言没有超时强关，不断言握手被拒后的最终通道状态。
Basis: [PR 说明](https://github.com/nervosnetwork/fiber/pull/1711)、[收到握手即清空计时](https://github.com/nervosnetwork/fiber/blob/7aa1d5de724fb28b8ddfc663f5da792ff48f1ee9/crates/fiber-lib/src/fiber/channel.rs)、上游 `test_reestablish_timeout_stops_after_rejected_handshake`。
Source: explicit
Testing: required

## 测试树

<!-- TEST-TREE-BEGIN -->
- V1 通道 reestablish 超时
  - 对端重连但不发握手
    - PR1711-01 [primary] -> SPEC-01：超时窗口内本端强关，且不早于超时
  - 对端离线
    - PR1711-02 [primary] -> SPEC-02：离线超过超时不强关；回来后恢复并可付款
  - 对端握手被拒绝
    - PR1711-03 [primary] -> SPEC-03：停表，不超时强关
  - [not_applicable] V2 通道 — 走 #1677 的独立 watchdog，本 PR 显式排除 V2
  - [unanalysed] `ShuttingDown`（未广播承诺）期间对端不发握手 — 需要先让协商关闭卡在 Shutdown 再断线；后续从 `shutdown_channel` + 拦截 `ClosingSigned` 入手
  - [unanalysed] `Stale` 通道不强关 — 需要备份恢复构造 Stale；上游状态表用例已覆盖
<!-- TEST-TREE-END -->

## 用例

共同前提：两端 v0.9.1 开 Legacy 通道并 `ChannelReady`，然后受害方以 `CURRENT_DEV`（v0.10.0-rc2）、攻击方以 `ATTACK_FULL_HASH_DEV` + `LEGACY_COUNTERPARTY_ENV` 重启并重连，确认通道仍 `ChannelReady`；受害方给攻击方付一笔款确认通道可用。下文 T=300s（`REESTABLISH_TIMEOUT`），I=60s（`CHECK_CHANNELS_INTERVAL` 的 release 值，作为上界；CI debug 构建实际为 3s）。所有等待有上限。

<!-- TEST-CASES-BEGIN -->
| 用例 | 场景 | 预期结果 | 防止的问题 | 优先级 |
| --- | --- | --- | --- | --- |
| `PR1711-01` | - [x] 攻击方先设置 `outbound_drop_kinds=["ReestablishChannel"]`，受害方 `disconnect_peer` 后再 `connect_peer`，记录重连时间，轮询受害方通道状态最长 T+3I | 重连后不早于 T、不晚于 T+3I，受害方通道变为 `ShuttingDown(WAITING_COMMITMENT_CONFIRMATION)` 或 `Closed(UNCOOPERATIVE_LOCAL)`；出块后受害方承诺交易上链 | V1 对端扣住握手，通道永远卡在 `ChannelReady`、对端发来的 TLC 无法处理 | P0 |
| `PR1711-02` | - [ ] 停止攻击方进程，确认受害方通道离线后等待 T+2I；再启动攻击方（不设拦截）并重连，等 reestablish 完成后再等 T+I，然后付一笔款 | 离线期间和恢复后受害方通道始终 `ChannelReady`，没有承诺交易进池；最后的付款 `Success`，双方余额按金额变化 | 把离线时间算进超时，对端一回来（或离线中）就被误强关 | P1 |
| `PR1711-03` | - [ ] 攻击方设置 `outbound_drop_kinds=["ReestablishChannel"]`，受害方断开并重连后，攻击方用 `send_reestablish` 发一条 `local_commitment_number` 比正常值大 2 的握手；之后等待 T+3I | 受害方不因超时强关：通道状态不是 `ShuttingDown(WAITING_COMMITMENT_CONFIRMATION)` / `Closed(UNCOOPERATIVE_LOCAL)`，交易池里没有本通道承诺交易；不断言最终通道状态 | 握手被拒（本端可能过期）后仍超时强关，广播已撤销的承诺而被对端惩罚 | P1 |
<!-- TEST-CASES-END -->

## 验证设计

- 独立预期：T、I 取自目标构建的非 test 常量；强关判据用 RPC 通道状态加链上承诺交易，不读节点内部字段。V1 前提由“通道由两端 v0.9.1 创建”保证，强关后可再用承诺交易 lock args 长度核对为 Legacy 布局。
- 实际入口与观察：受害方是未改动的 stock FNN，经真实 P2P 断连 / 重连；攻击方只通过调试 RPC 丢弃或伪造自己发出的握手。观察受害方 `list_channels`、CKB 交易池与链上交易。
- 缺陷敏感性：`PR1711-01` 在修复前的 stock 构建上应在 T+3I 后仍为 `ChannelReady`（旧 V1 无此超时），可作为负对照；`02`、`03` 是防止修复过度的约束，修复前同样通过，不作负对照。
- 证明边界：只证明受害方在真实节点上会 / 不会超时强关，不证明 V2 watchdog、Stale 通道或备份恢复路径。

## 自动化与验证（2026-11-10，G2 首例）

`PR1711-01` 映射到 `test_cases/fiber/devnet/security/test_pr1711_v1_reestablish_timeout.py::TestPr1711V1ReestablishTimeout::test_peer_withholds_reestablish_victim_force_closes_after_timeout`，继承 `P2pFiberTest`（`requires_attack_fnn`），由 `fiber-attack-fnn.yml` 的 “remaining tests marked requires_attack_fnn” 步骤收集，不改 workflow。`02`、`03` 待 G2 确认后实现。

本地二进制均按 `scripts/build_attack_fnn.sh` 的 debug profile 构建（`cargo build --locked --bin fnn`）：

| 角色 | 源码 | SHA-256 |
| --- | --- | --- |
| 受害方（修复后，CI 固定） | `nervosnetwork/fiber` `v0.10.0-rc2` = `7aa1d5de` | `649332131c357c21d06870d99ccf57876282596cc67a483ad35b241bb2cb9247` |
| 受害方（修复前，负对照） | `3bdb69f6`（#1711 合并提交 `ab6364f1` 的第一父提交） | `a91f95ced20d2454e322760c308854eb33953435efaf754185ad6dc10c731db5` |
| 攻击方（两次相同） | `gpBlockchain/fiber` `p2p-tap-full-payment-hash` = `b7a5299a` | `d191b459fbd7f943bd3aa6ed8b7a6b3986124b9cd9d762b5ec188970034f3856` |
| 建通道用 | 官方 release v0.9.1（`download_fiber.py`） | `1acf715c68641393817d3acd3bb142bce4a7711e7d23a8c282a51ed41e797e3a` |

命令（仓库根目录，`download/fiber/current/fnn` 换成对应受害方构建）：

```bash
python -m pytest -o addopts= --strict-markers -vv -s --tb=short -m requires_attack_fnn \
  test_cases/fiber/devnet/security/test_pr1711_v1_reestablish_timeout.py
```

- 修复后：`1 passed`，447s，退出码 0。断开后 0.5s 重连；断开后 306s 受害方变为 `ShuttingDown(WAITING_COMMITMENT_CONFIRMATION)`，日志为 `has been waiting over 300000 ms for the reconnected peer's ReestablishChannel, shutting down it forcefully`；资金 cell 被已上链交易 `0x974ec508f5087a3c6113f207d45c1e14243709dd1ae16454c195fabda7026ec8` 花费。
- 修复前：`1 failed`，611s，退出码 1。重连后 480s（上界 T+3I）受害方仍是 `ChannelReady`，日志里没有 reestablish 超时记录，失败在步骤 3 的强关断言。
- 本地运行注意：沙箱机器在 agent 空闲等待时会被挂起（节点日志每 60s 一次的 watchtower 检查出现 7–9 分钟空档），挂起期间的两次早期运行墙钟时间不可信，不计入上面的结果。用例已改为超过上界后再取一次最新状态才判失败，避免拿挂起前的旧状态误判。
- 检查：`check_test_design.py --review` 三份文档 rc=0；`scripts/check_test_map.py` 中 `PR1711-01` 已映射、无新增孤儿或重复 ID，其余未映射的本批 ID 为 `PR1705-01/02`、`PR1711-02/03`、`PR1728-01/02`（rc=1 来自既有的 `PMP-01..05`、`SETTLE-01` 孤儿映射及旧的未映射项）。
