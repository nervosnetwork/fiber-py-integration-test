# PR #1707：funding 与 watchtower 不再互抢 cell 用例评审

评审范围：watchtower 用独立的 `DefaultCellCollector` 给 revocation/settlement 交易选手续费 cell，看不到 funding 流程已预留的 cell（`LiveCellsExclusionMap` 在 `CkbChainActor` 内）；funding 也看不到 watchtower 已入池交易花费的 cell（indexer 要等交易所在块上链才把 cell 标记为已花）。两边可能选中同一个 cell。修复后引入进程级 `held_cells` 注册表：funding 每次变更预留都发布，watchtower 发出的每笔 revocation/settlement 输入持有 30 分钟，双方选币前都先锁定这些 cell。

源码版本：[PR #1707](https://github.com/nervosnetwork/fiber/pull/1707)；diff 取自 2026-11-11 GitHub API 快照（`gh pr diff 1707`）。测试仓库分支 `sunchengzhu/v0.10.0-rc2-regression`；初次评审阶段未修改测试。

## 导读

- **这个改动要做什么**：修一个「两只手从同一个钱包里抓同一枚硬币」的问题。节点一边在为新通道组装 funding 交易，另一边 watchtower 在为被攻击的通道组装维权交易，两边各自挑手续费 cell 时互相看不见对方刚挑走的——挑重了的后果：真实事故（testnet LSP，2026-10-28）里，维权交易上链后 funding 交易的输入变成死 cell，funding 永久卡住（`Resolve failed Unknown(OutPoint)`），通道永远开不起来。
- **行为变化**：改动前 → watchtower 交易在池中（未上链）时发起 funding，funding 可能选中同一 cell，之后 funding 卡死；改动后 → funding 选币时避开 watchtower 持有的 cell，两笔交易输入无交集，都能正常上链。
- **最怕出什么问题**：channel 开在半空——用户发起开通道，交易进了池却永远确认不了，资金被锁，且没有明确报错。
- **能测到什么**：完整的端到端事故复现。攻击用公开运维手段制造（回滚 fiber1 数据目录 + force close → 广播旧承诺，仿 `test_revert_tx.py`）；池内窗口用手动挖矿控制（不挖就一直有效），无时序竞争；cell 冲突直接对比两笔交易的输入 outpoint，是确定性断言。
- **测不到的**：反方向时序（funding 在池、watchtower 后选币）——watchtower 只在维权承诺**上链后**才动作，而挖出该承诺的同一块会顺带确认池中的 funding，窗口被挖矿行为本身关闭，公开操作构造不出来（见测试树说明）。

依据：[PR #1707 描述与 diff](https://github.com/nervosnetwork/fiber/pull/1707)（含 testnet 真实事故描述）；旧承诺攻击构造仿 `test_cases/fiber/devnet/watch_tower/test_revert_tx.py`；挖矿控制用框架既有 `Miner`。

## 需要你决定

- 无（事故场景与预期都来自真实线上事故与 PR 描述）。

## 用例

公共约定：devnet；fiber1 ↔ fiber2 开通道（双方各 1000 CKB）；fiber2 使用 `fiber_watchtower_check_interval_seconds: 5`（仿现有 watchtower 套件）。「旧承诺攻击」：备份 fiber1 数据目录 → fiber1 向 fiber2 付款成功 → 回滚 fiber1 数据 → fiber1 force close（广播旧承诺）→ 挖出该承诺 → fiber2 的 watchtower 发出 revocation tx 入池。「不挖」指不调用任何挖矿方法，交易池状态由 CKB RPC 查询确认。

<!-- TEST-CASES-BEGIN -->
| 用例 | 场景 | 预期结果 | 防止的问题 | 优先级 |
| --- | --- | --- | --- | --- |
| `PR1707-01` | - [x] 旧承诺攻击使 fiber2 的 watchtower 发出 revocation tx 并确认其入池；**不挖**，随后 fiber2 从同一账户向 fiber3 发起 `open_channel`；最后挖出全部交易 | revocation tx 与 funding tx 的输入 cell 无交集；两笔交易都上链；fiber2↔fiber3 通道进入 `ChannelReady`；fiber2 对 fiber1 的维权资金到账 | funding 选中 watchtower 已花费的 cell，维权交易上链后 funding 变死交易、通道永久 Pending、资金被锁 | P0 |
<!-- TEST-CASES-END -->

## 测试树

<!-- TEST-TREE-BEGIN -->
- watchtower 交易在池时，funding 从同一账户选币
  - 旧承诺攻击 → revocation tx 入池 → 同账户 open_channel → 挖矿
    - PR1707-01 [primary] -> SPEC-01：输入无交集、双双上链、通道 Ready
  - funding 在池时 watchtower 后选币（反方向） [not_applicable] — watchtower 只在承诺上链后动作，挖出承诺的同一块会确认池中 funding，窗口被挖矿关闭，公开操作无法构造
- 双方账户不同（无共享 cell） [not_applicable] — 无交集是平凡结果，无区分度
<!-- TEST-TREE-END -->

## Spec

### SPEC-01：funding 避开 watchtower 持有的 cell
- Condition: 节点账户的一笔 watchtower 交易（revocation/settlement）已广播但未上链；同一账户此时发起 open_channel。
- Expected: funding 交易不选用 watchtower 交易已花费的输入 cell；两笔交易都能上链；新通道正常进入 Ready；维权流程不受影响。
- Observable: 两笔交易的输入 outpoint 无交集（CKB RPC `get_transaction`）；两笔交易均 committed；`list_channels` 显示新通道 `ChannelReady`。
- Basis: [PR #1707 描述与 diff](https://github.com/nervosnetwork/fiber/pull/1707)（事故现象与修复方案）；线上事故：funding 在 settlement 上链后 `Resolve failed Unknown(OutPoint)`。
- Source: explicit
- Testing: required

## 验证设计

- 独立预期：「两笔交易不应共享输入」「funding 应能确认」来自交易有效性与开通道语义本身，不来自被测实现。
- 实际入口与观察：公开 RPC（`open_channel`、`shutdown_channel`、`send_payment`）、运维操作（数据目录备份/回滚、进程启停）、CKB RPC（交易池与交易查询）、框架手动挖矿。攻击不依赖任何内部钩子。
- 证明边界：真实构建的 devnet 节点。反例（旧实现）：funding 与 revocation tx 共享输入，维权交易上链后 funding 永久无法确认、通道停在 Pending——输入交集断言与 `ChannelReady` 等待超时都会拒绝旧实现。反向验证已完成（2026-11-11）：rc1（2026-09-25，不含 #1707）上用例如期失败——funding 与 revocation 抢同一 cell，funding 被交易池拒绝，`wait_tx_pool(2)` 超时；rc2 通过。另：devnet 有常驻自动矿工，池内窗口须先 `stop_miner()` 保持。
- 窗口确定性：手动挖矿保证 revocation tx 在 funding 组装期间一直在池中，无竞态。
