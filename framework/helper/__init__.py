"""
Fiber 测试框架辅助模块

提供 CKB 链交互、挖矿、交易构建等辅助功能。
"""

from framework.helper.miner import (
    make_tip_height_number,
    miner_until_tx_committed,
    miner_with_version,
    block_template_transfer_to_submit_block,
)

from framework.helper.node import (
    wait_get_transaction,
    wait_fetch_transaction,
    wait_tx_pool,
    wait_node_height,
    wait_cluster_height,
    wait_light_sync_height,
    wait_cluster_sync_with_miner,
)

__all__ = [
    # miner
    'make_tip_height_number',
    'miner_until_tx_committed',
    'miner_with_version',
    'block_template_transfer_to_submit_block',
    # node
    'wait_get_transaction',
    'wait_fetch_transaction',
    'wait_tx_pool',
    'wait_node_height',
    'wait_cluster_height',
    'wait_light_sync_height',
    'wait_cluster_sync_with_miner',
]
