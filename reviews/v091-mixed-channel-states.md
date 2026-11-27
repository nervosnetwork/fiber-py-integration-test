# v0.9.1 混合旧通道与 v0.10.1 新通道

## 导读

在中心 A 同一原数据目录内连续留下 v0.9.1 七项并行状态及一条正常关闭历史，经过 v0.10.0 和正式 v0.10.1 后，再留下三条不同结果的 V2 通道：合作关闭、带持单 TLC 的强关承诺已确认、保持可付款。`CURRENT_DEV` 首次接管应因未结 V1 记录退出；在停机备份后，用公开运维命令 `drop-v1-channel` 显式归档诊断中仍阻断升级的原 V1 记录，再启动新版。新版必须从同一目录接手，用原像领到旧版已经锁在链上的那笔 TLC；另一条活动通道仍要能独立付款。空通道退回本金不是 TLC 结算。全过程是一条评审行、一个测试方法。

## 需要你决定

无。

## 已确认的设计边界

- `V091MIX-01`：v0.10.1 的 C 向 A 付 100 CKB 持单并强关；承诺确认后停 C、升级 A。只有新版 A 得到原像并领取，C 随后才恢复。
- 保留同一用例、三条独立的 v0.10.1 V2 通道：合作关闭、链上结算、保留付款。复用原强关目标，不加第四条。
- `V091MIX-01`：用户已确认只对首次 `CURRENT_DEV` 诊断中**仍阻断升级且属于原七条的 ID**执行 `drop-v1-channel`，不预设必须归档七次。该命令只归档本地 V1 活动／监控记录，**不关闭 funding 交易**；已上链资金可能仍被锁定或损失。本行不把 V1 资金取回列为成功结果。

## 用例

公共约定：A 是唯一需要**同时持有七项条件**的 v0.9.1 节点，B1～B7 为各条通道独立的正常 v0.9.1 对端；各通道为公开 CKB、独立 ID 和 funding。建图前通过正常钱包转账为 A 留至少两格独立已确认的可用 cell，避免两条待确认通道争用同一输入。①由 B1 先出资 200 CKB、A 再出资 400 CKB；②③由 A 先出资 200 CKB、B2/B3 再出资 400 CKB；④～⑦由 A 各出资 200 CKB、对端只出最小预留。付款哈希各不相同。先让第 3、4、5、6、7 条 funding 确认；第 3 条在 funding 入池但尚未确认时停 B3，再挖矿，验证 A 只有 OUR_CHANNEL_READY；第 4、5、6 条分别造持单；第 5 条由 B5 在线发起合作关闭，原持单使关通道等待；第 7 条先停 B7，再由 A 调用普通 shutdown 并核对拒绝。随后停矿，造第 2 条的 funding，在 B2 离线后清池；再对第 6 条强关，让原承诺在池中待确认。最后由 B1 发起双出资开通，等 A 处于 `AwaitingTxSignatures` 且 `OUR_TX_SIGNATURES_SENT`、`THEIR_TX_SIGNATURES_SENT` 均已出现，再停 B1；在 miner 仍停的条件下取样。此组合依据 v0.9.1 源码和后续构建的对称样本推断，尚待本用例验证，并非已有 v0.9.1 实测。第 2 条只要求最终取样窗口内 funding 未确认且清池后该交易缺席，不宣称永不重播。资金和交易证据由原 ID、funding outpoint、付款哈希逐条关联。各前置等待最多 120 秒；最终有界连续观察 30 秒，持单有效期及 funding 超时必须覆盖全部准备时间。总耗时待实测，准备预算暂按 10～20 分钟，不作为成功判据。

额外旧历史在七项构造前完成：A 与在线 B4 另开一条无 TLC 的公开 CKB 通道，由 A 正常合作关闭并等原 funding 的关闭交易确认；双方 `Closed` 标志须含 `COOPERATIVE`。保存旧 ID/outpoint，随后再开 A–B4 的第④条。七项取样时用 `include_closed=true` 同时确认旧关闭历史，不能混淆两个 A–B4 ID。

七项取样后只停 A，不切换 B1～B7；`V0100_DEV` 在原目录继续，逐条尝试强关，矿工保持停止，①②不主动提交或确认原 funding。随后 A 同库切到**正式 v0.10.1**；其 tag `d9b6bbd7` 早于 V2-only 迁移门禁 `703ec1cc`，与本机 `CURRENT_DEV` 不同。新增 C 使用正常 v0.10.1，新通道双方都声明 `CHANNEL_V2`，避免旧 B 对端特性协商改变新通道类型。合作关及三条新 funding 的确认需恢复出块，①②旧 funding 可能随之确认。A 停机后先用 `CURRENT_DEV` 真实启动并核对拒绝，再在停机状态备份原目录，使用同一个 `CURRENT_DEV` 二进制的 `drop-v1-channel --store-path <A>/fiber/store --channel-id <ID>` 对诊断中的原 V1 阻断 ID 逐条 dry-run、核对原 outpoint，然后归档；这会移除本地记录而非关闭链上资金。再由 `CURRENT_DEV` 从原目录启动。整个门禁阶段暂停出块，强关目标的旧承诺不变，既不重发强关也不重建通道。

三条 V2 均为公开 CKB 通道。合作关闭和保留付款两条各由 A 提供 200 CKB 可付余额；链上结算目标由 C 提供 200 CKB 可付余额。该金额不含预留：双方另付各自的通道预留，持单前双方本金（可付余额加预留）之和须等于原 funding 容量。为 C 的 funding、预留及后续链上费用备足独立可用 cell。测试先生成随机原像 P 和完整 H=SHA256(P)；A 只用 H 开持单发票，C 指定目标 funding outpoint 单跳向 A 付 M=100 CKB（10,000,000,000 Shannon）。在两端确认同一笔 Committed TLC 后，由旧版 C 强关。原像只在新 A 接手后交给它。发票有效期 6 小时、末跳到期差 9,600,000 毫秒；检查实际 TLC expiry 足以覆盖升级、领取，并按链时间确认未到期。通常每次 RPC 状态／承诺确认等待最多 120 秒；v0.10.1 的未广播端按固定的 300 秒周期扫描对端强关，停矿等 A 观察到原强关的独立上限为 360 秒；按需生成确认块，结算阶段按 epoch 推进，总等待上限 30 分钟。总耗时待实测。

<!-- TEST-CASES-BEGIN -->
| 用例 | 场景 | 预期结果 | 防止的问题 | 优先级 |
| --- | --- | --- | --- | --- |
| `V091MIX-01` | - [x] 同一 A 库保留 v0.9.1 合作关闭历史和七项同步状态，经 v0.10.0 尝试强关；正式 v0.10.1 保留合作关闭及健康 V2，让 C→A 的 100 CKB 持单在第三条 V2 上强关并确认，停 C、停 A；CURRENT_DEV 遇 V1 拒绝后仅归档原阻断 ID，同库重启，仅向新 A 提供原像，领取后重连 C 验证健康通道付款 | 八条旧记录及 v0.10.0 各状态按原约定核对；升级前目标承诺精确消费原 funding，输出仍 live、TLC 未领；首次启动给出 V1 迁移提示，dry-run 与归档只命中原阻断集合，重试后三条 V2 的 ID/outpoint 不变；由新 A 凭原像领取原 TLC，已确认消费见证、完整哈希、100 CKB 及收款锁一致，双方按实际费用对账；另一条原 V2 定向付款 Success、发票 Paid、余额按额变化 | 防止空通道退本金、旧对端代领或升级后重新强关造成假通过，也防止归档误伤其他通道 | P1 |
<!-- TEST-CASES-END -->

## 测试树

<!-- TEST-TREE-BEGIN -->
- A 同一原库的连续混合状态场景
  - v0.9.1 旧关闭历史与七项并行取样、v0.10.0 可关者强关、正式 v0.10.1 三条新 V2、CURRENT_DEV 拒绝／显式归档后成功、CURRENT_DEV 领取 v0.10.1 已上链 TLC 及另一条付款：V091MIX-01 [primary] -> SPEC-01
  - 已归档的 v0.9.1 V1 的资金回收：[not_applicable] — 本行对 V1 只验证记录处理，不把它与必须实证的 V2 持单领取混为一谈。
<!-- TEST-TREE-END -->

## Spec

### SPEC-01：同库跨版本迁移门禁与 V2 后续资金路径可从外部验证
- Condition: v0.9.1 A/B1～B7 在同一 A 库留下七项同步状态，之前 A–B4 另有一条正常合作关闭的历史；停 A 后用 v0.10.0 只尝试当前可强关的旧通道，再停 A 用正式 v0.10.1 原库启动，并与同版 C 新开三条 V2 通道。C 在结算目标通道向 A 发送持单并强关；旧承诺确认且尚未被消费时才停旧进程。首次 CURRENT_DEV 启动因 V1 拒绝，显式归档诊断中的原 V1 阻断 ID 后重试。
- Expected: 七项旧状态仍满足原已确认的逐条预期；旧正常关闭历史为 COOPERATIVE 且 funding 被精确消费；v0.10.0 不让①② funding 上链并记录各次强关的实际受理／拒绝与对应池中消费；正式 v0.10.1 识别八个旧 ID/outpoint，留下已合作关闭、带未领取 TLC 的已确认强关承诺、仍 Ready 且 funding live 三种不同结果。首次 CURRENT_DEV 因原 V1 拒绝，归档全部实际阻断的原 V1 ID 后成功启动且三条 V2 原 ID/outpoint 仍可查；C 仍离线时，CURRENT_DEV 的 A 凭升级后首次提供的原像领取旧承诺内的原 TLC；恢复 C 后核对最终净到账及另一条 V2 的独立付款。
- Observable: A、各旧对端及 C 的 `node_info`、`list_channels(include_closed=true)`、付款/发票 RPC；CKB 交易池、区块、funding/关闭交易的精确 outpoint 消费与 live cell；CURRENT_DEV 进程退出码、启动片段、RPC 可用性，`drop-v1-channel` dry-run 与归档输出，旧版已确认承诺及其未花费输出、新版领取消费的见证和逐方净到账，以及独立付款的状态／双方余额。
- Basis: 原 `V091MIX-01` 七项已确认条件，本轮新增的 v0.9.1 正常关闭、v0.10.1 升级、三条新 V2 及后续迁移／结算要求，尤其是 CURRENT_DEV 必须结算 v0.10.1 已经放到链上的 TLC；前次本机 v0.10.0 调试对①②拒绝强关，对③④⑤⑦受理、⑥原先强关。源码 tag `v0.10.1`（`d9b6bbd7`）早于 V2-only 门禁 `703ec1cc`，且新通道对端须声明 `CHANNEL_V2`；同库组合仍待实测。用户粘贴的手工记录显示 CURRENT_DEV 首次因 21 项未结 V1 记录退出，逐条归档当时七个阻断 ID 后正常迁移并启动；数量与具体旧 ID 由本轮新建数据决定，不硬编码 21。`drop-v1-channel` 明示不关闭 funding，本行不得把其输出当作 V1 资金回收。
- Source: explicit
- Testing: required

## 验证设计

- v0.9.1 在同一 30 秒取样窗口按各自原 ID/outpoint 核对：① A 为 AwaitingTxSignatures、双方签名标志齐全且 B1 离线；② A 等就绪、原 funding 未确认且清池后缺席；③ funding 已确认、A 仅本端 Ready；④ A 付款 Inflight、B4 发票 Received，双方同哈希及持单金额；⑤ 双方因原持单处于 ShuttingDown；⑥ 原持单的强关承诺精确消费原 funding，仅在池中；⑦ 离线合作关遭拒且 A 仍 Ready。此前完成的旧正常关闭历史须双方 Closed/COOPERATIVE、关闭交易确认消费原 funding，与④不是同一通道。
- v0.10.0 逐 ID 记录强关 RPC 结果、后续状态和池中完整 outpoint 消费；①②拒绝且本阶段 funding 未确认，⑥不重复广播；③④⑤⑦不预设恰好四笔同时留池，也不把受理当作 Closed。保留原目录并核对八个旧 ID。
- **三条 V2 分开取证。** 查 A、C 的 `node_info`（正式 v0.10.1、`d9b6bbd7`、声明 `CHANNEL_V2`），保存各原 ID、完整 funding outpoint，确认与其他十条记录互异。合作关闭通道须双方 Closed/COOPERATIVE、确认交易精确消费原 funding；付款通道双方 Ready 且 funding live。记录强关目标在持单前的双方本金（可用余额加预留）与各自收款锁，作为独立账本。
- **分界点在强关确认，不在请求返回。** 旧版 C 定向发持单；在同一目标通道确认 C 出向、A 入向各有且仅有一笔已承诺的 H/M，C 付款 Inflight、A 发票 Received。保存实际 expiry 和 C 最新签名承诺标识。停自动出块，由 C 强关，仅挖到精确消费目标 funding 的对应承诺已确认且旧节点已观察到强关；核对签名承诺标识（排除补入的 cell deps）、确认区块哈希，以及带 V2 特征的承诺输出 outpoint。停止推进区块，检查该输出仍 live 且池中无消费。此时 P 从未交给节点。停 C、停 A，升级窗口内保持停矿；若原输出已经被领，前置失败，不以新建通道替换。
- **迁移门禁沿用原规则。** 恢复出块时①②旧 funding 可能确认，记录实际结果。首次 CURRENT_DEV 启动须非零退出、RPC 未就绪，且包含原 V1 ID 和提示 “Close these channels and finish pending settlement/delivery with the old binary, then retry this upgrade. No records or database version were changed.”。停稳备份，在原库仅对诊断中属于原七条的非空阻断集合逐条 dry-run 核对 ID/outpoint 后显式归档，不触碰 V2，不以此证明 V1 资金已回收。以同一原库重试，核对 CURRENT_DEV 身份、RPC、三条 V2 原 ID/outpoint、归档 ID 已退出运行时查询。复核旧承诺区块与 live 输出未变、目标 TLC 尚未到期。归档前备份使用每次独立的目录，普通运行自动清理自己的备份，`debug=True` 保留现场。已有现场可用 pytest 的 `--pdb` 接入，调用 `self.inspect_saved_channels()` 查询；仅显式传 `advance_epoch=True` 时出块。
- **只让新版 A 领取。** C 保持离线，无独立 watchtower；只向新 A 调用 `settle_invoice(H, P)`。按需推进 epoch 到领取条件成熟，沿上述确认的承诺 outpoint 及其派生输出，找出实际解锁 TLC 的已确认消费（不是余额解锁）。解析对应输入的 V2 见证：所解锁条目的完整 32 字节 H、M 及原像 P 均与旧样本匹配，SHA256(P)=H，收款锁属于 A。见证中的绝对时间锁须等于 `0x4000000000000000 | (expiry_ms // 1000)`；以领取确认块的父块 median time（毫秒转整秒）核对是在原 TLC 到期前领取。没有原像的退款、仅退本金、RPC 返回成功或通道 Closed 均不算通过。
- **领取与健康付款分别断言。** 确认 A 领到目标 TLC 后才恢复原 C，让双方完成其余本金领取。只统计源自该 funding 的消费链，净额扣除额外手续费输入／找零：A 到账 = 持单前 A 本金 + M − A 实付费用，C 到账 = 持单前 C 本金 − M − C 实付费用；两者加实际总费等于 funding 容量，无剩余承诺锁。另用新哈希经保留通道原 outpoint 单跳 A→C 付 1 CKB，双方 Ready、funding 仍 live、付款 Success、发票 Paid、双方账本各减／增 1 CKB。TLC 领取成功不抵消健康通道付款失败。
