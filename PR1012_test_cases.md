# PR#1012（Oneway Channel + Trampoline Routing）测试用例

适用范围：Fiber 仓库 PR#1012（分支 quake/oneway-channel）。本测试计划覆盖两类核心变更：

- Trampoline Routing：支付在部分拓扑不可见/私有通道场景下仍可完成。
- One-way Channel：通道只允许约定方向的支付/转发，反向必须被拒绝（尤其要覆盖 dry-run 与实际支付的一致性）。

## 1. 目标

- 验证 trampoline routing 的正确性：路由构造、费用预算、expiry 约束、feature gating、失败模式。
- 验证 one-way channel 的方向约束：路由层与通道层语义一致、错误提示稳定、不会破坏已有双向通道行为。
- 验证对现有支付/MPP/路由/发票等功能的回归影响。

## 2. 测试环境与前置条件

### 2.1 环境

- 本地/CI：macOS/Linux 均可。
- Fiber 节点测试：Rust 单元/集成测试（`crates/fiber-lib/src/fiber/tests/*`）。
- Python devnet 集成测试：`test_cases/fiber/devnet/*`。

### 2.2 前置条件

- 至少准备 2～6 个节点拓扑（Rust 测试中可用 `create_n_nodes_network_with_visibility`）。
- 能控制通道可见性（public/private），并可更新节点 features（trampoline on/off）。
- One-way 通道开通入口可用：RPC `open_channel(one_way=true)`。

## 3. 变更点与测试映射

### 3.1 Trampoline Routing 涉及代码路径

- 路由：`NetworkGraph::build_route` / `find_trampoline_route`
  - 文件：`fiber/crates/fiber-lib/src/fiber/graph.rs`
- 支付：`SendPaymentCommand` / `SendPaymentData` / TrampolineHop
  - 文件：`fiber/crates/fiber-lib/src/fiber/payment.rs`
- 数据结构：`types.rs` 与 `fiber.mol`（onion/trampoline 相关字段）
  - 文件：`fiber/crates/fiber-lib/src/fiber/types.rs`, `fiber/crates/fiber-lib/src/fiber/schema/fiber.mol`
- 测试：新增 `fiber/crates/fiber-lib/src/fiber/tests/trampoline.rs`

### 3.2 One-way Channel 涉及代码路径

- 通道状态：`ChannelActorState.is_one_way`
  - 文件：`fiber/crates/fiber-lib/src/fiber/channel.rs`
- 入站 TLC 方向校验：`handle_add_tlc_peer_message` 返回 `IncorrectTlcDirection`
  - 文件：`fiber/crates/fiber-lib/src/fiber/channel.rs`
- RPC 参数：`open_channel(one_way)`
  - 文件：`fiber/crates/fiber-lib/src/rpc/channel.rs`
- 迁移：`mig_20251219`（确保旧 DB 能读）
  - 文件：`fiber/migrate/src/migrations/mig_20251219.rs`
- Python 集成用例：`test_oneway_channel.py`
  - 文件：`test_cases/fiber/devnet/open_channel/test_oneway_channel.py`

## 4. 测试用例列表

约定：

- P0：必须在合入/发布前完成。
- P1：建议完成（高风险分支/边界）。
- P2：回归补充/稳定性验证。

### 4.1 Trampoline Routing（功能正确性）

#### 4.1.1 Fee 规则与用例设计要点

参考规范：[trampoline-routing.md](file:///Volumes/SSD/vscode/fiber-py-integration-test/fiber/docs/specs/trampoline-routing.md)

- fee 分两部分：Trampoline Service Fee（trampoline 节点的服务费）+ Routing Fee（外层 onion 路由中间跳的通道费）。
- `max_fee_amount` 必须先覆盖全部 Trampoline Service Fee，否则会在 build route 阶段直接失败，报错包含 required/budget。
- Trampoline Service Fee 计算（从后往前累加）：
  - 每个 trampoline hop 的 service fee：`fee = ceil(amount_to_forward * fee_rate_ppm / 1_000_000)`
  - `fee_rate_ppm` 默认：`DEFAULT_FEE_RATE * 2`（当 hop.fee_rate 未指定）
- 预算拆分：
  - `remaining_budget = max_fee_amount - trampoline_service_fee_total`
  - remaining_budget 会按段（segments）平均分配给各段 pathfinding（payer->t1、t1->t2、...）。
- 用例建议：
  - TR-001/2/3（成功类）建议显式设置 `max_fee_amount` 为“明显高于 required”的值，避免环境波动导致 flake。
  - TR-006（失败类）应刻意设置 `max_fee_amount < trampoline_service_fee_total`，并断言错误包含 `max_fee_amount too low for trampoline service fees` 以及 required/budget 字段。

| ID | 优先级 | 类型 | 场景 | 前置条件 | 步骤 | 期望结果 |
|---|---|---|---|---|---|---|
| TR-001 | P0 | Rust 集成 | 基础 trampoline（invoice）成功 | 拓扑：A-(public)->B-(private)->C；A 可见 B；A 不可通过 gossip 直接到 C | 1) C 生成 invoice 并插入 2) A `send_payment(invoice, trampoline_hops=[B])` | 1) 构造 route 成功 2) 支付状态 Success |
| TR-002 | P0 | Rust 集成 | 基础 trampoline（keysend）成功 | 同 TR-001 | 1) A `send_payment(target=C, amount, keysend=true, trampoline_hops=[B])` | 支付 Success |
| TR-003 | P0 | Rust 集成 | 多 trampoline hops（keysend）成功 | 拓扑：A-(public)->T1-(public)->T2-(private)->C | 1) A `send_payment(target=C, keysend=true, trampoline_hops=[T1,T2])` | 支付 Success |
| TR-004 | P0 | Rust 集成 | 未指定 trampoline_hops 时应失败 | 拓扑同 TR-001（C 对 A 不可见） | 1) A `send_payment(invoice)`（不带 trampoline_hops） | 返回失败，错误包含 “Failed to build route” 或等价 NoPathFound |
| TR-005 | P0 | Rust 集成 | trampoline hop 不支持 feature 时失败 | 拓扑同 TR-001；B features 关闭 trampoline | 1) 关闭 B 的 trampoline feature 2) 等待 A 的网络图/节点公告同步到 “B 不支持 trampoline” 的状态 3) A 发起 trampoline 支付：`send_payment(... trampoline_hops=[B])` | 返回失败，错误包含 “invalid trampoline_hops”/“does not support trampoline routing” |
| TR-006 | P1 | Rust 集成 | max_fee_amount 不足以覆盖 trampoline service fee | 至少 2 个 trampoline hop 且设置 hop fee_rate；设置很小 max_fee_amount | 1) A 发送 trampoline 支付 | 返回失败，错误包含 “max_fee_amount too low for trampoline service fees” |
| TR-007 | P1 | Rust 集成 | tlc_expiry_delta 超限失败 | 设置 trampoline_hops 的 tlc_expiry_delta 使累加超过 tlc_expiry_limit | 1) A 发送 trampoline 支付 | 返回失败，错误包含 “exceeds tlc_expiry_limit” |
| TR-008 | P1 | Rust 集成 | 首跳 trampoline = source/target 的参数校验 | hops[0] = source 或 hops[0] = target | 1) A 发送 trampoline 支付 | 返回失败，错误包含 “first hop must not be source/target” |
| TR-009 | P2 | Rust 集成 | 多 private trampoline hops 成功 | 拓扑：A-(public)->T1-(private)->T2-(private)->...->C | 1) A 使用 trampoline_hops=[T1,T2,...] 发送 invoice 支付 | 支付 Success |

对应现有测试参考：

- `fiber/crates/fiber-lib/src/fiber/tests/trampoline.rs`（包含 TR-001/2/3/4/5/9 的大部分场景）。

### 4.2 Trampoline Routing（回归与兼容性）

| ID | 优先级 | 类型 | 场景 | 前置条件 | 步骤 | 期望结果 |
|---|---|---|---|---|---|---|
| TR-R-001 | P0 | Rust 全量 | 不启用 trampoline 时行为不变 | 与基线版本对比（或以现有 tests 作为约束） | 1) 运行 fiber-lib 全部 tests | 现有测试全绿，无新增 flake |
| TR-R-002 | P1 | RPC 集成 | build_router + send_payment_with_router 不受影响 | 可构造可达的多跳 public 拓扑 | 1) build_router 2) send_payment_with_router | 成功，费用/expiry 合理 |
| TR-R-003 | P2 | 性能/稳定性 | 大量节点时寻路耗时可接受 | 构造 50+ 节点拓扑（可选） | 1) 多次发送支付，统计构造路由耗时 | 无明显退化/超时 |

### 4.3 One-way Channel（功能正确性：通道层）

| ID | 优先级 | 类型 | 场景 | 前置条件 | 步骤 | 期望结果 |
|---|---|---|---|---|---|---|
| OW-001 | P0 | Rust 单元/集成 | one-way 反向入站 add_tlc 被拒绝 | 建立 one-way 通道，明确允许发送方与接收方 | 1) 从不允许方向模拟对端发送 AddTlc | `IncorrectTlcDirection` 或等价错误 |
| OW-002 | P1 | RPC 集成 | public + one_way 参数校验 | 无 | 1) open_channel(public=true, one_way=true) | 返回 InvalidParameter（不允许 public one-way） |
| OW-003 | P1 | Rust/RPC | one-way 正向支付成功 | 建立 one-way 通道 | 1) 允许方向发起 keysend 或 invoice 支付 | Success |

### 4.4 One-way Channel（功能正确性：路由层一致性）

说明：此类用例用于保证 dry-run 与实际支付一致；当前已知风险是“图层未过滤反向边”。

| ID | 优先级 | 类型 | 场景 | 前置条件 | 步骤 | 期望结果 |
|---|---|---|---|---|---|---|
| OW-004 | P0 | Python devnet | one-way 反向 dry-run 必须 no path found | `open_channel(one_way=true, public=false)` | 1) A->B 正向支付成功 2) B->A `send_payment(dry_run=true)` | 抛异常，包含 “no path found” |
| OW-005 | P0 | Rust 图层 | graph 层 outbounds/inbounds 过滤反向方向 | graph 中注册 one-way channel | 1) `get_node_outbounds(allowed_sender)` 有边 2) `get_node_outbounds(other)` 无边 | 反向边被过滤，`build_route` 对反向返回 NoPathFound |
| OW-006 | P1 | Python devnet | one-way 反向真实支付失败且状态可观测 | 同 OW-004 | 1) B->A `send_payment(dry_run=false)` 2) 等待 payment 状态 | 失败状态为 Failed（错误原因稳定可断言） |

现有 Python 用例参考：

- `test_cases/fiber/devnet/open_channel/test_oneway_channel.py`（对应 OW-004）。

### 4.5 迁移与存储兼容性

| ID | 优先级 | 类型 | 场景 | 前置条件 | 步骤 | 期望结果 |
|---|---|---|---|---|---|---|
| MIG-001 | P0 | 迁移验证 | 旧版本 DB 迁移后可正常启动 | 准备 v0.6.0 DB 样本 | 1) 运行迁移 2) 启动新节点读取通道状态 | 不崩溃，通道可列出，状态一致 |
| MIG-002 | P1 | 迁移验证 | 迁移后仍可支付/路由 | 同 MIG-001 | 1) 在迁移后环境发起一次支付 | Success 或符合预期失败 |

## 5. 执行顺序建议（最小集）

1. P0（必须）：TR-001/002/003/004/005 + TR-R-001 + OW-004 + MIG-001。
2. P1（建议）：TR-006/007/008 + OW-002/005/006 + MIG-002。
3. P2：TR-009/TR-R-003。

## 6. 通过/失败判定

- 所有 P0 用例通过，且无新引入的 flake（同一组用例重复跑 3 次至少 2 次全绿）。
- 失败用例必须具备可定位信息：错误类型/错误字符串稳定（至少包含关键子串）。

## 7. 附：建议的断言关键字（便于稳定断言）

- 路由失败：`no path found` / `Failed to build route`
- trampoline hop 不支持：`invalid trampoline_hops` / `does not support trampoline routing`
- fee 预算不足：`max_fee_amount too low for trampoline service fees`
- expiry 超限：`exceeds tlc_expiry_limit`
- one-way 方向错误：`IncorrectTlcDirection`
