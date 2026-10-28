# 测试网长期 Watchtower 链上取回（5 跳多 TLC）

关联：nervosnetwork/acceptance-internal#1665

拓扑：`N1 - N2 - N3 - N4 - N5` 共 5 个 FNN 测试网节点、4 个 channel（"5 跳" 指 5 个节点的链路），3 个自控节点（C）+ 2 个公共节点（P），位置待定。Watchtower 为 fnn 内置，节点常驻即可。
触发（每日 CI）：沿整条链路发多笔 TLC：`send_payment` 普通支付 + hold invoice（不 settle 或延后 settle），随后对**两个自控节点之间**的一个 channel 执行 `shutdown_channel(force=true)`，输出场景记录。
监控（常驻进程）：读取场景记录，轮询 `list_channels` / CKB RPC，跟踪 commitment 上链、TLC 链上取回（preimage / 超时）、其他 channel 链下结算、公共节点 channel 状态。

| 用例 | 场景 | 预期结果 | 防止的问题 | 优先级 |
| --- | --- | --- | --- | --- |
| `WTL-01` | - [ ] 每日触发：按配置（`scenarios_per_day`、每场景 normal / preimage / timeout TLC 数量与金额）在 5 节点链路上构造场景，每个场景确认 TLC 在被强关 channel 上处于 pending 后，按配置 force shutdown 一组自控 channel（1 个或多个，含 C-C 平行 channel） | 每个场景中配置的每个 channel 强关请求成功，各自的 commitment 交易在测试网上链，实际生成的各类 TLC 数量与配置一致；场景记录写入 channel、TLC（payment_hash/金额/方向/expiry）、preimage、强关时间与交易哈希 | 触发脚本不能稳定构造出带多 TLC 的强关场景，后续验证无从开始 | P0 |
| `WTL-02` | - [ ] 强关 channel 上，下游已拿到 preimage（hold invoice 被 settle）的 TLC | 持有 preimage 的一方由 watchtower 在 TLC 过期前通过 preimage 链上取回，金额与 TLC 金额一致（扣除手续费） | 节点离线/不操作时 watchtower 不用 preimage 取回，导致资金被对方超时拿走 | P0 |
| `WTL-03` | - [ ] 强关 channel 上，hold invoice 始终不 settle 的 TLC，等到 TLC expiry 之后 | 发出 TLC 的一方由 watchtower 链上超时取回，金额一致；对方无法用 preimage 取走 | 超时 TLC 资金永久锁在链上或被错误一方取走 | P0 |
| `WTL-04` | - [ ] 强关后，commitment 中非 TLC 部分（to_local / to_remote）在 commitment delay 后 | 双方余额最终在链上取回，和强关前 `list_channels` 余额（扣除 pending TLC 与手续费）一致 | 主余额在强关后无法取回 | P0 |
| `WTL-05` | - [ ] 强关 channel 的上下游其他 channel（未强关）上对应的同一笔支付 | 上游 channel 的 TLC 依据下游链上结果在链下 remove（preimage 结算或失败回滚），channel 保持 `ChannelReady`，不被连带强关 | 一个 channel 链上取回连带导致相邻 channel 强关或 TLC 卡住 | P0 |
| `WTL-06` | - [ ] 整个场景周期内（触发到全部取回完成）持续检查公共节点参与的所有 channel，包括公共节点两侧相邻 channel 同时被强关上链的场景 | 公共节点的 channel 状态始终不是强关/关闭，无属于这些 channel 的 commitment 上链；公共节点 channel 上的 TLC 在其过期前于链下 remove（结算或失败） | watchtower 或 TLC 超时处理误触发公共节点 channel 强制关闭，影响公共网络 | P0 |
| `WTL-07` | - [ ] 强关后场景完成，在剩余 channel 上再次发送 send_payment（不经过已关 channel 的路径或新开 channel 后） | 支付成功，链下结算正常 | 链上取回后节点状态异常，后续链下支付不可用 | P1 |
| `WTL-08` | - [ ] 场景从强关起超过阈值（默认 最大 TLC expiry + 2×commitment delay + 缓冲）仍有未取回项 | 监控把场景判为失败，网页标红并推送 Discord，附未完成项 | 取回卡住却没人发现 | P1 |
| `WTL-09` | - [ ] 每日运行时任一节点 RPC 不可达或通道余额不足以构造场景 | 触发任务失败并给出明确原因，不执行强关，Discord 告警 | 环境异常时误强关或产生半截场景 | P1 |
| `WTL-11` | - [ ] 配置非法（数量为负、总金额超过可用 channel 容量、强关集合包含公共节点 channel、所需 C-C channel 数（`scenarios_per_day` × 每场景强关数）超过可用数） | 触发任务在发任何交易前失败并说明原因 | 错误配置导致半截场景或误强关 | P1 |
| `WTL-12` | - [ ] 同一场景同时强关链路两端的自控 channel（如 N1-N2 与 N4-N5），同一笔支付的 TLC 在两端都上链，其中部分 hold invoice 已 settle、部分不 settle | 已 settle 的 TLC 在收款侧由 watchtower 用 preimage 链上取回，付款侧对应 TLC 也用同一 preimage 链上取回；不 settle 的 TLC 在两端都超时取回；各端金额一致 | 多个 channel 同时上链时 preimage 未在上游链上使用，或两端取回冲突导致资金损失 | P0 |
| `WTL-13` | - [ ] 同一场景强关两个节点之间的多条平行 C-C channel，TLC 分布在不同平行 channel 上 | 每条平行 channel 的 commitment 与 TLC 各自正确取回，互不干扰，未强关的平行 channel 保持 `ChannelReady` | watchtower 按节点对而非 channel 处理导致取回错乱 | P1 |
| `WTL-10` | - [ ] 监控进程重启 | 从场景记录与链上状态恢复进度，不重复计数、不丢场景 | 常驻进程重启导致结果错误 | P2 |
