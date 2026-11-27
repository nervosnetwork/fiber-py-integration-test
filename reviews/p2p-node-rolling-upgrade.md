# v0.10.1 节点逐端升级：开通道与双向付款

## 导读

两个 v0.10.1 节点先开一条公开 CKB 通道，然后逐个升级。要区分三件事：只升级一端时原通道还能付款；新旧节点之间能再开一条可用的通道；两端都升级后，两条通道都还可用。并行通道存在时，一笔普通付款成功只说明至少有一条路可走。

## 需要你决定

无。

## 用例

A 是原通道发起方，也是先升级的一端；B 在最后才升级。升级沿用各自的数据目录、身份和原链，不重开通道代替恢复。两端各准备 10,000 CKB，两次开通均为公开 CKB 通道，目标余额每端 1,000 CKB。下表每笔双向探针为 **1 Shannon**；耗时是健康本地 devnet 的阶段估算，非实测。第一阶段含建环境；第二、三阶段从所列前提就绪时计，各发起方向用独立样本。

<!-- TEST-CASES-BEGIN -->
| 用例 | 场景 | 预期结果 | 防止的问题 | 优先级 |
| --- | --- | --- | --- | --- |
| `P2PUP-01` | - [x] 两个 v0.10.1 节点间只有一条已付款清账的通道，将 A 原库升级至 CURRENT_DEV，A→B、B→A 各付一次（约 3–6 分钟） | 首笔前原 ID、outpoint 及两端余额与停机前一致；两笔均为 Success，逐笔付款端余额减 1、收款端加 1 | 升级后通道丢失、余额重置，或只有一个方向能付 | P0 |
| `P2PUP-02` | - [x] A 新、B 旧且原通道可用，分别由 A 或 B 新开第二条通道，指定新通道双向各付一次（每种约 2–4 分钟） | 两种发起方向均新增独立且就绪的通道；两笔均成功且逐笔只改变新通道余额，原通道仍就绪 | 只支持一侧发起，或付款走原通道掩盖新通道不可用 | P1 |
| `P2PUP-03` | - [x] 原通道与混合版本新开的通道留下可区分的已结清余额，将 B 原库升级至 CURRENT_DEV，再指定两条通道分别双向各付一次（约 2–4 分钟） | 付款前两端均保留两条通道的原 ID、outpoint 和余额；四笔均成功且逐笔只改变指定通道余额 | 后升级的一端遗漏通道或串账，另一条仍能付款使问题漏检 | P0 |
<!-- TEST-CASES-END -->

## 测试树

<!-- TEST-TREE-BEGIN -->
- 仅 A 升级（CURRENT_DEV ↔ v0.10.1）
  - 复用唯一的原通道双向付款：P2PUP-01 [primary] -> SPEC-01
  - 新端或旧端发起第二条通道，验证新通道双向可付：P2PUP-02 [primary] -> SPEC-02
- 再升级 B（CURRENT_DEV ↔ CURRENT_DEV）
  - 分别复用升级前的两条通道：P2PUP-03 [primary] -> SPEC-01
<!-- TEST-TREE-END -->

## Spec

### SPEC-01：更换程序不应替换就绪通道或改变已结清的资金
- Condition: 停机前无在途付款；同一节点带原目录升级，对端在线。
- Expected: 升级前已就绪的每条通道都保留原身份和已结清余额，并可继续双向付款。
- Observable: 两端按同一 channel_id 与完整 funding outpoint 查到 ChannelReady；新付款有独立终态和对应余额变动。
- Basis: [现有逐端升级场景](../test_cases/fiber/devnet/compatibility/test_p2p_node.py)保留普通双向付款；本次确认的验收要求是双端升级后还须指定两条通道分别付款，逐笔核对余额。
- Source: explicit
- Testing: required

### SPEC-02：新旧端并存时可以协商并使用另一条公开通道
- Condition: 两个直连节点分别运行旧版和目标版，已有一条可用通道。
- Expected: 新版发起、旧版接受和旧版发起、新版接受均能开出第二条通道；指定新通道双向付款时，原通道余额不变。
- Observable: 两端查到同一新 ID/outpoint，均不同于原通道；固定新 outpoint 的实际付款在该通道清账。
- Basis: [现有混合版本开通步骤](../test_cases/fiber/devnet/compatibility/test_p2p_node.py)仅从新版发起，付款未指定通道；本次确认两种发起方向均须验证新通道实际收付款。
- Source: explicit
- Testing: required

## 验证设计

- **环境**：沿用[标准 devnet](../framework/basic_fiber.py)及同一套链上合约。本机[配置](../framework/test_fiber.py)所指二进制为 v0.10.1（`d9b6bbd`）→ CURRENT_DEV（v0.11.0-rc1，`c024753`）；提交号只标识构建，不作测试门禁。
- **构造可区分的余额**：默认自动配资用普通付款，可能走错平行通道。新增样本将两端[自动接受门槛](../source/fiber/dev_config_3.yml.j2)设为 2,000 CKB，高于单端 1,000 CKB 加预留的开通请求；双方通过 `open_channel` / `accept_channel` 各自出资。按完整 outpoint 查双方余额足够后，让 A→B 在原通道单向付 10 Shannon、在第二条建成后定向付 20 Shannon，均不付回。每次停机前等在途金额清零，确认余额不对称、两条并存时数值可区分，记录两端的 ID、outpoint 和 `local_balance`。升级后、任何新付款前按身份比对，不补资金。
- **提交与取证**：保留三个阶段的普通双向 keysend；现有 helper 可重发，只能说明最终可付。新增检查先等 `list_peers` 可见对端、目标通道在两端均为 ChannelReady 且路由可见，再逐笔只提交一次、按该 hash 查 `get_payment`。定向探针用 `build_router` 指定对端及完整 outpoint，核对返回的一跳，再用 `send_payment_with_router` 实际付款（[RPC 示例](../test_cases/fiber/devnet/send_payment/path/test_final_hop_route_history.py)）。每笔须 Success 且账本清结：付款端 −1、收款端 +1 Shannon，非目标通道不变，再发反向一笔；不以往返净零代替逐笔证据。
- **等待**：初始节点启动各最多 300 秒、升级 RPC 就绪各 90 秒；本设计对每阶段的重连、通道及路由就绪合计等至多 180 秒，每笔终态 60 秒、账本收敛 30 秒。超时报告失败，只轮询查询，不以重发或另开通道补救。这是两节点真实付款的验收，不推断链上关闭或其他资产的兼容性。
