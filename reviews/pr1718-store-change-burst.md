# PR #1718：store 突发变更时订阅不再中断用例评审

评审范围：store 的变更通知通道在突发（>16 条连续变更，转发任务来不及处理）时，旧版订阅方收到 `Lagged` 后**永久断订**——RPC WebSocket 订阅方（`subscribe_store_changes`）和进程内 CCH actor 都从此收不到任何 store 变更。修复后 store 自己的端口按序直投各订阅者信箱，突发多少条都不丢、不断。

源码版本：[PR #1718](https://github.com/nervosnetwork/fiber/pull/1718)；diff 取自 2026-11-11 GitHub API 快照（`gh pr diff 1718`）。测试仓库分支 `sunchengzhu/v0.10.0-rc2-regression`；初次评审阶段未修改测试。

## 导读

- **这个改动要做什么**：修一个「订阅被突发流量打死」的问题。store 每发生一次变更（开发票、付款状态推进、通道事件等）都会通知订阅者。旧版通知走一条容量 16 的广播通道：如果一瞬间来 17 条以上变更、转发任务还没来得及送，订阅方直接被判「掉队」并永久断开——之后任何变更都收不到，且没有报错提示。修复后改成 store 按序直投每个订阅者的信箱，没有中间缓冲上限。
- **行为变化**：改动前 → 一阵密集操作后，WebSocket 订阅静默失效，客户端（以及独立部署的 CCH 服务）永远不再收到通知；改动后 → 突发期间和之后的每条通知都按序送达。
- **最怕出什么问题**：通知丢失或乱序没有被发现——客户端以为自己「在线」却漏掉了关键状态变更（对 CCH 服务而言是丢链上事件）。
- **能测到什么**：fnn 的 RPC 端口同时服务 WebSocket，订阅 `subscribe_store_changes` 后用16 线程并发 `new_invoice` 制造 160 条突发变更，观察通知是否全部按序到达、订阅是否存活。这就是旧版必死的场景（上游测试：经旧通道 101 条变更只能收到 0 条）。
- **测不到的**：进程内 CCH actor 的订阅路径（同一根因、同一修复，上游 actor 测试已覆盖）；独立部署 CCH 服务的端到端链路（需要 BTC/LND 环境，根因与 RPC 订阅相同，不重复）。

依据：[PR #1718 描述与 diff](https://github.com/nervosnetwork/fiber/pull/1718)（含上游单元测试断言：旧通道 101 条变更收到 0 条，新端口全收）；未逐行核对固定 head 源码。

## 已决定

- 反向验证结论（2026-11-11 实测）：rc1 确含 buggy 代码（`subscribe_to_port` + 16 容量广播，见 `/tmp` 源码比对），但黑盒**无法稳定复现** Lagged 杀订阅——该竞争要求 17 条变更在转发任务两次调度之间完成，而公开 RPC 驱动的变更间隔受 HTTP/落盘延迟限制（毫秒级），转发只需微秒。rc1 实测：30 顺序、8 线程 80、16 线程 320 张发票突发后订阅均存活。因此两条用例定位为**契约守护**（订阅在高负载下持续有效、订阅者互不影响），区分 buggy 版本依赖上游单元测试（旧通道 101 条收 0 条）；若在慢速/高负载 CI 机器上竞争被触发，用例同样能抓住回归。

## 用例

公共约定：devnet；fiber1 单节点即可（store 变更本地产生）。「突发」指订阅建立后用 pytest 线程内的紧凑循环连续调用 30 次 `new_invoice`（每张发票产生至少 1 条 store 变更，超过旧版 16 的缓冲上限）；随后再创建 1 张「标记发票」。通知到达以 WebSocket 收到 `subscription` 消息计数，等待使用有上限的轮询。

<!-- TEST-CASES-BEGIN -->
| 用例 | 场景 | 预期结果 | 防止的问题 | 优先级 |
| --- | --- | --- | --- | --- |
| `PR1718-01` | - [x] 对 fiber1 建立 `subscribe_store_changes` WebSocket 订阅后，用 16 个并发线程突发创建 160 张发票，再创建 1 张标记发票 | 收到至少 31 条通知（30 张发票 + 标记），且最后一条标记发票的通知到达——证明突发后订阅仍存活 | 突发变更导致订阅静默永久失效，客户端漏收状态变更 | P0 |
| `PR1718-02` | - [x] 对 fiber1 建立两个并发订阅 A、B，突发期间关闭 A，B 保持 | A 关闭后 B 仍收到后续全部通知（含标记发票），订阅者互不影响 | 单个订阅者退出误伤其他订阅者；或停止的订阅者未被移除导致泄漏 | P1 |
<!-- TEST-CASES-END -->

## 测试树

<!-- TEST-TREE-BEGIN -->
- subscribe_store_changes 订阅遭遇 store 突发变更
  - 单订阅 + 30 条突发 + 事后标记变更
    - PR1718-01 [primary] -> SPEC-01：通知全到且突发后订阅存活
  - 双订阅，其一中途关闭
    - PR1718-02 [primary] -> SPEC-02：存活订阅者不受影响
  - 变更量低于突发阈值（≤16 条） [not_applicable] — 新旧版本行为一致，无区分度
- 进程内 CCH actor 的订阅路径 [not_applicable] — 同一根因与同一修复，由上游 actor 测试覆盖（101 条全收），黑盒不可直接观察
<!-- TEST-TREE-END -->

## Spec

### SPEC-01：突发后订阅持续有效且通知不丢
- Condition: 客户端通过 WebSocket 订阅 `subscribe_store_changes`；store 在短时间内产生超过旧广播通道容量（16）的连续变更。
- Expected: 每条变更都产生一条通知并按序送达；突发结束后新变更的通知仍然到达；连接不报错、不静默失效。
- Observable: WebSocket 收到的 subscription 通知计数 ≥ 突发变更数；事后标记发票的通知可收到。
- Basis: [PR #1718 描述与 diff](https://github.com/nervosnetwork/fiber/pull/1718)（旧版 17 连发即永久断订；新版 101 条全收）。
- Source: explicit
- Testing: required

### SPEC-02：订阅者互不影响
- Condition: 同一节点上存在多个并发订阅；其中一个在突发期间关闭。
- Expected: 其余订阅者继续收到全部后续通知；关闭的订阅者被移除，不影响通知投递。
- Observable: 存活订阅的通知计数完整（含事后标记变更）。
- Basis: [PR #1718 描述与 diff](https://github.com/nervosnetwork/fiber/pull/1718)（`a_stopped_subscriber_is_removed`：停止的订阅者被移除）。
- Source: explicit
- Testing: required

## 验证设计

- 独立预期：「订阅不应因突发失效」来自 RPC 订阅语义本身（订阅即持续接收），不来自被测实现；旧版必然失败的事实由上游测试给出（101 条收 0 条）。
- 实际入口与观察：公开 WebSocket RPC（`subscribe_store_changes` / `unsubscribe_store_changes`）与公开 RPC（`new_invoice`）；用 `websocket-client` 包直连 fnn RPC 端口，不依赖框架外的内部钩子。
- 证明边界：真实构建的 devnet 节点。反例（旧实现）在 30 条突发后订阅死亡，标记发票通知永远收不到，被等待超时拒绝。突发量 160（16 线程并发）约为旧缓冲上限 16 的十倍，无需精确控制消息时序。
- 无 CCH 依赖：本评审不引入 BTC/LND 环境；进程内 CCH 订阅路径已由上游测试覆盖。
