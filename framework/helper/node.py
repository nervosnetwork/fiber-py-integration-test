"""
节点等待和同步辅助函数
"""
from framework.test_node import CkbNode
from framework.test_cluster import Cluster
import time
import logging
from functools import wraps

from framework.constants import Timeout
from framework.waiter import WaitTimeoutError

logger = logging.getLogger(__name__)


def tx_message(client, tx_hash):
    """获取交易的输入输出信息"""
    tx = client.get_transaction(tx_hash)
    input_cells = []
    for i in range(len(tx["transaction"]["inputs"])):
        pre_cell = client.get_transaction(
            tx["transaction"]["inputs"][i]["previous_output"]["tx_hash"]
        )["transaction"]["outputs"][
            int(tx["transaction"]["inputs"][i]["previous_output"]["index"], 16)
        ]
        input_cells.append(
            {"arg": pre_cell["lock"]["args"], "capacity": int(pre_cell["capacity"], 16)}
        )
    outputs = []
    return {"inputs": input_cells, "outputs": outputs}


def wait_until_timeout(wait_times=Timeout.SHORT):
    """
    超时等待装饰器
    
    Args:
        wait_times: 最大等待次数（秒）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(wait_times):
                if func(*args, **kwargs):
                    return
                time.sleep(Timeout.POLL_INTERVAL)
            raise WaitTimeoutError(
                f"{func.__name__} timed out after {wait_times}s",
                elapsed=wait_times
            )

        return wrapper

    return decorator


@wait_until_timeout(wait_times=Timeout.SHORT)
def wait_get_transaction(node, tx_hash, status):
    """等待交易达到指定状态"""
    return node.getClient().get_transaction(tx_hash)["tx_status"]["status"] == status


@wait_until_timeout(wait_times=Timeout.SHORT)
def wait_fetch_transaction(node, tx_hash, status):
    """等待获取交易达到指定状态"""
    return node.getClient().fetch_transaction(tx_hash)["status"] == status


@wait_until_timeout(wait_times=Timeout.SHORT)
def wait_tx_pool(node, pool_key, gt_size):
    """等待交易池达到指定大小"""
    return int(node.getClient().tx_pool_info()[pool_key], 16) >= gt_size


def wait_node_height(node: CkbNode, num, wait_times=Timeout.MEDIUM):
    """
    等待节点达到指定区块高度
    
    Args:
        node: CKB 节点实例
        num: 目标区块高度
        wait_times: 超时时间（秒）
    """
    for i in range(wait_times):
        if node.getClient().get_tip_block_number() >= num:
            return
        time.sleep(Timeout.POLL_INTERVAL)
    raise WaitTimeoutError(
        f"Node did not reach height {num} within {wait_times}s, "
        f"current: {node.getClient().get_tip_block_number()}",
        elapsed=wait_times
    )


def wait_cluster_height(cluster: Cluster, num, wait_times=Timeout.MEDIUM):
    """等待集群中所有节点达到指定区块高度"""
    for ckb_node in cluster.ckb_nodes:
        wait_node_height(ckb_node, num, wait_times)


def wait_light_sync_height(ckb_light_node, height, wait_times=Timeout.MEDIUM):
    """
    等待轻节点同步到指定高度
    
    Args:
        ckb_light_node: CKB 轻节点实例
        height: 目标高度
        wait_times: 超时时间（秒）
    """
    min_height = 0
    for i in range(wait_times):
        min_height = float('inf')
        scripts = ckb_light_node.getClient().get_scripts()
        if len(scripts) == 0:
            raise Exception("No scripts registered in light node")
        for script in scripts:
            min_height = min(min_height, int(script["block_number"], 16))
        if min_height >= height:
            return
        logger.debug(f"Light node sync height: {min_height}, expected: {height}")
        time.sleep(Timeout.POLL_INTERVAL)
    raise WaitTimeoutError(
        f"Light node did not sync to height {height} within {wait_times}s, "
        f"current: {min_height}",
        elapsed=wait_times
    )


def wait_cluster_sync_with_miner(cluster: Cluster, wait_times=Timeout.MEDIUM, sync_number=None):
    """
    等待集群同步（带挖矿）
    
    Args:
        cluster: CKB 集群实例
        wait_times: 超时时间（秒）
        sync_number: 同步目标高度（可选，默认为当前最高块）
    """
    if sync_number is None:
        sync_number = cluster.ckb_nodes[0].getClient().get_tip_block_number()
    cluster.ckb_nodes[0].start_miner()
    wait_cluster_height(cluster, sync_number, wait_times)
    cluster.ckb_nodes[0].stop_miner()
