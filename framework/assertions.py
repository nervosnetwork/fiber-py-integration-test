"""
Fiber 测试框架断言辅助模块

提供常用的断言方法，简化测试代码，提高可读性。
"""

from typing import Optional, Dict, Any, List, Union
import logging

from framework.constants import (
    Amount,
    ChannelState,
    PaymentStatus,
    InvoiceStatus,
)

logger = logging.getLogger(__name__)


class AssertionError(Exception):
    """断言错误"""
    
    def __init__(self, message: str, actual: Any = None, expected: Any = None):
        super().__init__(message)
        self.actual = actual
        self.expected = expected


class FiberAssert:
    """Fiber 测试断言辅助类"""
    
    @staticmethod
    def channel_balance(
        fiber,
        peer_id: str,
        expected_local: Optional[int] = None,
        expected_remote: Optional[int] = None,
        tolerance: int = 0,
        udt: Optional[Dict] = None,
        message: str = ""
    ) -> Dict:
        """
        断言通道余额
        
        Args:
            fiber: Fiber 节点实例
            peer_id: 对端节点 peer_id
            expected_local: 期望的本地余额
            expected_remote: 期望的远端余额
            tolerance: 允许的误差范围
            udt: UDT 类型脚本（如果是 UDT 通道）
            message: 自定义错误消息
            
        Returns:
            通道信息字典
            
        Raises:
            AssertionError: 余额不匹配时
            
        Example:
            >>> FiberAssert.channel_balance(
            ...     fiber1, fiber2.get_peer_id(),
            ...     expected_local=Amount.ckb(900),
            ...     expected_remote=Amount.ckb(100)
            ... )
        """
        channels = fiber.get_client().list_channels({"peer_id": peer_id})
        
        if not channels.get("channels"):
            raise AssertionError(
                f"No channel found with peer {peer_id}",
                actual=None,
                expected="at least one channel"
            )
        
        # 找到匹配的通道
        channel = None
        for ch in channels["channels"]:
            if udt is None and ch.get("funding_udt_type_script") is None:
                channel = ch
                break
            elif udt is not None and ch.get("funding_udt_type_script") == udt:
                channel = ch
                break
        
        if channel is None:
            raise AssertionError(
                f"No matching channel found (udt={udt})",
                actual=channels["channels"],
                expected=f"channel with udt={udt}"
            )
        
        local_balance = int(channel["local_balance"], 16)
        remote_balance = int(channel["remote_balance"], 16)
        
        prefix = f"{message}: " if message else ""
        
        if expected_local is not None:
            if abs(local_balance - expected_local) > tolerance:
                raise AssertionError(
                    f"{prefix}Local balance mismatch: "
                    f"expected {expected_local} ({Amount.to_ckb(expected_local)} CKB), "
                    f"got {local_balance} ({Amount.to_ckb(local_balance)} CKB), "
                    f"diff {local_balance - expected_local}",
                    actual=local_balance,
                    expected=expected_local
                )
        
        if expected_remote is not None:
            if abs(remote_balance - expected_remote) > tolerance:
                raise AssertionError(
                    f"{prefix}Remote balance mismatch: "
                    f"expected {expected_remote} ({Amount.to_ckb(expected_remote)} CKB), "
                    f"got {remote_balance} ({Amount.to_ckb(remote_balance)} CKB), "
                    f"diff {remote_balance - expected_remote}",
                    actual=remote_balance,
                    expected=expected_remote
                )
        
        return channel
    
    @staticmethod
    def channel_state(
        fiber,
        peer_id: str,
        expected_state: Union[str, List[str]],
        channel_id: Optional[str] = None,
        include_closed: bool = False,
        message: str = ""
    ) -> Dict:
        """
        断言通道状态
        
        Args:
            fiber: Fiber 节点实例
            peer_id: 对端节点 peer_id
            expected_state: 期望的状态，可以是单个状态或状态列表
            channel_id: 指定通道 ID（可选）
            include_closed: 是否包含已关闭的通道
            message: 自定义错误消息
            
        Returns:
            通道信息字典
            
        Raises:
            AssertionError: 状态不匹配时
            
        Example:
            >>> FiberAssert.channel_state(
            ...     fiber1, fiber2.get_peer_id(),
            ...     ChannelState.CHANNEL_READY
            ... )
        """
        channels = fiber.get_client().list_channels({
            "peer_id": peer_id,
            "include_closed": include_closed
        })
        
        if not channels.get("channels"):
            raise AssertionError(
                f"No channel found with peer {peer_id}",
                actual=None,
                expected=expected_state
            )
        
        expected_states = expected_state if isinstance(expected_state, list) else [expected_state]
        
        # 查找指定或第一个通道
        channel = None
        if channel_id:
            for ch in channels["channels"]:
                if ch["channel_id"] == channel_id:
                    channel = ch
                    break
            if channel is None:
                raise AssertionError(
                    f"Channel {channel_id} not found",
                    actual=None,
                    expected=channel_id
                )
        else:
            channel = channels["channels"][0]
        
        actual_state = channel["state"]["state_name"]
        prefix = f"{message}: " if message else ""
        
        if actual_state not in expected_states:
            raise AssertionError(
                f"{prefix}Channel state mismatch: "
                f"expected {expected_states}, got '{actual_state}'",
                actual=actual_state,
                expected=expected_states
            )
        
        return channel
    
    @staticmethod
    def payment_status(
        fiber,
        payment_hash: str,
        expected_status: Union[str, List[str]],
        message: str = ""
    ) -> Dict:
        """
        断言支付状态
        
        Args:
            fiber: Fiber 节点实例
            payment_hash: 支付哈希
            expected_status: 期望的状态
            message: 自定义错误消息
            
        Returns:
            支付信息字典
            
        Raises:
            AssertionError: 状态不匹配时
            
        Example:
            >>> FiberAssert.payment_status(
            ...     fiber1, payment_hash,
            ...     PaymentStatus.SUCCESS
            ... )
        """
        payment = fiber.get_client().get_payment({"payment_hash": payment_hash})
        actual_status = payment["status"]
        expected_statuses = expected_status if isinstance(expected_status, list) else [expected_status]
        
        prefix = f"{message}: " if message else ""
        
        if actual_status not in expected_statuses:
            raise AssertionError(
                f"{prefix}Payment status mismatch: "
                f"expected {expected_statuses}, got '{actual_status}'",
                actual=actual_status,
                expected=expected_statuses
            )
        
        return payment
    
    @staticmethod
    def payment_success(fiber, payment_hash: str, message: str = "") -> Dict:
        """
        断言支付成功
        
        Args:
            fiber: Fiber 节点实例
            payment_hash: 支付哈希
            message: 自定义错误消息
            
        Returns:
            支付信息字典
        """
        return FiberAssert.payment_status(
            fiber, payment_hash, PaymentStatus.SUCCESS, message
        )
    
    @staticmethod
    def payment_failed(fiber, payment_hash: str, message: str = "") -> Dict:
        """
        断言支付失败
        
        Args:
            fiber: Fiber 节点实例
            payment_hash: 支付哈希
            message: 自定义错误消息
            
        Returns:
            支付信息字典
        """
        return FiberAssert.payment_status(
            fiber, payment_hash, PaymentStatus.FAILED, message
        )
    
    @staticmethod
    def invoice_status(
        fiber,
        payment_hash: str,
        expected_status: Union[str, List[str]],
        message: str = ""
    ) -> Dict:
        """
        断言发票状态
        
        Args:
            fiber: Fiber 节点实例
            payment_hash: 支付哈希
            expected_status: 期望的状态
            message: 自定义错误消息
            
        Returns:
            发票信息字典
        """
        invoice = fiber.get_client().get_invoice({"payment_hash": payment_hash})
        actual_status = invoice["status"]
        expected_statuses = expected_status if isinstance(expected_status, list) else [expected_status]
        
        prefix = f"{message}: " if message else ""
        
        if actual_status not in expected_statuses:
            raise AssertionError(
                f"{prefix}Invoice status mismatch: "
                f"expected {expected_statuses}, got '{actual_status}'",
                actual=actual_status,
                expected=expected_statuses
            )
        
        return invoice
    
    @staticmethod
    def invoice_paid(fiber, payment_hash: str, message: str = "") -> Dict:
        """
        断言发票已支付
        
        Args:
            fiber: Fiber 节点实例
            payment_hash: 支付哈希
            message: 自定义错误消息
            
        Returns:
            发票信息字典
        """
        return FiberAssert.invoice_status(
            fiber, payment_hash, InvoiceStatus.PAID, message
        )
    
    @staticmethod
    def channel_count(
        fiber,
        expected_count: int,
        include_closed: bool = False,
        message: str = ""
    ) -> List[Dict]:
        """
        断言通道数量
        
        Args:
            fiber: Fiber 节点实例
            expected_count: 期望的通道数量
            include_closed: 是否包含已关闭的通道
            message: 自定义错误消息
            
        Returns:
            通道列表
        """
        channels = fiber.get_client().list_channels({"include_closed": include_closed})
        actual_count = len(channels.get("channels", []))
        
        prefix = f"{message}: " if message else ""
        
        if actual_count != expected_count:
            raise AssertionError(
                f"{prefix}Channel count mismatch: "
                f"expected {expected_count}, got {actual_count}",
                actual=actual_count,
                expected=expected_count
            )
        
        return channels["channels"]
    
    @staticmethod
    def peers_connected(
        fiber,
        expected_peer_ids: List[str],
        message: str = ""
    ) -> Dict:
        """
        断言节点已连接指定对端
        
        Args:
            fiber: Fiber 节点实例
            expected_peer_ids: 期望已连接的 peer_id 列表
            message: 自定义错误消息
            
        Returns:
            节点信息字典
        """
        node_info = fiber.get_client().node_info()
        # 从通道中获取已连接的 peer
        channels = fiber.get_client().list_channels({})
        connected_peers = set(ch["peer_id"] for ch in channels.get("channels", []))
        
        prefix = f"{message}: " if message else ""
        
        for peer_id in expected_peer_ids:
            if peer_id not in connected_peers:
                raise AssertionError(
                    f"{prefix}Peer {peer_id[:16]}... not connected",
                    actual=list(connected_peers),
                    expected=expected_peer_ids
                )
        
        return node_info
    
    @staticmethod
    def balance_change(
        before_balance: Dict,
        after_balance: Dict,
        expected_change: int,
        key: str = "local_balance",
        tolerance: int = 0,
        message: str = ""
    ) -> int:
        """
        断言余额变化
        
        Args:
            before_balance: 操作前的余额
            after_balance: 操作后的余额
            expected_change: 期望的变化量（正数表示增加，负数表示减少）
            key: 要比较的余额键（local_balance, remote_balance 等）
            tolerance: 允许的误差
            message: 自定义错误消息
            
        Returns:
            实际变化量
        """
        before = before_balance.get(key, 0)
        if isinstance(before, str):
            before = int(before, 16)
            
        after = after_balance.get(key, 0)
        if isinstance(after, str):
            after = int(after, 16)
        
        actual_change = after - before
        prefix = f"{message}: " if message else ""
        
        if abs(actual_change - expected_change) > tolerance:
            raise AssertionError(
                f"{prefix}Balance change mismatch for {key}: "
                f"expected {expected_change}, got {actual_change} "
                f"(before: {before}, after: {after})",
                actual=actual_change,
                expected=expected_change
            )
        
        return actual_change


# 便捷函数
def assert_channel_balance(
    fiber,
    peer_id: str,
    expected_local: Optional[int] = None,
    expected_remote: Optional[int] = None,
    tolerance: int = 0,
    **kwargs
) -> Dict:
    """断言通道余额（便捷函数）"""
    return FiberAssert.channel_balance(
        fiber, peer_id, expected_local, expected_remote, tolerance, **kwargs
    )


def assert_channel_state(
    fiber,
    peer_id: str,
    expected_state: Union[str, List[str]],
    **kwargs
) -> Dict:
    """断言通道状态（便捷函数）"""
    return FiberAssert.channel_state(fiber, peer_id, expected_state, **kwargs)


def assert_payment_success(fiber, payment_hash: str, **kwargs) -> Dict:
    """断言支付成功（便捷函数）"""
    return FiberAssert.payment_success(fiber, payment_hash, **kwargs)


def assert_payment_failed(fiber, payment_hash: str, **kwargs) -> Dict:
    """断言支付失败（便捷函数）"""
    return FiberAssert.payment_failed(fiber, payment_hash, **kwargs)


def assert_invoice_paid(fiber, payment_hash: str, **kwargs) -> Dict:
    """断言发票已支付（便捷函数）"""
    return FiberAssert.invoice_paid(fiber, payment_hash, **kwargs)


__all__ = [
    'AssertionError',
    'FiberAssert',
    'assert_channel_balance',
    'assert_channel_state',
    'assert_payment_success',
    'assert_payment_failed',
    'assert_invoice_paid',
]
