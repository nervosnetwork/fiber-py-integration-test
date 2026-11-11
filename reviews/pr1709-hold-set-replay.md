# PR #1709：hold-set 结算重放时队列中的 fulfill 不再阻塞用例评审

评审范围：MPP hold 发票结算中，当某个 TLC 的 fulfill 已排队（对端断连/等待 ack）时，收款方重放 `SettleReceivedHoldTlcSet` 必须仍能重建结算上下文并完成任务，不能丢上下文导致 hold TLC 卡死。单一部分（非 MPP）的 hold 结算重试已由 `PR-1289` 系列用例覆盖；排队 fail 压制本地原像的分支由 `PR1672-03` 覆盖，均不重复。

源码版本：[PR #1709](https://github.com/nervosnetwork/fiber/pull/1709)；diff 取自 2026-11-10 GitHub API 快照（`gh pr diff 1709`）。测试仓库分支 `sunchengzhu/pr1708-funding-pool-conflict`；初次评审阶段未修改测试。

## 导读

- **这个改动要做什么**：修复一个 MPP hold 付款的结算卡死问题。场景是：买家分多路（多条通道）付一张 hold 发票，卖家结算时买家恰好不在线，fulfill 消息排队等对端确认；这时如果卖家节点重启，恢复后要「重放」这次结算。旧版重放时会把正在排队的 TLC 误认为「已处理」而跳过，导致结算上下文丢失、TLC 永远卡在通道里。修复后排队的 fulfill 被视为「同一次结算的重放」，正常完成。
- **行为变化**：改动前 → 上述场景下卖家重启后，发票和部分 TLC 永远卡住，付款方钱被锁；改动后 → 重放正常完成，发票变 Paid，付款方收到 Success，双方无残留 TLC。
- **最怕出什么问题**：修过头 —— 把「排队的失败」也放行了：下游已经明确失败的转发，不应被本地原像改写为成功（这一半行为由既有用例 PR1672-03 守护）。
- **能测到什么**：用公开 RPC 可完整构造：MPP hold 发票 + 双通道付款 + 对端停机/断连 + 收款方 `settle_invoice` + 收款方重启触发重放 + 恢复连接。观察付款状态、发票状态、双方 pending TLC 数量。
- **测不到的**：内部谓词 `can_auto_fulfill_received_tlc` 的真值表本身（属单元测试，PR 已自带）；我们只看端到端资金结果。

依据：[PR #1709 描述与 diff](https://github.com/nervosnetwork/fiber/pull/1709)；内部触发路径（`SettleReceivedHoldTlcSet` 重放经 `can_auto_fulfill_received_tlc` 重建上下文）来自 PR 描述，未逐行核对固定 head 源码。

## 已决定

- `PR1709-01/02` 时序屏障（2026-11-10 确认）：结算前**必须**先等 fiber2 发票进入 `Received`（两部分 TLC 均到达的官方信号），再停/断 fiber1、再 settle、再重启 fiber2。不用固定 sleep 赌时序，保证每次运行精确复现「钱齐 → 结算时对端离线 → 收款方重启」的事故链。
- 收款方用 SIGKILL 崩溃而非优雅停止（2026-11-10 实测修正）：重放（`retry_hold_tlc_sets`）只在启动时 hold 存储里仍有记录时才触发；优雅停止前 settle 的异步交接已完成、hold 记录已清空，重放根本不会执行（日志证实重启后只有重试队列恢复，无重放）。`settle_invoice` RPC 在写入原像后立即返回、结算走异步 actor 交接，此刻 SIGKILL 可真实落在「durable 队列已写、hold 记录未删」的崩溃窗口——日志证实重启后 replay 为未完成交接的 TLC 重建了 fulfill。SIGKILL 落在窗口外时各版本行为一致，不会在正确实现上误报。
- 反向验证基线（2026-11-10 查实）：bug 由 #1672 引入（2026-10-01 合入），而 rc1 二进制是 647a720（2026-09-25，`compare` 确认不含 #1672），**rc1 不是有效反向基线**；本地无「含 #1672 但不含 #1709」的 buggy 二进制（构建需 Rust 工具链与上游源码，本机不具备）。反向验证以日志证据替代：SIGKILL 变体在 rc2 上证实重启重放真实执行且结果正确。

## 用例

公共约定：devnet；fiber1（付款方）与 fiber2（收款方）之间开**两条**通道；fiber2 创建 `allow_mpp` 的 hold 发票（自带 payment_hash），金额超过单通道余额以强制分两部分；fiber1 付款后等待 fiber2 发票 `Received`（两部分 TLC 均已到达）。「收款方重启」指 stop + start 触发启动时的结算重放。终态判定：fiber1 付款 `Success`、fiber2 发票 `Paid`、双方 pending TLC 归零（`wait_fibers_pending_tlc_eq0`）。

<!-- TEST-CASES-BEGIN -->
| 用例 | 场景 | 预期结果 | 防止的问题 | 优先级 |
| --- | --- | --- | --- | --- |
| `PR1709-01` | - [x] MPP hold 发票的两部分 TLC 均已到达 fiber2（发票 Received）；停掉 fiber1 进程后 fiber2 执行 `settle_invoice`（fulfill 开始排队），**立即 SIGKILL fiber2 模拟崩溃**（打断 durable 队列与 hold 存储的交接），重启 fiber2 触发启动时的结算重放，最后重启 fiber1 并重连 | fiber1 付款 `Success`；fiber2 发票 `Paid`；双方 pending TLC 归零，无卡死 | 收款方崩溃重启后结算重放丢上下文，hold TLC 永远卡住、资金被锁 | P0 |
| `PR1709-02` | - [x] 同 PR1709-01，但对端离线方式改为 RPC `disconnect_peer`（进程不退出），SIGKILL 并重启 fiber2 后重连恢复 | 同 PR1709-01：付款 `Success`、发票 `Paid`、双方 pending TLC 归零 | 仅进程停止路径修复而协议层断连路径仍卡死 | P1 |
<!-- TEST-CASES-END -->

## 测试树

<!-- TEST-TREE-BEGIN -->
- MPP hold 发票结算，fulfill 因对端离线排队
  - 对端进程停止后 settle，收款方重启重放
    - PR1709-01 [primary] -> SPEC-01：重放完成，付款成功、发票 Paid、无 TLC 残留
  - 对端 RPC 断连后 settle，收款方重启重放
    - PR1709-02 [primary] -> SPEC-01：同上，断连方式为正交变体（review-feedback：断连须覆盖重启与 RPC 断开两种）
  - 对端在线时 settle（无排队） [not_applicable] — 正常路径已由 settle_invoice/test_mpp.py 等既有用例覆盖
- 排队的 fail 压制本地原像（本 PR 同一谓词的另一半） [not_applicable] — 已由 reviews/pr1672-forwarded-local-invoice.md 的用例 3 守护，不重复实现
<!-- TEST-TREE-END -->

## Spec

### SPEC-01：排队的 fulfill 不阻塞结算重放
- Condition: MPP hold 发票的全部 TLC 部分已到达收款方（发票 Received）；收款方结算时付款方离线，fulfill 进入重试队列；收款方随后重启，启动时重放结算命令。
- Expected: 重放把排队的 fulfill 视为同一次结算的继续而非「已处理」，重建全部 TLC 上下文并完成结算；对端恢复后 remove 被确认，资金正常转移。
- Observable: 付款方 `get_payment` 为 `Success`；收款方 `get_invoice` 为 `Paid`；双方 pending TLC 归零；通道保持 Ready。
- Basis: [PR #1709 描述与 diff](https://github.com/nervosnetwork/fiber/pull/1709)（排队的 fulfill 不再使 `can_auto_fulfill_received_tlc` 返回 false）。
- Source: explicit
- Testing: required

## 验证设计

- 独立预期：「重放应完成、资金不卡死」来自 PR 描述与用户可报告现象（发票 Paid、付款 Success），不来自被测实现；两条用例共用同一 oracle（付款状态 + 发票状态 + pending TLC 归零）。
- 实际入口与观察：公开 RPC（`new_invoice`、`send_payment`、`settle_invoice`、`disconnect_peer`、`get_payment`、`get_invoice`）与运维操作（进程停止/启动）；前置屏障为发票 `Received` 状态，终态用框架既有等待方法，不用固定 sleep 判断成功。
- 证明边界：真实构建的 devnet 节点；重放由真实重启触发，非内部钩子。反例（旧实现）应在收款方重启后 TLC 持续在途、发票不到 Paid，被等待超时拒绝。
