"""
Fiber 测试框架

提供 CKB 和 Fiber 网络的集成测试基础设施。

主要模块:
    - constants: 常量定义（金额、超时、状态等）
    - waiter: 智能等待工具
    - assertions: 断言辅助函数
    - basic: CKB 测试基类
    - basic_fiber: Fiber 测试基类
    - config: 框架配置
    - rpc: CKB RPC 客户端
    - fiber_rpc: Fiber RPC 客户端

使用示例:
    from framework import FiberTest, Amount, Timeout, ChannelState
    
    class TestMyFeature(FiberTest):
        def test_payment(self):
            self.open_channel(
                self.fiber1, self.fiber2,
                Amount.ckb(1000), Amount.ckb(500)
            )
            self.wait_for_channel_state(
                self.fiber1.get_client(),
                self.fiber2.get_peer_id(),
                ChannelState.CHANNEL_READY
            )
"""

# 常量模块
from framework.constants import (
    Amount,
    Timeout,
    ChannelState,
    PaymentStatus,
    InvoiceStatus,
    FeeRate,
    TLCExpiry,
    HashAlgorithm,
    Currency,
)

# 等待工具
from framework.waiter import (
    Waiter,
    WaitConfig,
    WaitTimeoutError,
    wait_until,
    wait_for_value,
    retry,
)

# 断言辅助
from framework.assertions import (
    FiberAssert,
    assert_channel_balance,
    assert_channel_state,
    assert_payment_success,
    assert_payment_failed,
    assert_invoice_paid,
)

# 测试基类
from framework.basic import CkbTest
from framework.basic_fiber import FiberTest

# 配置
from framework.config import (
    ACCOUNT_PRIVATE_1,
    ACCOUNT_PRIVATE_2,
    DEFAULT_MIN_DEPOSIT_CKB,
    DEFAULT_MIN_DEPOSIT_UDT,
)

__all__ = [
    # 常量
    'Amount',
    'Timeout',
    'ChannelState',
    'PaymentStatus',
    'InvoiceStatus',
    'FeeRate',
    'TLCExpiry',
    'HashAlgorithm',
    'Currency',
    # 等待工具
    'Waiter',
    'WaitConfig',
    'WaitTimeoutError',
    'wait_until',
    'wait_for_value',
    'retry',
    # 断言
    'FiberAssert',
    'assert_channel_balance',
    'assert_channel_state',
    'assert_payment_success',
    'assert_payment_failed',
    'assert_invoice_paid',
    # 测试基类
    'CkbTest',
    'FiberTest',
    # 配置
    'ACCOUNT_PRIVATE_1',
    'ACCOUNT_PRIVATE_2',
    'DEFAULT_MIN_DEPOSIT_CKB',
    'DEFAULT_MIN_DEPOSIT_UDT',
]
