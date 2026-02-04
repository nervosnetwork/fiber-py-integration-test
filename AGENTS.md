# Agent 测试用例编写指南

本文档面向 AI，用于在本仓库（fiber-py-integration-test）中编写或修改 Fiber 相关集成测试用例。请按本指南的目录结构、基类选择、API 用法和断言风格来编写测试，**并在测试文件中写清注释**，保证与现有代码风格一致、可维护且可重复运行。

**重要：本框架提供了语义化的常量、智能等待工具和断言辅助函数，编写测试时应优先使用这些工具，避免硬编码魔法数字。**

---

## 1. 项目与测试目标

- **项目**：Fiber 网络节点的 Python 集成测试。
- **测试目标**：验证 Fiber JSON-RPC 行为、通道/支付/路由等场景的正确性、边界与异常。
- **可追溯性**：在测试类或用例的 docstring 中注明需求来源（如 PR 链接、Issue、规格说明），便于回溯。

---

## 2. 测试目录与文件组织

### 2.1 目录结构

```
test_cases/fiber/
├── devnet/          # 开发网/本地环境用例（最常用）
│   ├── send_payment/
│   │   ├── params/        # 按参数/子功能分子目录
│   │   │   └── test_fee.py
│   │   ├── mpp/
│   │   └── ...
│   ├── open_channel/
│   ├── accept_channel/
│   ├── connect_peer/
│   └── ...
├── testnet/         # 测试网相关
├── mainnet/         # 主网相关
├── cch/             # 跨链等专用
└── wasm/            # WASM 相关
```

- 新用例应放在与「被测 RPC/功能」对应的目录下；若该目录已有大量用例，可再按参数或场景建子目录（如 `params/`、`mpp/`）。
- 同一文件内聚焦同一类行为（如同一 RPC 的不同参数或同一场景的正例/反例）。

### 2.2 文件与用例命名

- **命名需符合测试内容**：文件名、测试类名、测试方法名必须准确反映实际测试的场景与预期，读者仅凭名称即可判断该用例在测什么、预期结果是什么。禁止使用与实现不符的泛化名称（如 `test_success`、`test_basic`）或与内容无关的名称。
- **文件名**：`test_*.py`，名称要能看出测的是哪块功能，例如 `test_fee.py`、`test_connect_peer.py`。
- **测试类名**：`TestXxx`，与文件主题一致，如 `TestFee`、`TestConnectPeer`。
- **测试方法名**：`test_<场景>_<预期>` 或 `test_<case 编号>_<简短描述>`，例如：
  - `test_case2_both_provided_max_fee_amount_tighter_succeeds`
  - `test_boundary_max_fee_rate_zero_rejects_payment`
  - `test_connect_peer`

---

## 3. 测试基类选择

### 3.1 FiberTest（每个用例独立环境）

- **适用**：每个用例需要全新的 CKB + 多个 Fiber 节点，用例间完全隔离。
- **行为**：`setup_method` 会为当前用例起 fiber1/fiber2 等，`teardown_method` 会停掉并清理。
- **使用方式**：继承 `framework.basic_fiber.FiberTest`。
- **典型场景**：简单连通性、单次 open_channel、单次 send_payment，不依赖复杂多跳拓扑。
- **内置常量类**：`FiberTest` 已绑定常用常量类（`Amount`、`Timeout`、`ChannelState` 等），可通过 `self.Amount`、`self.Timeout` 访问。

```python
from framework.basic_fiber import FiberTest
from framework.constants import Amount, ChannelState

class TestConnectPeer(FiberTest):
    def test_connect_peer(self):
        """测试节点连接"""
        self.fiber1.connect_peer(self.fiber2)
        # 使用语义化常量打开通道
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=Amount.ckb(500)
        )
        # 使用状态常量等待
        self.wait_for_channel_state(
            self.fiber1.get_client(),
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY
        )
```

### 3.2 SharedFiberTest（同一类内共享环境）

- **适用**：多个用例共享同一套 CKB + 多 Fiber 拓扑（如固定路由图），以节省启动/建链时间。
- **行为**：`setup_class` 建好 fiber1/fiber2；子类在 `setUp`（或同名约定）里建更多 fiber、开通道等；`teardown_class` 统一清理。
- **使用方式**：继承 `framework.basic_share_fiber.SharedFiberTest`。
- **典型场景**：对同一拓扑的大量 send_payment 参数/边界用例（如 test_fee 中多跳路由）。

```python
from framework.basic_share_fiber import SharedFiberTest
from framework.test_fiber import Fiber
from framework.constants import Amount, TLCFeeRate

class TestFee(SharedFiberTest):
    fiber3: Fiber
    fiber4: Fiber
    # ...

    def setUp(self):
        if getattr(TestFee, "_channel_inited", False):
            return
        TestFee._channel_inited = True
        self.__class__.fiber3 = self.start_new_fiber(self.generate_account(10000))
        # 使用语义化常量构建拓扑
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=0,
            fiber1_fee=TLCFeeRate.DEFAULT,
            fiber2_fee=TLCFeeRate.DEFAULT
        )
        self.open_channel(self.fiber2, self.fiber3, ...)
        # 构建多跳拓扑
```

**注意**：用类属性配合 `_channel_inited` 这类标志做「只初始化一次」时，要与 `teardown_class` 的职责一致，避免跨类污染。

---

## 4. 编写测试的通用步骤

1. **定场景与需求**  
   明确测的是哪个 RPC、哪种参数/边界/错误；如有 PR/文档，在类或方法的 docstring 中写上链接或引用。

2. **选基类与目录**  
   按「是否需要共享复杂拓扑」在 `FiberTest` 与 `SharedFiberTest` 间选择；按功能把文件放到对应 `test_cases/fiber/devnet/...` 目录。

3. **准备环境**  
   - `FiberTest`：直接用 `self.fiber1`、`self.fiber2`，必要时在用例里 `open_channel`。  
   - `SharedFiberTest`：在 `setUp` 里建好拓扑，用 `start_new_fiber`、`generate_account`、`open_channel`。

4. **调用 RPC 并等待**  
   通过 `fiber.get_client()` 拿到 `FiberRPCClient`，调用对应方法（如 `send_payment`、`open_channel`）。需要等状态的，用框架提供的 `wait_payment_state`、`wait_for_channel_state`，避免裸 `time.sleep` 做主逻辑。

5. **断言**  
   对返回值、错误信息、状态做明确断言；错误场景用 `pytest.raises` 并检查异常信息。

6. **清理**  
   一般不在一则用例里手写清理；依赖基类的 `teardown_method` / `teardown_class` 即可。若有临时资源，在用例末尾或 finally 中清理。

7. **写清注释（含 Step）**  
   按第 10 节「测试文件中的注释规范」在文件中写清注释：类与测试方法必有 docstring；**测试方法 docstring 中必须列出 Step 1、Step 2、…，下方代码严格按 Step 分段编写**，每段以 `# Step N: ...` 对应，关键逻辑与断言按需加行内注释。**所有代码和注释必须使用英文编写**。

---

## 5. 框架与 API 使用约定

### 5.1 常量模块（重要）

框架提供了语义化的常量类，**编写测试时必须优先使用这些常量，避免硬编码魔法数字**。

```python
from framework.constants import (
    Amount,         # 金额单位转换
    Timeout,        # 超时时间常量
    ChannelState,   # 通道状态
    PaymentStatus,  # 支付状态
    InvoiceStatus,  # 发票状态
    FeeRate,        # 上链交易手续费率常量（用于 open_channel 的 commitment_fee_rate、funding_fee_rate）
    PaymentFeeRate, # 支付路由费率常量（用于 send_payment 的 max_fee_rate，如果支持）
    TLCFeeRate,     # TLC 转发费用比例常量（用于通道的 tlc_fee_proportional_millionths）
    Currency,       # 货币类型
    HashAlgorithm,  # 哈希算法
)
```

#### 5.1.1 Amount - 金额单位

```python
# 基础常量
Amount.CKB = 100_000_000  # 1 CKB = 10^8 shannon
Amount.UDT = 100_000_000  # 基础 UDT 单位

# 转换方法
Amount.ckb(100)           # 100 CKB -> 10000000000 shannon
Amount.udt(1000)          # 1000 UDT -> 100000000000 基础单位
Amount.to_ckb(10000000000)  # 10000000000 shannon -> 100.0 CKB
Amount.to_hex(amount)     # 转为十六进制字符串

# 使用示例（推荐）
self.open_channel(fiber1, fiber2, Amount.ckb(1000), Amount.ckb(500))
# 而不是
self.open_channel(fiber1, fiber2, 1000 * 100000000, 500 * 100000000)
```

#### 5.1.2 Timeout - 超时时间

```python
Timeout.SHORT = 30        # 快速操作（连接、状态查询）
Timeout.MEDIUM = 120      # 中等操作（通道打开）
Timeout.LONG = 360        # 长时操作（支付完成）
Timeout.VERY_LONG = 600   # 超长操作（复杂支付）

# 特定场景
Timeout.CHANNEL_READY = 120   # 等待通道就绪
Timeout.PAYMENT_SUCCESS = 360 # 等待支付成功
Timeout.POLL_INTERVAL = 1.0   # 轮询间隔

# 使用示例
self.wait_for_channel_state(..., timeout=Timeout.CHANNEL_READY)
```

#### 5.1.3 状态常量

```python
# 通道状态
ChannelState.NEGOTIATING_FUNDING
ChannelState.CHANNEL_READY
ChannelState.SHUTTING_DOWN
ChannelState.CLOSED

# 支付状态
PaymentStatus.CREATED
PaymentStatus.INFLIGHT
PaymentStatus.SUCCESS
PaymentStatus.FAILED

# 发票状态
InvoiceStatus.OPEN
InvoiceStatus.PAID
InvoiceStatus.CANCELLED
InvoiceStatus.EXPIRED

# 使用示例
self.wait_for_channel_state(client, peer_id, ChannelState.CHANNEL_READY)
self.wait_payment_state(fiber1, payment_hash, PaymentStatus.SUCCESS)
```

#### 5.1.4 FeeRate - 上链交易手续费率常量

```python
FeeRate.MIN = 1000                  # 最小费率（1000 shannons per KB）
FeeRate.DEFAULT = 1000              # 默认费率（1000 shannons per KB）
FeeRate.MEDIUM = 2000               # 中等费率（2000 shannons per KB）
FeeRate.HIGH = 5000                 # 高费率（5000 shannons per KB）
FeeRate.MAX = 1_000_000_000_000_000 # 最大费率（不限制时使用）

# 使用示例：用于 open_channel 的 commitment_fee_rate 和 funding_fee_rate 参数
self.fiber1.get_client().open_channel({
    "peer_id": self.fiber2.get_peer_id(),
    "funding_amount": hex(Amount.ckb(1000)),
    "public": True,
    "commitment_fee_rate": hex(FeeRate.DEFAULT),  # commitment 交易的手续费率
    "funding_fee_rate": hex(FeeRate.DEFAULT),     # funding 交易的手续费率
})
```

**注意**：`FeeRate` 用于上链交易的手续费率（如 `open_channel` 的 `commitment_fee_rate`、`funding_fee_rate`），单位为 shannons per KB，不要与其他费率常量混淆。

#### 5.1.5 PaymentFeeRate - 支付路由费率常量

```python
PaymentFeeRate.ZERO = 0
PaymentFeeRate.DEFAULT = 5              # 默认费率（5‰ = 0.5%），与 RPC 默认值一致
PaymentFeeRate.MEDIUM = 10              # 中等费率（10‰ = 1%）
PaymentFeeRate.HIGH = 50                # 高费率（50‰ = 5%）
PaymentFeeRate.MAX = 1_000_000_000_000_000 # 最大费率（不限制时使用）

# 使用示例：用于 send_payment 的 max_fee_rate 参数
self.fiber1.get_client().send_payment({
    "target_pubkey": self.fiber2.get_client().node_info()["node_id"],
    "amount": hex(Amount.ckb(100)),
    "keysend": True,
    "max_fee_rate": hex(PaymentFeeRate.DEFAULT),  # 支付路由的最大费率限制（5‰ = 0.5%）
})
```

**注意**：
- `PaymentFeeRate` 用于 `send_payment` 的 `max_fee_rate` 参数
- 单位是千分之一（‰），即 per thousand
- 例如：`PaymentFeeRate.DEFAULT = 5` 表示 0.5%（5‰），`PaymentFeeRate.MEDIUM = 10` 表示 1%（10‰）

#### 5.1.6 TLCFeeRate - TLC 转发费用比例常量

```python
TLCFeeRate.ZERO = 0
TLCFeeRate.DEFAULT = 1000              # 默认费率（0.1%，以百万分之一为单位）
TLCFeeRate.MAX = 1_000_000_000_000_000 # 最大费率（不限制时使用）

# 使用示例：用于 open_channel 的 tlc_fee_proportional_millionths 参数
self.open_channel(
    fiber1, fiber2,
    fiber1_balance=Amount.ckb(1000),
    fiber2_balance=Amount.ckb(500),
    fiber1_fee=TLCFeeRate.DEFAULT,  # 传递给 open_channel RPC 的 tlc_fee_proportional_millionths
    fiber2_fee=TLCFeeRate.DEFAULT   # 传递给 accept_channel RPC 的 tlc_fee_proportional_millionths
)
```

**注意**：
- `TLCFeeRate` 专门用于通道的 TLC 转发费用比例（`tlc_fee_proportional_millionths`），与 `FeeRate`（用于支付费率限制）区分开
- 值以百万分之一为单位。例如：
  - `TLCFeeRate.DEFAULT = 1000` 表示 0.1%（1000 / 1,000,000 = 0.001 = 0.1%）
  - 若需要设置 0.5% 的费率，应使用 `5000`（5000 / 1,000,000 = 0.005 = 0.5%）

### 5.2 Fiber 节点与 RPC

- **RPC 文档指引**：Fiber JSON-RPC 的完整 API 规范、参数、返回类型等详见 **fiber-skill**（`.claude/skills/fiber-skill/`）。AI 在编写或调试 RPC 调用时，应优先查阅 fiber-skill 中的 `references/rpc-readme.md` 获取权威定义；框架的 `fiber_rpc.py` 为 Python 封装实现。
- **获取 RPC 客户端**：统一用 `fiber.get_client()`，得到 `FiberRPCClient`。
- **常见 RPC**（名称与用法以 `framework/fiber_rpc.py` 为准，详细规范见 fiber-skill）：
  - `send_payment(params)`、`get_payment(params)`
  - `open_channel(param)`、`accept_channel(param)`、`list_channels(param)`、`update_channel(param)`
  - `new_invoice(param)`、`get_invoice(param)`、`settle_invoice(param)`
  - `connect_peer(...)`、`list_peers()`、`node_info()`

### 5.3 基类提供的常用方法

- **拓扑与节点**  
  - `start_new_fiber(account_private_key, ...)`  
  - `generate_account(ckb_balance, ...)`  
- **通道**  
  - `open_channel(fiber1, fiber2, fiber1_balance, fiber2_balance, fiber1_fee=TLCFeeRate.DEFAULT, fiber2_fee=TLCFeeRate.DEFAULT, ...)`  
    - `fiber1_fee`: fiber1 的 TLC 转发费用比例（对应 `open_channel` RPC 的 `tlc_fee_proportional_millionths` 参数），以百万分之一为单位，默认 `TLCFeeRate.DEFAULT`（1000，即 0.1%）
    - `fiber2_fee`: fiber2 的 TLC 转发费用比例（对应 `accept_channel` RPC 的 `tlc_fee_proportional_millionths` 参数），以百万分之一为单位，默认 `TLCFeeRate.DEFAULT`（1000，即 0.1%）
  - `wait_for_channel_state(client, peer_id, expected_state, timeout=Timeout.CHANNEL_READY)`  
- **支付与状态**  
  - `send_payment(fiber1, fiber2, amount, wait, ...)`（封装好的便捷方法）  
  - `wait_payment_state(client, payment_hash, status=PaymentStatus.SUCCESS, timeout=Timeout.PAYMENT_SUCCESS)`  
  - `wait_invoice_state(client, payment_hash, status=InvoiceStatus.PAID)`
- **断言辅助**（详见 5.5 节）
  - `assert_channel_balance(fiber, peer_id, expected_local, expected_remote)`
  - `assert_payment_success(fiber, payment_hash)`
  - `assert_channel_state(fiber, peer_id, expected_state)`

在写用例时优先使用这些方法，再按需直接调 `fiber.get_client().xxx()`。

### 5.4 金额与 hex

- **推荐使用 `Amount` 类**进行金额转换，而不是手动计算：
  ```python
  # 推荐
  amount = Amount.ckb(100)
  hex_amount = hex(amount)
  
  # 不推荐
  amount = 100 * 100000000
  ```
- 传入 RPC 时多为 `hex(amount)`，可用 `Amount.to_hex(amount)`。
- 文档或代码里会出现「0.5%」「max_fee_rate=5 表示 0.5%」等，编写断言时需按实现换算一致。

### 5.5 断言辅助函数（重要）

框架提供了断言辅助类 `FiberAssert`，已绑定到 `FiberTest` 基类，可直接使用：

```python
from framework.assertions import FiberAssert

# 或直接通过基类使用（推荐）
class TestPayment(FiberTest):
    def test_payment_success(self):
        payment_hash = self.send_payment(self.fiber1, self.fiber2, Amount.ckb(100))
        
        # 断言支付成功
        self.assert_payment_success(self.fiber1, payment_hash)
        
        # 断言通道余额
        self.assert_channel_balance(
            self.fiber1, 
            self.fiber2.get_peer_id(),
            expected_local=Amount.ckb(900),
            expected_remote=Amount.ckb(100),
            tolerance=Amount.ckb(1)  # 允许 1 CKB 误差（用于手续费）
        )
        
        # 断言通道状态
        self.assert_channel_state(
            self.fiber1,
            self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY
        )
```

可用的断言方法：
- `assert_channel_balance(fiber, peer_id, expected_local, expected_remote, tolerance)`
- `assert_channel_state(fiber, peer_id, expected_state)`
- `assert_payment_success(fiber, payment_hash)`
- `assert_payment_failed(fiber, payment_hash)`
- `assert_payment_status(fiber, payment_hash, expected_status)`
- `assert_invoice_paid(fiber, payment_hash)`
- `assert_invoice_status(fiber, payment_hash, expected_status)`
- `assert_channel_count(fiber, expected_count)`
- `assert_balance_change(before_balance, after_balance, expected_change, key, tolerance)`

### 5.6 智能等待工具

框架提供了 `Waiter` 类用于更灵活的等待场景：

```python
from framework.waiter import Waiter, WaitConfig, wait_until, wait_for_value

# 基础等待
Waiter.wait_until(
    condition=lambda: channel.state == ChannelState.CHANNEL_READY,
    config=WaitConfig(timeout=Timeout.MEDIUM, interval=1.0),
    error_message="Channel not ready"
)

# 等待特定值
result = Waiter.wait_for_value(
    getter=lambda: fiber.get_client().get_payment({"payment_hash": hash})["status"],
    expected=[PaymentStatus.SUCCESS, PaymentStatus.FAILED],
    config=WaitConfig(timeout=Timeout.LONG)
)

# 带指数退避的等待
Waiter.wait_until(
    condition=some_condition,
    config=WaitConfig(
        timeout=300,
        interval=1.0,
        exponential_backoff=True,
        max_interval=10.0
    )
)

# 重试执行
result = Waiter.retry(
    func=lambda: fiber.get_client().send_payment(params),
    max_retries=3,
    retry_interval=2.0
)
```

### 5.7 对错误和异常的处理

- 期望 RPC 抛错时，用 `with pytest.raises(Exception) as exc_info:`，并对 `exc_info.value.args` 或 `str(exc_info.value)` 做包含关系断言（例如关键字 "Failed"、"max_fee"），避免依赖完整文案导致脆弱。
- 框架定义了 `WaitTimeoutError` 用于等待超时，可精确捕获：

```python
from framework.waiter import WaitTimeoutError

# RPC 错误断言
with pytest.raises(Exception) as exc_info:
    self.fiber1.get_client().send_payment({...})
err = exc_info.value.args[0] if exc_info.value.args else ""
assert "Failed" in err or "max_fee" in err.lower(), f"预期因费用限制失败，实际: {err}"

# 超时错误断言
with pytest.raises(WaitTimeoutError) as exc_info:
    self.wait_payment_state(self.fiber1, payment_hash, PaymentStatus.SUCCESS, timeout=5)
assert exc_info.value.elapsed >= 5
```

---

## 6. 断言与可读性

- 对「通过/失败」有明确条件，用 `assert cond, "简短说明"` 便于排查。
- 对枚举/状态（如 payment status、channel state）断言具体值，不要只依赖「非空」「为真」。
- 边界用例（如 max_fee_rate=0、max_fee_amount=0）要写清「预期拒绝」或「预期接受」以及对应的业务含义。

---

## 7. 参数化与重复逻辑

- 多组输入、同一套逻辑时，使用 `@pytest.mark.parametrize("a,b,expected", [(...), (...)])`，保持用例简洁。
- 重复的「解析/校验」逻辑可提成模块内辅助函数（如 `_parse_fee(fee)`），或在基类里加小方法，避免在用例里复制大段相同代码。

---

## 8. 运行与本地调试

- **单文件**：`python3 -m pytest -vv test_cases/fiber/devnet/send_payment/params/test_fee.py`
- **单用例**：`python3 -m pytest -vv test_cases/fiber/devnet/send_payment/params/test_fee.py::TestFee::test_case2_both_provided_max_fee_amount_tighter_succeeds`
- **脚本**：项目中 `test.sh` 使用 `pytest -vv` 跑传入的用例路径，并汇总到 `pytest_output.txt` / GITHUB_STEP_SUMMARY。
- **pytest 配置**：见 `pytest.ini`（如 `-s`、log 级别等），编写时不要依赖未在配置中打开的选项。

---

## 9. 反模式与禁忌

- **不要**使用与测试内容不符的用例名称：测试方法名、类名、文件名必须准确描述该用例在测什么、预期是什么；禁止泛化或误导性命名（如实际测 max_fee 却命名为 `test_success`、`test_basic`）。
- **不要**用长时间无意义的 `time.sleep` 代替 `wait_payment_state`、`wait_for_channel_state` 等显式等待。
- **不要**让用例依赖执行顺序（如依赖前一个用例改过的全局/类状态），同一类内用共享拓扑时，要明确「谁在 setUp/setup_class 里初始化」。
- **不要**在用例或配置里写真实私钥、助记词；用 `generate_account`、测试用 key 或 fixtures。
- **不要**在断言里写死与实现强绑定的完整错误字符串，优先用关键字或结构化字段判断。
- **不要**使用硬编码的魔法数字，必须使用框架提供的常量：
  ```python
  # 错误 ❌
  self.open_channel(fiber1, fiber2, 1000 * 100000000, 500 * 100000000)
  self.wait_for_channel_state(client, peer_id, "CHANNEL_READY", timeout=120)
  
  # 正确 ✓
  self.open_channel(fiber1, fiber2, Amount.ckb(1000), Amount.ckb(500))
  self.wait_for_channel_state(client, peer_id, ChannelState.CHANNEL_READY, timeout=Timeout.MEDIUM)
  ```
- **不要**使用中文编写代码和注释，所有代码、docstring、行内注释、Step 注释必须使用英文：
  ```python
  # 错误 ❌
  """测试支付功能"""
  # Step 1: 发送支付
  assert payment.status == "SUCCESS", "支付应成功"
  
  # 正确 ✓
  """Test payment functionality"""
  # Step 1: Send payment
  assert payment.status == "SUCCESS", "Payment should succeed"
  ```
- **慎用** `@pytest.mark.skip`：若必须跳过，请写清原因（如 "todo"、"restart 后 list_peer 不稳定"），便于以后修或删。

---

## 10. 测试文件中的注释规范（必须遵守）

AI 在编写或修改测试文件时，**必须在文件中写清注释**，方便后续维护和排查。注释应覆盖以下层级，且保持简洁、准确。

### 10.1 文件头注释（推荐）

- 在文件最上方、`import` 之前或之后，用 1～3 行说明本文件测的是哪块功能、对应需求或 PR（若有）。
- 若文件名已能表达主题，可省略文件头，在类 docstring 中写清即可。

```python
"""
send_payment 的 max_fee_rate / max_fee_amount 相关用例。
需求见: https://github.com/nervosnetwork/fiber/pull/1073
"""
import pytest
from framework.basic_share_fiber import SharedFiberTest
```

### 10.2 类 docstring（必须）

- 每个测试类必须有 docstring。
- 内容：本类在测什么（RPC/场景）、对应的需求/PR/规格链接（若有）、若有共享拓扑，简要说明拓扑用途（如「多跳路由：fiber1→2→3→4→5→6→7→8」）。
- 多行时保持 2～5 行，避免冗长。

```python
class TestFee(SharedFiberTest):
    """
    send_payment 的 max_fee_rate / max_fee_amount 校验与默认行为。
    需求: https://github.com/nervosnetwork/fiber/pull/1073
    拓扑: fiber1→2→3→4→5→6→7→8，用于多跳支付与费用校验。
    """
```

### 10.3 测试方法 docstring（必须）

- 每个测试方法必须有 docstring。
- 内容：用 1～3 句话写清「测什么场景、预期结果」（如「仅设置 max_fee_amount 且大于 0.5% 时，仍按 0.5% 限制」「边界：max_fee_rate=0 时应拒绝支付」）。
- **必须包含 Step**：在 docstring 中列出 Step 1、Step 2、…，概括本用例的步骤顺序；**下方方法体内的代码必须按这些 Step 分段编写**，每一段代码对应一个 Step，并配有 `# Step N: ...` 注释，与 docstring 中的 Step 一一对应。
- 若对应规格中有 Case 编号，在 docstring 中注明（如「Case 2: 同时提供 max_fee_rate 与 max_fee_amount，且 max_fee_amount 更严时，支付应成功」）。

```python
def test_case2_both_provided_max_fee_amount_tighter_succeeds(self):
    """
    Case 2: Payment should succeed when max_fee_amount is tighter but set to actual required fee.
    Step 1: Get required fee for this payment via dry_run.
    Step 2: Send real payment with tighter max_fee_amount and relaxed max_fee_rate.
    Step 3: Wait for payment success.
    Step 4: Assert actual fee does not exceed max_fee_amount.
    """
```

### 10.4 用例内步骤注释（必须）

- **先定 Step，再写代码**：测试方法内应先有步骤设计（在方法 docstring 中写出 Step 1、Step 2、…），**代码严格按 Step 分段**：每一段逻辑只做一件事，对应一个 Step，段首用 `# Step N: ...` 注释，与 docstring 中的 Step 一一对应，便于一眼看出逻辑。
- 在测试方法内部，按「准备 → 调用 → 断言」等顺序分段，用 `# Step 1: ...` / `# 步骤 1: ...` 标出；同一文件内风格统一（推荐 `# Step N: ...`）。
- 步骤数建议 2～5 步，过长时拆成子方法并给子方法起有语义的名字、配合注释说明。

```python
def test_boundary_max_fee_rate_zero_rejects_payment(self):
    """
    Boundary: Payment should be rejected when max_fee_rate=0.
    Step 1: Call send_payment with max_fee_rate=0 (dry_run).
    Step 2: Assert error message is related to fee/routing.
    """
    amount = 1 * 100000000
    # Step 1: Call send_payment with max_fee_rate=0 (dry_run)
    with pytest.raises(Exception) as exc_info:
        self.fiber1.get_client().send_payment({
            "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
            "amount": hex(amount),
            "keysend": True,
            "max_fee_rate": hex(0),
            "dry_run": True,
        })
    # Step 2: Assert error message is related to fee/routing
    err = exc_info.value.args[0] if exc_info.value.args else ""
    assert "Failed" in err or "max_fee" in err.lower(), f"Actual error: {err}"
```

### 10.5 关键逻辑与断言的行内注释（按需）

- 对「非显而易见」的逻辑必须加注释：魔法数含义、费率/金额换算公式、为何取该边界值等。
- 断言若依赖业务规则，在断言上一行或行尾用注释写明「预期依据」，例如：`# 0.1% => amount * 1 // 1000`、`# 费用不应超过 max_fee_amount`。

```python
# max_fee_rate=1 means 0.1%, fee limit = amount * 1 // 1000
expected_fee_limit = amount * max_fee_rate // 1000
# ...
assert actual_fee <= expected_fee_limit, "Actual fee should not exceed the limit calculated by rate"
```

### 10.6 setUp / 辅助逻辑的注释

- `setUp`、`setUpClass` 或类内共享的初始化逻辑：用 1～2 行注释说明在做什么（如「仅初始化一次拓扑，避免每个用例重复建链」「构建 fiber1→2→3→…→8 的线性路由」）。
- 模块内辅助函数（如 `_parse_fee`）：必须有 docstring，说明入参/出参含义及单位（如「解析 fee 字段，支持 hex 或 int，返回 msat」）。

### 10.7 注释用语与风格

- **必须使用英文**：所有代码、注释（包括 docstring、行内注释、Step 注释）必须使用英文编写，确保代码库的一致性和国际化。
- 注释要写「做什么、为何这样做」，避免只重复代码（如不要写 `# Call send_payment` 而下面只有 `send_payment(...)`，应写成 `# Use dry_run to get estimated fee for setting max_fee_amount` 等有信息量的说明）。
- skip 的用例：在 `@pytest.mark.skip("reason")` 或方法 docstring 中写清为何跳过、计划何时修复或是否长期跳过。

**总结**：类与测试方法必须有 docstring；测试方法 docstring 中必须列出 Step，**代码按 Step 分段编写**并与 docstring 中的 Step 对应；关键逻辑与断言需有行内注释；其余按「能否帮助后续读者快速理解」决定是否加注释。

---

## 11. 示例摘要（含注释风格参考）

下面示例展示「**先在方法 docstring 中列出 Step，再在代码中按 Step 分段编写**」的写法（类 docstring + 方法 docstring 含 Step + 代码内 `# Step N:` 与之一一对应 + 关键断言注释 + 使用常量），供 AI 在测试文件中写清注释时参考。

```python
"""
Test cases for send_payment max_fee_rate / max_fee_amount.
Requirement: https://github.com/nervosnetwork/fiber/pull/1073
"""
import pytest
from framework.basic_share_fiber import SharedFiberTest
from framework.test_fiber import Fiber
from framework.constants import Amount, Timeout, ChannelState, PaymentStatus, FeeRate, PaymentFeeRate, TLCFeeRate


def _parse_fee(fee) -> int:
    """Parse fee field, support hex string or integer, return msat."""
    if fee is None:
        return 0
    if isinstance(fee, str) and len(fee) > 2 and fee[:2] == "0x":
        return int(fee, 16)
    return int(fee)


class TestFee(SharedFiberTest):
    """
    Test max_fee_rate / max_fee_amount validation and default behavior for send_payment.
    Requirement: https://github.com/nervosnetwork/fiber/pull/1073
    Topology: fiber1→2→3→…→8, for multi-hop payment and fee validation.
    """
    fiber3: Fiber
    # ...

    def setUp(self):
        """Initialize multi-hop topology once to avoid rebuilding for each test case."""
        if getattr(TestFee, "_channel_inited", False):
            return
        TestFee._channel_inited = True
        self.__class__.fiber3 = self.start_new_fiber(self.generate_account(10000))
        # Build linear channels fiber1→2→3→…→8 using semantic constants
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=0,
            fiber1_fee=TLCFeeRate.DEFAULT,
            fiber2_fee=TLCFeeRate.DEFAULT
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000),
            fiber2_balance=0,
            fiber1_fee=TLCFeeRate.DEFAULT,
            fiber2_fee=TLCFeeRate.DEFAULT
        )
        # ...

    def test_case2_both_provided_max_fee_amount_tighter_succeeds(self):
        """
        Case 2: Payment should succeed when max_fee_amount is tighter but set to actual required fee.
        Step 1: Get required fee for this payment via dry_run.
        Step 2: Send real payment with tighter max_fee_amount and relaxed max_fee_rate.
        Step 3: Wait for payment success.
        Step 4: Assert actual fee does not exceed max_fee_amount.
        """
        amount = Amount.ckb(1)  # 1 CKB
        # Step 1: Get required fee for this payment via dry_run
        dry = self.fiber1.get_client().send_payment({
            "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
            "amount": hex(amount),
            "keysend": True,
            "dry_run": True,
        })
        required_fee = _parse_fee(dry.get("fee"))
        max_fee_amount = required_fee + 10000  # Slightly larger than actual fee to ensure pass
        
        # Step 2: Send real payment with tighter max_fee_amount and relaxed max_fee_rate
        payment = self.fiber1.get_client().send_payment({
            "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
            "amount": hex(amount),
            "keysend": True,
            "max_fee_rate": hex(PaymentFeeRate.HIGH),  # Sufficiently large payment routing fee rate
            "max_fee_amount": hex(max_fee_amount),
        })
        
        # Step 3: Wait for payment success
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"],
            PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS
        )
        
        # Step 4: Assert actual fee does not exceed max_fee_amount
        actual = self.fiber1.get_client().get_payment({"payment_hash": payment["payment_hash"]})
        assert _parse_fee(actual.get("fee")) <= max_fee_amount, "Fee should not exceed the set limit"

    def test_boundary_max_fee_rate_zero_rejects_payment(self):
        """
        Boundary: Payment should be rejected when max_fee_rate=0 (no fees allowed).
        Step 1: Call send_payment with max_fee_rate=0 (dry_run).
        Step 2: Assert error message is related to fee/routing.
        """
        amount = Amount.ckb(1)  # 1 CKB
        
        # Step 1: Call send_payment with max_fee_rate=0 (dry_run)
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment({
                "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                "amount": hex(amount),
                "keysend": True,
                "max_fee_rate": hex(FeeRate.ZERO),  # Zero fee rate
                "dry_run": True,
            })
        
        # Step 2: Assert error message is related to fee/routing
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert "Failed" in err or "max_fee" in err.lower(), f"max_fee_rate=0 should reject payment, actual: {err}"

    def test_payment_with_assertions(self):
        """
        Demonstrate using assertion helper functions for testing.
        Step 1: Send payment.
        Step 2: Verify using assertion helper functions (payment success, channel state).
        """
        amount = Amount.ckb(10)  # 10 CKB
        
        # Step 1: Send payment
        payment_hash = self.send_payment(
            self.fiber1, self.fiber2, amount, wait=True
        )
        
        # Step 2: Verify using assertion helper functions
        # Verify payment success
        self.assert_payment_success(self.fiber1, payment_hash)
        
        # Verify channel state
        self.assert_channel_state(
            self.fiber1, self.fiber2.get_peer_id(),
            ChannelState.CHANNEL_READY
        )
```

---

## 12. 常量速查表

| 类别 | 常量 | 说明 |
|------|------|------|
| **金额** | `Amount.ckb(n)` | n CKB 转为 shannon |
| | `Amount.udt(n)` | n UDT 转为基础单位 |
| | `Amount.to_ckb(shannon)` | shannon 转为 CKB |
| **超时** | `Timeout.SHORT` | 30 秒 |
| | `Timeout.MEDIUM` | 120 秒 |
| | `Timeout.LONG` | 360 秒 |
| | `Timeout.CHANNEL_READY` | 120 秒 |
| | `Timeout.PAYMENT_SUCCESS` | 360 秒 |
| **通道状态** | `ChannelState.CHANNEL_READY` | 通道就绪 |
| | `ChannelState.CLOSED` | 通道已关闭 |
| **支付状态** | `PaymentStatus.SUCCESS` | 支付成功 |
| | `PaymentStatus.FAILED` | 支付失败 |
| **发票状态** | `InvoiceStatus.PAID` | 发票已支付 |
| | `InvoiceStatus.OPEN` | 发票待支付 |
| **上链交易手续费率** | `FeeRate.DEFAULT` | 1000（shannons per KB，用于 open_channel 的 commitment_fee_rate、funding_fee_rate） |
| | `FeeRate.MIN` | 1000（最小费率） |
| | `FeeRate.MAX` | 不限制费率 |
| **支付路由费率** | `PaymentFeeRate.DEFAULT` | 5（5‰ = 0.5%，用于 send_payment 的 max_fee_rate） |
| | `PaymentFeeRate.ZERO` | 0（零费率） |
| | `PaymentFeeRate.MAX` | 不限制费率 |
| **TLC 转发费率** | `TLCFeeRate.DEFAULT` | 1000（0.1%，用于通道的 tlc_fee_proportional_millionths） |
| | `TLCFeeRate.ZERO` | 0（零费率） |
| | `TLCFeeRate.MAX` | 不限制费率 |

---

遵循上述约定即可在本仓库中写出风格统一、**注释完整**、**使用语义化常量**、易维护、并与现有用例一致的 Fiber 集成测试。若某模块有特殊约定（如 wasm、cch），可在对应目录下增加 `README` 或在本文件中增加对应小节。
