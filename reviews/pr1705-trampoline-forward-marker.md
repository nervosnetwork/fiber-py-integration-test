# PR #1705：TLC 离开通道时清除 trampoline 转发标记用例评审

范围：trampoline 节点在转发成功 / 失败后清除 `waiting_forward_tlc_tasks` 标记，以及同时引入的“被转发的 TLC 不能结算转发节点自己同 hash 发票”的约束、重启时清理旧标记。只用两端 stock FNN 的 RPC 可观察结果。

依据：[PR #1705](https://github.com/nervosnetwork/fiber/pull/1705)，2026-11-05 合入 develop，merge commit `811db5bc8096fab19852bcdc3b20709db8655047`，head `f2f06c48d1002cef2ddd9130974fcd086f8e6dad`；CI 固定的 `v0.10.0-rc2`（`7aa1d5de`）已包含。改动在 [`channel.rs`](https://github.com/nervosnetwork/fiber/blob/7aa1d5de724fb28b8ddfc663f5da792ff48f1ee9/crates/fiber-lib/src/fiber/channel.rs)：`apply_remove_tlc` 删除标记；移除前记录 `was_waiting_forward`；失败 TLC 打 `AppliedFlags::REMOVE`；恢复通道时 `drop_stale_waiting_forward_tlc_tasks`。

测试仓库基线：`v0.10.0` 分支 `bd1051d`（PR #110 head）。本轮只做静态分析。

## 变更与现有测试影响

- 修复前：trampoline 转发在 `register_and_apply_forward_tlc` 插入标记，但走的是新建付款，不会收到 `ForwardTlcResult`，标记一直留在通道状态里（持久化），只会越积越多。
- 修复后：TLC 移除时一起删标记。由于删除发生在结算判断之前，PR 同时改成用移除前的 `was_waiting_forward` 判断：被转发的 TLC fulfill 时，不能把转发节点自己同 `payment_hash` 的发票标成 Paid。
- 标记本身不在任何 RPC 中暴露；泄漏的直接后果是状态膨胀，不改变付款结果。因此集成侧可观察的是：转发节点自有发票不被误结算、成功 / 失败转发后 TLC 清空且余额守恒、重启后通道继续可用。
- 上游新增 `test_trampoline_forward_marker_lifecycle`、`test_trampoline_fulfill_does_not_settle_forwarder_invoice` 以及两条状态单测（只修剪已确认的失败 TLC 标记、恢复时清理旧标记）。
- 本仓库 `test_cases/fiber/devnet/trampoline_routing/` 已在 `fiber.yml` 的 `fiber_test_trampoline_routing_one_way` job 中运行，新文件放在该目录即可被 CI 收集。现有用例不涉及转发节点自有同 hash 发票。

## Spec

### SPEC-01：被转发的 TLC 结算时不结算转发节点自己的同 hash 发票
Condition: A→T→C，T 为 trampoline；C 持单发票已收到 TLC；T 之后自己也建一张同 `payment_hash` 的持单发票；C 用原像结算。
Expected: A 付款 `Success`，C 发票 `Paid`；T 自己的发票保持 `Open`。对照：A 直接付 T 的普通发票，T 发票变 `Paid`。
Observable: 三方 `get_payment` / `get_invoice` 状态。
Basis: [PR diff 中的 `was_waiting_forward`](https://github.com/nervosnetwork/fiber/pull/1705/files)、上游 `test_trampoline_fulfill_does_not_settle_forwarder_invoice`。
Source: explicit
Testing: required

### SPEC-02：trampoline 转发成功与失败后，转发节点通道上的 TLC 全部离开且余额守恒，重启后可继续使用
Condition: A→T→C 公开通道，另有与网络不连通的节点 B；A 经 T 多次付 C（成功）和付 B（失败）。
Expected: 成功付款 `Success`、失败付款 `Failed`；T 两条通道的 `pending_tlcs` 最终为空；失败付款不改变 A–T 余额，成功付款按金额加手续费变化。T 重启并重连后，再经 T 付 C 成功。
Observable: `list_channels` 的 `pending_tlcs`、`local_balance` / `remote_balance`，付款状态。
Basis: [PR 说明](https://github.com/nervosnetwork/fiber/pull/1705)、[`drop_stale_waiting_forward_tlc_tasks`](https://github.com/nervosnetwork/fiber/blob/7aa1d5de724fb28b8ddfc663f5da792ff48f1ee9/crates/fiber-lib/src/fiber/channel.rs)、上游 `test_trampoline_forward_marker_lifecycle`。
Source: inference
Testing: required

### SPEC-03：标记数量本身归零
Condition: 同 SPEC-02。
Expected: T 上 `waiting_forward_tlc_tasks` 不保留已离开通道的 TLC。
Observable: 仅节点内部状态；RPC 不暴露。debug 日志 `schedule_next_retry_task ... waiting_forward: N` 会打印数量，但只在调度重试时出现。
Basis: [PR 说明](https://github.com/nervosnetwork/fiber/pull/1705)。
Source: explicit
Testing: not_tested — RPC 不暴露；是否接受 debug 日志作为判据待确认，上游 Rust 用例已直接断言。

## 测试树

<!-- TEST-TREE-BEGIN -->
- trampoline 转发标记
  - 转发 fulfill 与转发节点自有发票
    - PR1705-01 [primary] -> SPEC-01：T 自有同 hash 发票保持 Open；直接付款对照变 Paid
  - 成功 / 失败转发后的通道状态
    - PR1705-02 [primary] -> SPEC-02：pending_tlcs 清空、余额守恒、T 重启后继续可用
  - [not_applicable] 标记数量直接断言 — SPEC-03；RPC 不暴露，上游已覆盖；日志判据待确认
  - [unanalysed] 从旧版本（带泄漏标记）升级到新版本后的清理 — 需要先用修复前构建制造泄漏再换二进制；可按 migration 目录的升级模式扩展
<!-- TEST-TREE-END -->

## 用例

共同前提：stock `CURRENT_DEV`（v0.10.0-rc2）节点 A、T、C、B；A–T、T–C 为公开通道，双方都有足够余额；B 不建通道；等到 A 的图里有 T 且 T 支持 trampoline。付款显式传 `trampoline_hops=[T]`，发票 `allow_trampoline_routing=true`，原像由测试自己生成。

<!-- TEST-CASES-BEGIN -->
| 用例 | 场景 | 预期结果 | 防止的问题 | 优先级 |
| --- | --- | --- | --- | --- |
| `PR1705-01` | - [ ] C 用自选原像的 hash 建持单发票，A 经 T 付款并等到 C 发票 `Received`；T 再用同一 `payment_hash` 建自己的持单发票；C `settle_invoice` 后等 A 付款 `Success`；最后 A 直接付 T 新建的普通发票 | C 发票 `Paid`、A 第一笔 `Success`；T 同 hash 发票仍为 `Open`；A 直接付 T 的那笔 `Success` 且 T 该发票 `Paid` | 清标记后误把转发 TLC 当成本地终点，用别人的原像结算转发节点自己的发票 | P0 |
| `PR1705-02` | - [ ] A 经 T 连续付 C 3 笔（成功）、付 B 3 笔（失败），全部到终态后等待 T 两条通道 TLC 清空；然后重启 T 并重连 A、C，再经 T 付 C 一笔 | 6 笔付款依次为 3 `Success`、3 `Failed`；T 两条通道 `pending_tlcs` 为空；A–T 余额只按成功付款的金额加手续费变化，T–C 只按成功金额变化；T 重启后通道 `ChannelReady`，最后一笔 `Success` | 失败 TLC 被重复处理或标记残留，导致 TLC 不清、余额错乱或重启后通道不可用 | P1 |
<!-- TEST-CASES-END -->

## 验证设计

- 独立预期：发票状态和余额变化由测试自己选的金额、手续费上限和“成功 / 失败”分组决定；手续费以 A 的 `get_payment` 返回的 `fee` 为准，再核对 A–T 余额差等于金额加手续费。
- 实际入口与观察：真实节点 RPC `new_invoice → send_payment(trampoline_hops) → settle_invoice`，观察 `get_invoice`、`get_payment`、`list_channels`；重启用框架的 `stop` / `start`。
- 缺陷敏感性：`PR1705-01` 防的是修复引入的回归，修复前构建也应通过；`PR1705-02` 修复前大概率也通过（泄漏本身不可见），二者都不作修复前负对照。真正的泄漏只能由上游 Rust 用例证明。
- 证明边界：不证明内部标记数量为 0；不覆盖从旧版本升级时的清理。
