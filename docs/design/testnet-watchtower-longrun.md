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
5. 每日 TLC 数量和金额、失败判定的 deadline。

## 9. 风险
- 公共节点的 `tlc_expiry_delta` 可能是默认 4h，超时类 TLC 可能要跨天；另外公共节点会因 TLC 过期而**自己**强关和我们之间的 channel（上游 TLC 过期未 remove 时 fnn 会强关），这恰恰是 WTL-06 要防的问题，hold invoice 必须保证在上游过期前于链下结算/失败。
- "下游已有 preimage、上游未 remove" 的窗口依赖时序，可能需要断开 peer。
- 每日强关会消耗测试网 CKB，需重开 channel。
- 本草案尚未在本地 devnet 跑通完整 5 节点流程；现有 devnet 用例（`devnet/watch_tower_wit_tlc/`）已覆盖 2 节点 preimage/超时取回，可作为下一步原型参考。
