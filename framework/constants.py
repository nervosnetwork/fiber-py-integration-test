"""
Fiber 测试框架常量定义模块

提供语义化的常量定义，避免魔法数字，提高代码可读性。
"""

from typing import Union


class Amount:
    """金额单位常量和转换工具"""
    
    # 基础单位
    CKB = 100_000_000  # 1 CKB = 10^8 shannon
    UDT = 100_000_000  # 基础 UDT 单位
    
    # 常用金额
    MIN_CHANNEL_CKB = 99 * CKB  # 最小通道 CKB 金额
    
    @staticmethod
    def ckb(n: Union[int, float]) -> int:
        """
        转换 CKB 为 shannon
        
        Args:
            n: CKB 数量
            
        Returns:
            shannon 数量
            
        Example:
            >>> Amount.ckb(100)
            10000000000
        """
        return int(n * Amount.CKB)
    
    @staticmethod
    def udt(n: Union[int, float]) -> int:
        """
        转换 UDT 为基础单位
        
        Args:
            n: UDT 数量
            
        Returns:
            基础单位数量
            
        Example:
            >>> Amount.udt(1000)
            100000000000
        """
        return int(n * Amount.UDT)
    
    @staticmethod
    def to_ckb(shannon: int) -> float:
        """
        将 shannon 转换为 CKB
        
        Args:
            shannon: shannon 数量
            
        Returns:
            CKB 数量
        """
        return shannon / Amount.CKB
    
    @staticmethod
    def to_udt(base_unit: int) -> float:
        """
        将基础单位转换为 UDT
        
        Args:
            base_unit: 基础单位数量
            
        Returns:
            UDT 数量
        """
        return base_unit / Amount.UDT
    
    @staticmethod
    def to_hex(amount: int) -> str:
        """
        将金额转换为十六进制字符串
        
        Args:
            amount: 金额
            
        Returns:
            十六进制字符串
        """
        return hex(amount)


class Timeout:
    """超时时间常量（单位：秒）"""
    
    # 基础超时
    VERY_SHORT = 10     # 非常快速的操作
    SHORT = 30          # 快速操作（连接、状态查询）
    MEDIUM = 120        # 中等操作（通道打开）
    LONG = 360          # 长时操作（支付完成）
    VERY_LONG = 600     # 超长操作（复杂支付、MPP）
    
    # 特定场景超时
    CHANNEL_READY = MEDIUM      # 等待通道就绪
    PAYMENT_SUCCESS = LONG      # 等待支付成功
    GRAPH_SYNC = MEDIUM         # 等待图同步
    TX_COMMITTED = 100          # 等待交易确认
    
    # 轮询间隔
    POLL_INTERVAL = 1.0         # 默认轮询间隔
    FAST_POLL_INTERVAL = 0.1    # 快速轮询间隔
    SLOW_POLL_INTERVAL = 2.0    # 慢速轮询间隔


class ChannelState:
    """通道状态常量"""
    
    # 通道生命周期状态
    NEGOTIATING_FUNDING = "NEGOTIATING_FUNDING"
    COLLABRATING_FUNDING_TX = "COLLABRATING_FUNDING_TX"
    AWAITING_TX_SIGNATURES = "AWAITING_TX_SIGNATURES"
    AWAITING_CHANNEL_READY = "AWAITING_CHANNEL_READY"
    CHANNEL_READY = "CHANNEL_READY"
    SHUTTING_DOWN = "SHUTTING_DOWN"
    CLOSED = "CLOSED"
    
    # 状态分组
    ACTIVE_STATES = [CHANNEL_READY]
    PENDING_STATES = [NEGOTIATING_FUNDING, COLLABRATING_FUNDING_TX, AWAITING_TX_SIGNATURES, AWAITING_CHANNEL_READY]
    CLOSING_STATES = [SHUTTING_DOWN, CLOSED]
    
    @classmethod
    def is_active(cls, state: str) -> bool:
        """检查是否为活跃状态"""
        return state in cls.ACTIVE_STATES
    
    @classmethod
    def is_pending(cls, state: str) -> bool:
        """检查是否为待处理状态"""
        return state in cls.PENDING_STATES
    
    @classmethod
    def is_closing(cls, state: str) -> bool:
        """检查是否为关闭中状态"""
        return state in cls.CLOSING_STATES


class PaymentStatus:
    """支付状态常量"""
    
    CREATED = "Created"
    INFLIGHT = "Inflight"
    SUCCESS = "Success"
    FAILED = "Failed"
    
    # 终态
    FINAL_STATES = [SUCCESS, FAILED]
    
    @classmethod
    def is_final(cls, status: str) -> bool:
        """检查是否为终态"""
        return status in cls.FINAL_STATES
    
    @classmethod
    def is_success(cls, status: str) -> bool:
        """检查是否成功"""
        return status == cls.SUCCESS


class InvoiceStatus:
    """发票状态常量"""
    
    OPEN = "Open"
    CANCELLED = "Cancelled"
    EXPIRED = "Expired"
    RECEIVED = "Received"
    PAID = "Paid"
    
    # 终态
    FINAL_STATES = [CANCELLED, EXPIRED, PAID]
    
    @classmethod
    def is_final(cls, status: str) -> bool:
        """检查是否为终态"""
        return status in cls.FINAL_STATES
    
    @classmethod
    def is_paid(cls, status: str) -> bool:
        """检查是否已支付"""
        return status == cls.PAID


class FeeRate:
    """上链交易手续费率常量（用于 open_channel 的 commitment_fee_rate、funding_fee_rate 等）"""
    
    # 基础费率（shannons per KB，CKB 交易手续费率单位）
    MIN = 1000                      # 最小费率（1000 shannons per KB）
    DEFAULT = 1000                  # 默认费率（1000 shannons per KB）
    MEDIUM = 2000                  # 中等费率（2000 shannons per KB）
    HIGH = 5000                     # 高费率（5000 shannons per KB）
    
    # 最大费率
    MAX = 1_000_000_000_000_000     # 最大费率（用于不限制费率的场景）
    
    @staticmethod
    def to_hex(rate: int) -> str:
        """将费率转换为十六进制"""
        return hex(rate)


class PaymentFeeRate:
    """支付路由费率常量（用于 send_payment 的 max_fee_rate）
    
    单位：千分之一（‰），即 per thousand
    例如：5 表示 0.5%（5‰），10 表示 1%（10‰）
    """
    
    # 基础费率（per thousand，‰）
    ZERO = 0                        # 零费率
    LOW = 1                         # 低费率（1‰ = 0.1%）
    DEFAULT = 5                     # 默认费率（5‰ = 0.5%），与 RPC 默认值一致
    MEDIUM = 10                     # 中等费率（10‰ = 1%）
    HIGH = 50                       # 高费率（50‰ = 5%）
    
    # 最大费率
    MAX = 1_000_000_000_000_000     # 最大费率（用于不限制费率的场景）
    
    @staticmethod
    def to_hex(rate: int) -> str:
        """将费率转换为十六进制"""
        return hex(rate)


class TLCFeeRate:
    """TLC 转发费用比例常量（用于通道的 tlc_fee_proportional_millionths）"""
    
    # 基础费率（millionths，以百万分之一为单位）
    ZERO = 0                        # 零费率
    LOW = 100                       # 低费率（0.01%）
    DEFAULT = 1000                  # 默认费率（0.1%）
    MEDIUM = 10000                  # 中等费率（1%）
    HIGH = 100000                   # 高费率（10%）
    
    # 最大费率
    MAX = 1_000_000_000_000_000     # 最大费率（用于不限制费率的场景）
    
    @staticmethod
    def to_hex(rate: int) -> str:
        """将费率转换为十六进制"""
        return hex(rate)


class TLCExpiry:
    """TLC 过期时间常量（毫秒）"""
    
    # 基础过期时间
    DEFAULT = 14 * 24 * 60 * 60 * 1000      # 14 天（毫秒）
    SHORT = 1 * 24 * 60 * 60 * 1000         # 1 天
    MEDIUM = 7 * 24 * 60 * 60 * 1000        # 7 天
    LONG = 30 * 24 * 60 * 60 * 1000         # 30 天
    
    # Delta 值（用于 final_tlc_expiry_delta）
    DEFAULT_DELTA = 120960000               # 默认 delta（毫秒）


class HashAlgorithm:
    """哈希算法常量"""
    
    SHA256 = "sha256"
    BLAKE2B = "blake2b"
    CKB_HASH = "ckb_hash"


class Currency:
    """货币类型常量"""
    
    FIBD = "Fibd"       # Fiber Devnet
    FIBT = "Fibt"       # Fiber Testnet
    FIB = "Fib"         # Fiber Mainnet


# 导出所有常量类，方便统一导入
__all__ = [
    'Amount',
    'Timeout', 
    'ChannelState',
    'PaymentStatus',
    'InvoiceStatus',
    'FeeRate',
    'PaymentFeeRate',
    'TLCFeeRate',
    'TLCExpiry',
    'HashAlgorithm',
    'Currency',
]
