"""旧通道迁移的运维操作和取样。只用已发布的节点接口及 CKB 交易池。"""

import re
from pathlib import Path
import subprocess

from framework.basic_fiber import check_port
from framework.helper.fiber_ops import (
    get_channel,
    start_with_confirm,
    wait_for_result,
)
from framework.util import get_project_root


def attach_saved_fiber(peer, builds):
    """接入原节点；停机时只用上次已打开此库并开始监听的构建，不确认迁移。"""
    home = Path(peer.tmp_path)
    revision = last_listener = None
    with (home / "node.log").open(errors="replace") as log:
        for line in log:
            if "fnn: Starting node with git version" in line:
                build = re.search(r"\(([0-9a-f]+ [\d-]+)\)", line)
                revision = build[1] if build else None
            elif revision and "Started listening tentacle on" in line:
                address = re.search(r'"([^"]+/p2p/[^"/]+)"', line)
                if address:
                    last_listener = revision, address[1]
    if not last_listener:
        raise RuntimeError(f"{home}/node.log 没有可识别的启动及监听记录，保留原库")

    revision, address = last_listener
    for build in builds:
        binary = Path(get_project_root()) / build.fiber_bin_path
        if binary.is_file() and subprocess.check_output(
            [binary, "--version"], text=True, timeout=5
        ).strip().endswith(f"({revision})"):
            peer.fiber_config_enum = build
            break
    else:
        raise RuntimeError(f"未找到原节点构建 {revision}，请先恢复对应二进制：{home}")

    if not check_port(int(peer.rpc_port)):
        start_with_confirm(peer, confirm="n", fnn_log_level="info", timeout=30)
    client = peer.get_client()
    client.timeout, client.try_count = 5, 1
    info = client.node_info()
    assert (
        info["commit_hash"] == revision and address in info["addresses"]
    ), f"RPC {peer.rpc_port} 的节点身份或构建与 {home} 不符"


def state_flags(row):
    return {
        token.strip()
        for token in (row["state"].get("state_flags") or "").split("|")
        if token.strip()
    }


def channel_state(peer, channel_id, state, *, required=(), absent=(), timeout=120):
    def read():
        try:
            row = get_channel(peer, channel_id)
        except StopIteration:  # 正在开通，从临时 ID 过渡为正式 ID
            return None
        flags = state_flags(row)
        if (
            row["state"]["state_name"] == state
            and set(required) <= flags
            and not flags.intersection(absent)
        ):
            return row

    return wait_for_result(f"{channel_id} 等待 {state} / {required}", read, timeout)


def pool_spend(ckb, outpoint):
    """池里有交易不够，返回实际消费指定 funding 的那一笔。"""
    pool = ckb.get_raw_tx_pool()
    for tx_hash in list(pool["pending"]) + list(pool["proposed"]):
        result = ckb.get_transaction(tx_hash)
        if (
            result
            and result["tx_status"]["status"] in ("pending", "proposed")
            and any(
                i["previous_output"] == outpoint
                for i in result["transaction"]["inputs"]
            )
        ):
            return tx_hash


def tx_status(ckb, tx_hash):
    result = ckb.get_transaction(tx_hash)
    return result["tx_status"]["status"] if result else None


def mine_until(ckb, label, read, *, timeout=180):
    """调用方已暂停连续出块；只推进到指定的链上观察点。"""

    def step():
        value = read()
        if value:
            return value
        ckb.generate_block()

    return wait_for_result(label, step, timeout)
