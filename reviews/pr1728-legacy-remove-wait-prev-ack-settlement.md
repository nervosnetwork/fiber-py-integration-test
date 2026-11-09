# PR #1728：Legacy 通道 `RemoveWaitPrevAck` 结算余额用例评审

范围：Legacy（V1）通道里本端发出的 TLC 已被对端移除、又在等待上一个 ACK 时收到对端 `CommitmentSigned`（状态 `RemoveWaitPrevAck`）时，本端承诺的结算余额要计入移除结果。V2 和远端承诺不变。

依据：[PR #1728](https://github.com/nervosnetwork/fiber/pull/1728)，2026-11-09 合入 develop，merge commit `7aa1d5de724fb28b8ddfc663f5da792ff48f1ee9`，即 `v0.10.0-rc2` tag 本身。改动为 [`build_settlement_data`](https://github.com/nervosnetwork/fiber/blob/7aa1d5de724fb28b8ddfc663f5da792ff48f1ee9/crates/fiber-lib/src/fiber/channel.rs) 中 `(v2 || !for_remote) && RemoveWaitPrevAck` 时使用移除原因。

测试仓库基线：`v0.10.0` 分支 `bd1051d`（PR #110 head）。本轮只做静态分析。

## 变更与现有测试影响

- 修复前：V1 本端承诺不含处于 `RemoveWaitPrevAck` 的已发 TLC 输出，但余额也没把移除结果算进去：fail 时退款没回到本端，fulfill 时金额没给对端，结算总额少了 TLC 金额。上游单测里 1000 的通道算成 700。
- 本端承诺（`for_remote=false`）用于验证对端发来的 `CommitmentSigned`，也用于本端强关广播。错误余额可能导致签名验证失败而卡住，或强关时资金分配错误。待确认：修复前在真实节点上的具体表现（拒绝 CS / 断连 / 强关后金额错），由首个用例在修复前构建上的结果确定，不预先写成契约。
- 上游新增 2 条单测（fail 退款、fulfill 转给对端）。集成侧需要一个能拦截消息的对端：攻击方先移除 TLC，压住自己的 `CommitmentSigned`；受害方再发一次 CS（等待 ACK），攻击方丢弃 RAA；之后放出压住的 CS，让受害方的 TLC 进入 `RemoveWaitPrevAck`。`list_channels` 的 `pending_tlcs[].status` 可直接看到 `RemoveWaitPrevAck`。
- 需要 Legacy 通道：沿用 old-old 做法（两端 v0.9.1 开通道，受害方升级到 `CURRENT_DEV`，攻击方升级到 `ATTACK_FULL_HASH_DEV` + `LEGACY_COUNTERPARTY_ENV`）。现有 `security/test_announce_wait_prev_ack_onchain_panic.py` 是入站方向的同类构造，可复用其拦截与链上余额读取方式。
- 新文件放在 `test_cases/fiber/devnet/security/`，标 `requires_attack_fnn`，由 `fiber-attack-fnn.yml` 的“remaining tests”步骤收集。

## Spec

### SPEC-01：fail 后进入 RemoveWaitPrevAck，本端承诺把 TLC 金额退回本端
Condition: Legacy 通道，受害方发出 TLC，攻击方以 `RemoveTlcFail` 移除；受害方在等待上一 ACK 时收到攻击方 CS，TLC 为 `RemoveWaitPrevAck`。
Expected: 受害方接受该 CS（通道保持 `ChannelReady`，不断开）；此时受害方强关，广播的本端承诺不含该 TLC 输出，结算后受害方所得等于付款前本端余额（扣除交易费），攻击方所得等于其付款前余额。
Observable: `pending_tlcs` 状态、通道状态、付款状态、`local_balance`；强关后链上受害方地址容量变化。
Basis: [PR 说明](https://github.com/nervosnetwork/fiber/pull/1728)、上游 `failed_offered_tlc_in_remove_wait_prev_ack_is_refunded_on_local_commitment`。
Source: explicit
Testing: required

### SPEC-02：fulfill 后进入 RemoveWaitPrevAck，本端承诺把 TLC 金额给对端
Condition: 同上，但攻击方以正确原像 `RemoveTlcFulfill`。
Expected: 受害方接受该 CS；此时受害方强关，本端承诺不含该 TLC 输出，结算后受害方所得比付款前本端余额少付款金额，攻击方多付款金额（均扣除交易费），双方合计等于通道总额。
Observable: 同 SPEC-01。
Basis: [PR 说明](https://github.com/nervosnetwork/fiber/pull/1728)、上游 `fulfilled_offered_tlc_in_remove_wait_prev_ack_moves_to_remote_balance`。
Source: explicit
Testing: required

## 测试树

<!-- TEST-TREE-BEGIN -->
- Legacy 本端承诺的 RemoveWaitPrevAck
  - 移除原因为 fail
    - PR1728-01 [primary] -> SPEC-01：CS 被接受，退款回本端，强关金额正确
  - 移除原因为 fulfill
    - PR1728-02 [primary] -> SPEC-02：CS 被接受，金额给对端，强关金额正确
  - [not_applicable] V2 通道与远端承诺 — PR 声明行为不变；V2 已有对应分支
  - [unanalysed] 两端都是 stock 节点、双向并发付款自然触发 — 时序不可控，不适合 CI；可作为后续压测观察项
<!-- TEST-TREE-END -->

## 用例

共同前提：两端 v0.9.1 开 Legacy 通道（受害方出资，攻击方 auto-accept），受害方升级为 `CURRENT_DEV`、攻击方升级为 `ATTACK_FULL_HASH_DEV` + `LEGACY_COUNTERPARTY_ENV` 并重连，通道 `ChannelReady`。记录双方通道余额和链上地址容量。受害方给攻击方付一笔款，TLC 记为 X。构造顺序：攻击方移除 X 并压住（hold）自己发出的 `CommitmentSigned`；受害方收到移除后，自己再发起一次更新（第二笔小额付款）发出 CS，攻击方丢弃 RAA；然后攻击方放出压住的 CS。强关用 `shutdown_channel(force=true)`，按仓库现有方式出块、跨过 commitment delay，等结算交易上链。所有等待有上限。

<!-- TEST-CASES-BEGIN -->
| 用例 | 场景 | 预期结果 | 防止的问题 | 优先级 |
| --- | --- | --- | --- | --- |
| `PR1728-01` | - [ ] 攻击方用 `RemoveTlcFail` 移除 X，按共同前提让受害方的 X 进入 `RemoveWaitPrevAck`；确认后受害方强关并完成链上结算 | 受害方 `pending_tlcs` 中 X 为 `RemoveWaitPrevAck`，此时通道仍 `ChannelReady`；强关的承诺交易上链，结算后受害方得到付款前本端余额（扣交易费），攻击方得到其付款前余额 | Legacy 本端承诺漏算 fail 退款，CS 验签失败卡住或强关时少拿钱 | P0 |
| `PR1728-02` | - [ ] 攻击方用正确原像 `RemoveTlcFulfill` 移除 X，其余同 `PR1728-01` | X 为 `RemoveWaitPrevAck`、通道仍 `ChannelReady`；强关结算后受害方所得比付款前本端余额少 X 金额，攻击方多 X 金额（均扣交易费），合计等于通道总额 | Legacy 本端承诺漏算 fulfill 给对端的金额，导致总额不守恒或对端拿不到已结算的钱 | P0 |
<!-- TEST-CASES-END -->

## 验证设计

- 独立预期：金额来自测试选定的付款金额和记录的付款前余额，不读取节点计算出的结算数据；交易费用链上交易实际 fee 扣减。
- 实际入口与观察：受害方是 stock FNN，经真实 P2P 收到攻击方的移除与 CS；攻击方只拦截 / 延迟自己的消息。观察受害方 `list_channels`、CKB 链上交易和地址容量。
- 缺陷敏感性：`PR1728-01` 首例实现后，在修复前的构建（`7aa1d5de` 的父提交）上运行一次，记录实际失败方式，用来回答“修复前表现”的待确认项；若修复前也通过，说明该构造没有打到缺陷，需回到 G1 调整。
- 证明边界：只覆盖受害方本端承诺；不覆盖远端承诺、V2 通道和 watchtower 代为结算。
