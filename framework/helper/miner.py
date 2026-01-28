"""
挖矿相关辅助函数
"""
import time
import logging

from framework.constants import Timeout

logger = logging.getLogger(__name__)


def make_tip_height_number(node, number):
    current_tip_number = node.getClient().get_tip_block_number()
    if current_tip_number == number:
        return
        # number < current_tip_number  cut block
    if number < current_tip_number:
        block_hash = node.getClient().get_block_hash(hex(number))
        node.getClient().truncate(block_hash)
        current_tip_number = node.getClient().get_tip_block_number()
        assert current_tip_number == number
        return
        # number >= current_tip_number miner block
    miner_num = number - current_tip_number
    # self.client.
    for i in range(miner_num):
        miner_with_version(node, "0x0")
    current_tip_number = node.getClient().get_tip_block_number()
    assert current_tip_number == number


def miner_until_tx_committed(node, tx_hash, with_unknown=False, max_blocks=Timeout.TX_COMMITTED):
    """
    持续挖矿直到交易被确认
    
    Args:
        node: CKB 节点实例
        tx_hash: 交易哈希
        with_unknown: 是否在 unknown 状态时继续挖矿
        max_blocks: 最大挖矿区块数
        
    Returns:
        交易响应
        
    Raises:
        Exception: 交易被拒绝或超时
    """
    for i in range(max_blocks):
        tx_response = node.getClient().get_transaction(tx_hash)
        if tx_response["tx_status"]["status"] == "committed":
            return tx_response
        if (
            tx_response["tx_status"]["status"] == "pending"
            or tx_response["tx_status"]["status"] == "proposed"
        ):
            miner_with_version(node, "0x0")
            time.sleep(Timeout.POLL_INTERVAL)
            continue
        if with_unknown and tx_response["tx_status"]["status"] == "unknown":
            miner_with_version(node, "0x0")
            time.sleep(Timeout.POLL_INTERVAL)
            continue

        if (
            tx_response["tx_status"]["status"] == "rejected"
            or tx_response["tx_status"]["status"] == "unknown"
        ):
            raise Exception(
                f"Transaction {tx_hash[:16]}... status: {tx_response['tx_status']['status']}, "
                f"reason: {tx_response['tx_status']['reason']}"
            )

    raise Exception(
        f"Mined {max_blocks} blocks but tx {tx_hash[:16]}... still pending, "
        f"status: {tx_response['tx_status']['status']}"
    )


# https://github.com/nervosnetwork/rfcs/pull/416
# support > 0x0 when ckb2023 active
def miner_with_version(node, version, max_retries=10):
    """
    使用指定版本挖矿
    
    Args:
        node: CKB 节点实例
        version: 区块版本
        max_retries: 最大重试次数
    """
    for i in range(max_retries):
        try:
            block = node.getClient().get_block_template()
            node.getClient().submit_block(
                block["work_id"],
                block_template_transfer_to_submit_block(block, version),
            )
            break
        except Exception as e:
            time.sleep(Timeout.POLL_INTERVAL)
    pool = node.getClient().tx_pool_info()
    header = node.getClient().get_tip_header()
    logger.debug(
        f"Mined block #{int(block['number'].replace('0x', ''), 16)}"
    )
    logger.debug(
        f"Pool tip: {int(pool['tip_number'].replace('0x', ''), 16)}, "
        f"Header: {int(header['number'].replace('0x', ''), 16)}"
    )
    for i in range(Timeout.TX_COMMITTED):
        pool_info = node.getClient().tx_pool_info()
        tip_number = node.getClient().get_tip_block_number()
        if int(pool_info["tip_number"], 16) == tip_number:
            return
        time.sleep(Timeout.POLL_INTERVAL)
    raise Exception("Pool tip number does not match chain tip number")


def block_template_transfer_to_submit_block(block, version="0x0"):
    block["transactions"].insert(0, block["cellbase"])
    block["transactions"] = [x["data"] for x in block["transactions"]]
    ret = {
        "header": {
            "compact_target": block["compact_target"],
            "dao": block["dao"],
            "epoch": block["epoch"],
            "extra_hash": "0x0000000000000000000000000000000000000000000000000000000000000000",
            "nonce": "0x0",
            "number": block["number"],
            "parent_hash": block["parent_hash"],
            "proposals_hash": "0x0000000000000000000000000000000000000000000000000000000000000000",
            "timestamp": get_hex_timestamp(),
            "transactions_root": "0x0000000000000000000000000000000000000000000000000000000000000000",
            "version": version,
        },
        "extension": block["extension"],
        "uncles": [],
        "transactions": block["transactions"],
        "proposals": block["proposals"],
    }
    return ret


def get_hex_timestamp():
    timestamp = int(time.time() * 1000)
    hex_timestamp = hex(timestamp)
    return hex_timestamp


def compact_to_target(compact):
    exponent = compact >> 24
    mantissa = compact & 0x00FFFFFF
    rtn = 0
    if exponent <= 3:
        mantissa >>= 8 * (3 - exponent)
        rtn = mantissa
    else:
        rtn = mantissa
        rtn <<= 8 * (exponent - 3)
    overflow = mantissa != 0 and (exponent > 32)
    return rtn, overflow


def target_to_compact(target):
    bits = (target).bit_length()
    exponent = (bits + 7) // 8
    compact = (
        target << (8 * (3 - exponent))
        if exponent <= 3
        else (target >> (8 * (exponent - 3)))
    )
    compact = compact | (exponent << 24)
    return compact
