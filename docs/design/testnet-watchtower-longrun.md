# 设计：测试网长期 Watchtower 链上取回

状态：草案，待 review（用例见 `reviews/testnet/watchtower-longrun.md`）。评审确认前不写自动化代码。

## 1. 关键约束（来自 fiber 源码 develop）
- release 构建：`MILLI_SECONDS_PER_EPOCH = 4h`，`DEFAULT_COMMITMENT_DELAY_EPOCHS = 1`，`MIN_TLC_EXPIRY_DELTA = 2/3 epoch ≈ 160 min`；默认 `tlc_expiry_delta = 4h`，默认 `final_tlc_expiry_delta = 24h`，`MAX_PAYMENT_TLC_EXPIRY_LIMIT = 14d`。
- 5 节点链路，最终 TLC 过期时间 ≈ final_delta + 中间 3 跳 × tlc_expiry_delta。全部用最小值约 4 × 160 min ≈ 10.7 h；再加 commitment delay（约 1 epoch，4h）。**结论：当天（约 15–20h）能看到超时取回，但前提是自控节点把 `tlc_expiry_delta` 设为最小值，并在发支付时传 `final_tlc_expiry_delta` 最小值**；公共节点的 `tlc_expiry_delta` 不受我们控制，可能是默认 4h，会拉长。
- watchtower 检查间隔默认 60s（`fiber_watchtower_check_interval_seconds`）。

## 2. 强关哪个 channel（按公共节点位置）
只强关两个自控节点（C-C）之间的 channel。前提是链路中至少存在一个 C-C 相邻对：
- 方案 A（推荐）`C1-C2-P1-C3-P2` 或 `C1-C2-C3-P1-P2`：强关 C1-C2（付款端）或 C2-C3。被强关 channel 靠近付款端时，hold invoice 的 TLC 会经过公共节点，可以验证 WTL-05/06 下公共节点 channel 链下回滚。
- 方案 B `P1-C1-C2-C3-P2`：公共节点在两端，付款/收款方是公共节点，我们无法在公共节点上创建 hold invoice 或发起支付，**不可行**，除非公共节点只做中间跳。
- 付款端（N1）与收款端（N5）必须是自控节点（要调 `send_payment` 和 hold invoice/`settle_invoice`），因此可行拓扑为 `C - x - x - x - C`，两个公共节点位于 N2–N4 中的两个，剩下一个自控节点必须和端点相邻才有 C-C channel：`C-C-P-P-C`、`C-P-P-C-C`、`C-P-C-P-C`（**无 C-C 相邻对，不可行**）。推荐 `C1-C2-P1-P2-C3` 强关 C1-C2，或 `C1-P1-P2-C2-C3` 强关 C2-C3（收款端，preimage 取回发生在收款侧更直接）。
- 每日轮换：两个方向（付款侧/收款侧）交替，覆盖 preimage 在上游/下游的两种情形。强关后需要重新开该 channel（自控节点之间，可自动 open_channel），保证第二天可用。

## 3. 触发脚本（`test_cases/fiber/testnet/watchtower_longrun/trigger.py`，复用 `framework/fiber_rpc.py`）
1. 预检：5 个节点 RPC、`list_channels` 状态与余额、链路连通（`build_router`/dry-run）。失败即退出（WTL-09）。
2. 若上次强关的 C-C channel 已关闭，重新开通并等待 `ChannelReady`。
3. 发 TLC：N5 创建 k 个普通 invoice（N1 `send_payment`）+ m 个 hold invoice（只给 payment_hash，preimage 暂存）。普通支付在强关前完成；hold invoice 保持 pending。强关前 settle 其中一部分 hold invoice → 产生"下游有 preimage 但上游 TLC 尚未 remove"的窗口：需要在 settle 后立刻强关，存在时序竞争，必要时让上游节点暂时断开 peer（`disconnect_peer`）以冻结链下 remove。
4. `shutdown_channel({channel_id, force: true})`，记录 commitment tx。
5. 写场景记录，退出。

## 3.1 可配置的每日交易量（`config/watchtower_longrun.yaml`）
```yaml
scenarios_per_day: 2            # 每天构造几个强关场景，每个场景强关 1 个 C-C channel
run_times: ["02:00", "14:00"]   # 可选，同一天多场景的触发时刻（Asia/Shanghai）；为空则同一次 CI 内依次执行
scenario:
  normal_payments: {count: 3, amount_ckb: 1}     # send_payment 普通支付，强关前链下完成
  preimage_tlcs:   {count: 2, amount_ckb: 2}     # hold invoice，强关前 settle → 期望 preimage 链上取回
  timeout_tlcs:    {count: 2, amount_ckb: 2}     # hold invoice，永不 settle → 期望超时链上取回
  final_tlc_expiry_delta_ms: 9600000             # 160 min，最小值
force_close:
  candidates: [[N1, N2], [N4, N5]]  # 允许强关的 C-C channel（按拓扑填写）
  strategy: round_robin             # round_robin | fixed
  reopen_capacity_ckb: 1000         # 强关后重开 channel 的出资
deadline_hours: 30
limits: {max_tlcs_per_scenario: 50, max_scenarios_per_day: 4}
```
- `workflow_dispatch` 输入（全部可选，覆盖 yaml）：`scenarios_per_day`、`normal_count`、`preimage_count`、`timeout_count`、`amount_ckb`、`dry_run`（只做预检与容量计算，不发交易）。定时触发只用 yaml。
- 映射规则：**一个场景 = 一次强关 = 一个 C-C channel**。同一天多个场景按 `candidates` 轮换；若某候选 channel 还没重开好（重开需等 funding 上链确认，通常数分钟），则下一个场景使用另一个候选，或先 `open_channel` 一条新的 C-C 平行 channel（`reopen_capacity_ckb`）。可用 C-C channel 数不足时按 WTL-11 拒绝。
- 容量 / CKB 估算（预检时计算并写入记录）：每场景被强关 channel 需容纳 `pending = preimage_count×amount + timeout_count×amount`，同时整条路径上每个 channel（含公共节点 channel）的付款方向余额 ≥ 该场景全部 TLC 总额 + 手续费；pending TLC 在 fnn 中受每 channel TLC 数量上限（`max_tlc_number_in_flight`）与 `max_tlc_value_in_flight` 限制，`count` 需小于此值。每次强关消耗：commitment + 每个 TLC 一笔取回交易的手续费 + 每个 TLC output 的 cell 占用（取回后释放）+ 重开 channel 的出资（约 `reopen_capacity_ckb`，会在下次强关后回到钱包）。经过公共节点的 timeout TLC 会把这部分资金在公共节点 channel 上锁到 TLC 解决为止，建议 timeout 总额远小于公共节点 channel 容量。

## 4. 场景记录（JSON，`$DATA_DIR/scenarios/<date>-<id>.json`）
```json
{"id":"2026-10-29-01","created_at":"...","topology":[{"name":"N1","pubkey":"...","controlled":true}],
 "channels":[{"channel_id":"0x..","outpoint":"..","nodes":["N1","N2"],"public_node":false,"force_closed":true,"balance_before":{}}],
 "force_close":{"channel_id":"0x..","by":"N1","tx_hash":"0x..","at":"..."},
 "tlcs":[{"payment_hash":"0x..","amount":"0x..","kind":"hold|normal","preimage":"0x..|null","settled_before_close":true,
          "expiry_ms":1730000000000,"expected":"preimage|timeout|offchain","channel_id":"0x.."}],
 "deadline":"..."}
```

## 5. 监控状态机（每个场景）
`TRIGGERED → COMMITMENT_ONCHAIN → (每个 TLC) WAIT_PREIMAGE_CLAIM | WAIT_EXPIRY → TIMEOUT_CLAIMED | PREIMAGE_CLAIMED → SETTLED_MAIN_BALANCE → PASSED`；任一时刻超过 deadline → `FAILED`；公共节点 channel 状态异常 → 立即 `FAILED(WTL-06)`。
观察方式：CKB indexer `get_transactions` 跟踪 funding/commitment 输出的花费链；fnn `list_channels`（含 closed）、`get_payment` 状态；状态保存到 SQLite，重启可恢复（WTL-10）。

## 6. 网页 & Discord
- 单进程（FastAPI 或 Python 标准库 http.server + Jinja）只读页面：总览（每日场景、状态色块）、场景详情（每个 TLC 的预期/实际取回方式、testnet explorer 链接 `https://testnet.explorer.nervos.org/transaction/<hash>`、时间线）、节点状态（在线、高度、channel 余额）。只监听本机/内网，是否需要对外暴露待定。
- Discord：webhook 每日一次摘要（成功/失败/进行中数量 + 网页链接），失败立即推送。webhook URL 存在服务器环境变量中，不进仓库。

## 7. CI
`.github/workflows/testnet-watchtower-longrun.yml`：`schedule`（每日一次）+ `workflow_dispatch`；`runs-on: [self-hosted, fiber-testnet]`；只跑触发脚本并上传场景记录为 artifact，同时写入服务器 `$DATA_DIR`。监控以 systemd 服务常驻，不在 CI 中。

## 8. 需要用户提供
1. 5 个节点的链路顺序、哪两个是公共节点、各节点 RPC 地址（自控节点）和公共节点 pubkey/地址。
2. 自控节点配置：`tlc_expiry_delta` 设为最小值、watchtower 已开启、check interval；节点钱包有足够测试网 CKB（每日开新 channel + 手续费）。
3. 在节点机上注册 self-hosted runner（标签建议 `fiber-testnet`）。
4. Discord webhook URL；网页是否需要公网访问。
5. 默认配置值（每天场景数、每场景各类 TLC 数量与金额）和失败判定的 deadline；可在 yaml 或手动运行时调整。

## 9. 风险
- 公共节点的 `tlc_expiry_delta` 可能是默认 4h，超时类 TLC 可能要跨天；另外公共节点会因 TLC 过期而**自己**强关和我们之间的 channel（上游 TLC 过期未 remove 时 fnn 会强关），这恰恰是 WTL-06 要防的问题，hold invoice 必须保证在上游过期前于链下结算/失败。
- "下游已有 preimage、上游未 remove" 的窗口依赖时序，可能需要断开 peer。
- 每日强关会消耗测试网 CKB，需重开 channel。
- 本草案尚未在本地 devnet 跑通完整 5 节点流程；现有 devnet 用例（`devnet/watch_tower_wit_tlc/`）已覆盖 2 节点 preimage/超时取回，可作为下一步原型参考。
