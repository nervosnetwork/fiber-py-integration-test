"""同一原库的七种 Legacy 状态、V2-only 升级门禁和新通道资金路径。"""

import os
import secrets
import shutil
import socket
import subprocess
import time
from pathlib import Path
from tempfile import mkdtemp

import pytest
import toml
import yaml

from framework.basic_fiber import COMMIT_LOCK_CODE_HASH, FiberTest, check_port
from framework.config import DEFAULT_MIN_DEPOSIT_CKB
from framework.helper.channel_settlement import (
    ChannelSettlement,
    commitment_hash_without_deps,
    unpack_channel_outpoint,
)
from framework.helper.channel_upgrade import (
    attach_saved_fiber,
    channel_state,
    mine_until,
    pool_spend,
    state_flags,
    tx_status,
)
from framework.helper.fiber_ops import (
    FiberExitedBeforeRpc,
    calculate_payment_hash,
    get_channel,
    start_with_confirm,
    wait_for_result,
)
from framework.test_fiber import FiberConfigPath, wait_for_port
from framework.util import ckb_hash, get_project_root

CKB = 100_000_000
SETTLEMENT_TIMEOUT = 30 * 60


class TestV091MixedChannelStates(FiberTest):
    fiber_version = FiberConfigPath.V091_DEV
    tmp_path_name = "tmp"
    ckb_rpc_port, ckb_p2p_port = 29414, 29425
    fiber1_rpc_port, fiber1_p2p_port = 29428, 29427
    fiber2_rpc_port, fiber2_p2p_port = 29429, 29430
    extra_fiber_rpc_port, extra_fiber_p2p_port = 29651, 29761
    fnn_log_level = "info"
    start_fiber_config = {
        "fiber_open_channel_auto_accept_min_ckb_funding_amount": 10_000 * CKB,
        "fiber_watchtower_check_interval_seconds": 2,
    }

    @classmethod
    def _setup_ckb(cls):
        ckb = Path(cls.node.ckb_dir)
        work = ckb.parent.parent
        saved = ckb.exists() or any(
            (work / f"fiber/node{i}").exists() for i in range(1, 10)
        )
        if cls.debug and saved:
            # 调试入口只需要原链和中心 A；B1～B7、C 可能本来就离线。
            center = work / "fiber/node2"
            for path in (
                ckb / "data/db/CURRENT",
                ckb / "data/network/secret_key",
                center / "fiber/store/CURRENT",
                center / "fiber/sk",
                center / "ckb/key",
                center / "node.log",
            ):
                assert path.is_file(), f"调试现场缺少 {path}，保留现场，不重新初始化"
            rpc_address = toml.load(ckb / "ckb.toml")["rpc"]["listen_address"]
            config = yaml.safe_load((center / "config.yml").read_text())
            assert rpc_address == f"127.0.0.1:{cls.ckb_rpc_port}", ckb
            assert config["ckb"]["rpc_url"] == cls.node.rpcUrl, center
            assert (
                config["rpc"]["listening_addr"] == f"127.0.0.1:{cls.fiber2_rpc_port}"
            ), center
            if not check_port(cls.ckb_rpc_port):
                cls.node.start()  # 只启动已有链，不 prepare、解包快照或开矿。
                wait_for_port(cls.ckb_rpc_port, timeout=30)
            client = cls.node.getClient()
            client.timeout, client.try_count = 5, 1
            peer_id = subprocess.check_output(
                [
                    ckb / "ckb",
                    "peer-id",
                    "from-secret",
                    "--secret-path",
                    ckb / "data/network/secret_key",
                ],
                text=True,
                timeout=5,
            ).strip()
            assert (
                peer_id == f"peer_id: {cls.node.get_peer_id()}"
            ), f"CKB RPC 与 {ckb} 不符"
            return
        assert not saved, f"测试目录已有节点数据：{work}"
        ports = (
            cls.ckb_rpc_port,
            cls.ckb_p2p_port,
            cls.fiber1_rpc_port,
            cls.fiber1_p2p_port,
            cls.fiber2_rpc_port,
            cls.fiber2_p2p_port,
            *(cls.extra_fiber_rpc_port + i for i in range(7)),
            *(cls.extra_fiber_p2p_port + i for i in range(7)),
        )
        for port in ports:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", port))
        super()._setup_ckb()

    def setup_method(self, method):
        super().setup_method(method)
        if self.debug:
            attach_saved_fiber(
                self.fiber2,
                (
                    FiberConfigPath.V091_DEV,
                    FiberConfigPath.V0100_DEV,
                    FiberConfigPath.V0101_DEV,
                    FiberConfigPath.CURRENT_DEV,
                ),
            )
            if method.__name__.startswith("test_"):
                pytest.fail(
                    "已接入保留的调试现场，不重放迁移。可用 --pdb 查看 "
                    "self.inspect_saved_channels()；完整回归需要干净目录。"
                )

    def inspect_saved_channels(self, *, advance_epoch=False):
        """手动调试入口：默认只查询；显式传 advance_epoch=True 才推进一个 epoch。"""
        if advance_epoch:
            self.node.getClient().generate_epochs("0x1")
        return self.fiber2.get_client().list_channels({"include_closed": True})

    @staticmethod
    def _direct_route(sender, receiver, outpoint, amount, *, expiry_delta=None):
        """只查路由：确认目标公开通道可见，并核对指定对端、出资点和金额。"""
        client = sender.get_client()
        target = receiver.get_pubkey()
        wait_for_result(
            f"目标通道路由可见：{outpoint}",
            lambda: any(
                edge["channel_outpoint"] == outpoint
                for edge in client.graph_channels()["channels"]
            ),
            120,
        )
        hops = client.build_router(
            {
                "amount": hex(amount),
                "hops_info": [{"pubkey": target, "channel_outpoint": outpoint}],
                "final_tlc_expiry_delta": expiry_delta,
            }
        )["router_hops"]
        assert len(hops) == 1, hops
        hop = hops[0]
        assert (
            hop["target"],
            hop["channel_outpoint"],
            int(hop["amount_received"], 16),
        ) == (target, outpoint, amount), hop
        return hops

    # TEST-MAP: V091MIX-01
    def test_one_legacy_node_keeps_seven_channel_conditions(self):
        """
        1. A 与 B4 留下正常关闭历史，再与七个旧版对端形成独立拓扑。
        2. B3 的 funding 入池时停 B3，再确认同一出资；A 仅本端 Ready。
        3. B4～B6 各留一笔已承诺的 hold TLC；B5 合作关，B7 离线后普通关被拒。
        4. 停矿；B2 的 funding 入池后停对端并清池；A 对持单的 B6 通道强关。
        5. B1 先出资、A 后出资，签名齐全时停 B1；连续检查七条原通道。
        6. A 原库先用 v0.10.0 逐条尝试强关，再用正式 v0.10.1 建三条 V2。
        7. 旧版 C 经目标通道向 A 付 100 CKB 持单并强关；原承诺确认后停 C、停 A。
        8. CURRENT_DEV 对未结 V1 原库先拒绝；备份后只归档原阻断 ID，同库重试。
        9. C 离线时只向新版 A 交原像，验证旧承诺的领取见证，再恢复 C 并核对双方净额。
        10. 在保留的健康 V2 上定向付 1 CKB，核对发票、余额与原 funding。
        """
        # 1. 星形拓扑：中心 A=fiber2，B1=fiber1，B2～B7 是六个独立旧版节点。
        # fiber1 同时是额外节点的充值来源，不让它承担七条通道的总出资。
        # B4～B7：A 各出 200 CKB，公开 CKB；对端只提供框架要求的最小预留。
        a, b1 = self.fiber2, self.fiber1
        b2, b3, b4, b5, b6, b7 = [
            self.start_new_fiber(
                self.generate_account(600),
                fiber_version=FiberConfigPath.V091_DEV,
                startup_timeout=90,
            )
            for _ in range(6)
        ]
        for peer in (a, b1, b2, b3, b4, b5, b6, b7):
            peer.get_client().timeout = 10
            peer.get_client().try_count = 1
        peers = {
            "b1": b1,
            "b2": b2,
            "b3": b3,
            "b4": b4,
            "b5": b5,
            "b6": b6,
            "b7": b7,
        }
        peer_pubkeys = {label: peer.get_pubkey() for label, peer in peers.items()}
        ckb = self.node.getClient()
        # 两条待确认通道会各自占用钱包输入；先用矿工钱包给 A 留两格独立已确认 cell。
        # 只提高出资可用性，不修改节点或其数据库。
        for _ in range(2):
            top_up = self.Ckb_cli.wallet_transfer_by_private_key(
                self.Config.MINER_PRIVATE_1,
                a.get_account()["address"]["testnet"],
                1_000,
                self.node.rpcUrl,
                3000,
            )
            self.Miner.miner_until_tx_committed(self.node, top_up, True)
        for peer, minimum in ((a, 2_500), (b1, 300)):
            available = self.Ckb_cli.wallet_get_capacity(
                peer.get_account()["address"]["testnet"], api_url=ckb.url
            )
            assert (
                available >= minimum
            ), f"{peer.rpc_port} 可用余额 {available} CKB，至少需要 {minimum} CKB"
        observer = ChannelSettlement(ckb, COMMIT_LOCK_CODE_HASH)
        closed_history = self.open_channel(
            a, b4, 200 * CKB, 0, other_config={"public": True}
        )
        history_point = unpack_channel_outpoint(
            get_channel(a, closed_history)["channel_outpoint"]
        )
        a.get_client().shutdown_channel(
            {"channel_id": closed_history, "force": False, "fee_rate": hex(1000)}
        )
        history_close = wait_for_result(
            "v0.9.1 正常关闭交易确认消费原 funding",
            lambda: observer.find_spending_transaction(history_point),
            120,
        )
        assert any(
            inp["previous_output"] == history_point for inp in history_close["inputs"]
        ), history_close
        for peer in (a, b4):
            channel_state(peer, closed_history, "Closed", required=("COOPERATIVE",))
        ready_ids = {}
        for label, peer in (("b4", b4), ("b5", b5), ("b6", b6), ("b7", b7)):
            ready_ids[label] = self.open_channel(
                a, peer, 200 * CKB, 0, other_config={"public": True}
            )
            assert (
                get_channel(a, ready_ids[label])["state"]["state_name"]
                == "ChannelReady"
            )

        # 2. A(200 CKB) — B3(400 CKB)：停矿后双出资，确认前停 B3。
        # 仅 A 的链确认，B3 不发 ChannelReady；不拿新通道代替原 funding。
        a.connect_peer(b3)
        self.node.stop_miner()
        opening3 = a.get_client().open_channel(
            {
                "pubkey": peer_pubkeys["b3"],
                "funding_amount": hex(200 * CKB),
                "public": True,
            }
        )["temporary_channel_id"]
        wait_for_result(
            "B3 收到原开通请求",
            lambda: any(
                row["channel_id"] == opening3
                for row in b3.get_client().list_channels({"only_pending": True})[
                    "channels"
                ]
            ),
            120,
        )
        id3 = b3.get_client().accept_channel(
            {"temporary_channel_id": opening3, "funding_amount": hex(400 * CKB)}
        )["channel_id"]
        row3 = channel_state(
            a,
            id3,
            "AwaitingChannelReady",
            absent=("OUR_CHANNEL_READY", "THEIR_CHANNEL_READY"),
        )
        funding3 = unpack_channel_outpoint(row3["channel_outpoint"])
        wait_for_result(
            "B3 的 funding 在池",
            lambda: tx_status(ckb, funding3["tx_hash"]) in ("pending", "proposed"),
            120,
        )
        b3.stop()
        mine_until(
            ckb,
            "B3 离线后原 funding 已确认、A 仅本端 Ready",
            lambda: tx_status(ckb, funding3["tx_hash"]) == "committed"
            and "OUR_CHANNEL_READY" in state_flags(get_channel(a, id3))
            and "THEIR_CHANNEL_READY" not in state_flags(get_channel(a, id3)),
        )
        assert (
            ckb.get_live_cell(funding3["index"], funding3["tx_hash"])["status"]
            == "live"
        )
        self.node.start_miner()

        # 3. A→B4、A→B5、A→B6 各一笔 1 CKB hold；彼此独立的发票和付款哈希。
        # B4 始终 Ready；B5 收到已承诺持单后从对端发起合作关。
        holds = {}
        edges = {}
        for label, peer in (("b4", b4), ("b5", b5), ("b6", b6)):
            channel_id = ready_ids[label]
            edges[label] = observer.snapshot_channel(a, peer, channel_id)
            preimage = "0x" + secrets.token_hex(32)
            payment_hash = ckb_hash(preimage)
            invoice = peer.get_client().new_invoice(
                {
                    "amount": hex(CKB),
                    "currency": "Fibd",
                    "payment_hash": payment_hash,
                    "hash_algorithm": "ckb_hash",
                    "final_expiry_delta": hex(9_600_000),
                    "expiry": hex(6 * 3600),
                }
            )
            sent = a.get_client().send_payment(
                {"invoice": invoice["invoice_address"], "max_parts": "0x1"}
            )
            assert sent["payment_hash"] == payment_hash
            self.wait_payment_state(a, payment_hash, "Inflight", timeout=120)
            self.wait_invoice_state(peer, payment_hash, "Received", timeout=120)
            observer.record_committed_tlcs(edges[label], payment_hash)
            assert len(edges[label]["tlcs"]) == 1 and edges[label]["sent"] == CKB
            observer.assert_payment_locked(edges[label], payment_hash)
            holds[label] = payment_hash

        b5.get_client().shutdown_channel(
            {"channel_id": ready_ids["b5"], "force": False, "fee_rate": hex(1000)}
        )
        for peer in (a, b5):
            row = channel_state(peer, ready_ids["b5"], "ShuttingDown")
            assert any(
                tlc["payment_hash"] == holds["b5"] for tlc in row["pending_tlcs"]
            ), row
        b7.stop()
        wait_for_result(
            "A 确认 B7 已离线",
            lambda: not any(
                peer["pubkey"] == peer_pubkeys["b7"]
                for peer in a.get_client().list_peers()["peers"]
            ),
            30,
        )
        with pytest.raises(Exception):
            a.get_client().shutdown_channel(
                {"channel_id": ready_ids["b7"], "force": False}
            )
        assert get_channel(a, ready_ids["b7"])["state"]["state_name"] == "ChannelReady"

        # 4. A(200 CKB) — B2(400 CKB)：仅这笔未确认 funding 被清池。
        # 先清池、后强关 B6，避免全局清池抹掉 B6 的承诺交易。
        self.node.stop_miner()
        a.connect_peer(b2)
        opening2 = a.get_client().open_channel(
            {
                "pubkey": peer_pubkeys["b2"],
                "funding_amount": hex(200 * CKB),
                "public": True,
            }
        )["temporary_channel_id"]
        wait_for_result(
            "B2 收到原开通请求",
            lambda: any(
                row["channel_id"] == opening2
                for row in b2.get_client().list_channels({"only_pending": True})[
                    "channels"
                ]
            ),
            120,
        )
        id2 = b2.get_client().accept_channel(
            {"temporary_channel_id": opening2, "funding_amount": hex(400 * CKB)}
        )["channel_id"]
        row2 = channel_state(
            a,
            id2,
            "AwaitingChannelReady",
            absent=("OUR_CHANNEL_READY", "THEIR_CHANNEL_READY"),
        )
        funding2 = unpack_channel_outpoint(row2["channel_outpoint"])
        wait_for_result(
            "B2 的 funding 在池",
            lambda: tx_status(ckb, funding2["tx_hash"]) in ("pending", "proposed"),
            120,
        )
        b2.stop()
        ckb.clear_tx_pool()
        assert tx_status(ckb, funding2["tx_hash"]) not in (
            "pending",
            "proposed",
            "committed",
        )
        signed6 = get_channel(a, ready_ids["b6"])["latest_commitment_transaction_hash"]
        assert signed6
        a.get_client().shutdown_channel({"channel_id": ready_ids["b6"], "force": True})
        closing6 = wait_for_result(
            "B6 原 funding 的强关承诺在池",
            lambda: pool_spend(ckb, edges["b6"]["funding"]),
            120,
        )
        assert tx_status(ckb, closing6) in ("pending", "proposed")
        packed6 = ckb.get_transaction(closing6, "0x0")["transaction"]
        assert commitment_hash_without_deps(packed6) == signed6
        channel_state(
            a,
            ready_ids["b6"],
            "ShuttingDown",
            required=("WAITING_COMMITMENT_CONFIRMATION",),
        )

        # 5. B1(200 CKB) — A(400 CKB)：B1 先签，A 后签且保留待确认状态。
        # B1 停机后连续取样，七条原 ID 必须同时可查，不能用先前缓存替代。
        wait_for_result(
            "A 与 B1 保持连接",
            lambda: any(
                peer["pubkey"] == peer_pubkeys["b1"]
                for peer in a.get_client().list_peers()["peers"]
            ),
            30,
        )
        opening1 = b1.get_client().open_channel(
            {"pubkey": a.get_pubkey(), "funding_amount": hex(200 * CKB), "public": True}
        )["temporary_channel_id"]
        wait_for_result(
            "A 收到原开通请求",
            lambda: any(
                row["channel_id"] == opening1
                for row in a.get_client().list_channels({"only_pending": True})[
                    "channels"
                ]
            ),
            120,
        )
        id1 = a.get_client().accept_channel(
            {"temporary_channel_id": opening1, "funding_amount": hex(400 * CKB)}
        )["channel_id"]
        row1 = channel_state(
            a,
            id1,
            "AwaitingTxSignatures",
            required=("OUR_TX_SIGNATURES_SENT", "THEIR_TX_SIGNATURES_SENT"),
        )
        funding1 = unpack_channel_outpoint(row1["channel_outpoint"])
        b1.stop()
        offline_pubkeys = {peer_pubkeys[label] for label in ("b1", "b2", "b3", "b7")}
        wait_for_result(
            "A 的四个目标对端均已离线",
            lambda: not offline_pubkeys
            & {peer["pubkey"] for peer in a.get_client().list_peers()["peers"]},
            30,
        )
        channel_ids = {"b1": id1, "b2": id2, "b3": id3, **ready_ids}
        assert len(set(channel_ids.values())) == 7, channel_ids
        deadline = time.monotonic() + 30
        while True:
            rows = {
                label: get_channel(a, channel_id)
                for label, channel_id in channel_ids.items()
            }
            for label, row in rows.items():
                assert row["pubkey"] == peer_pubkeys[label], (label, row)
            assert rows["b1"]["state"]["state_name"] == "AwaitingTxSignatures"
            assert {
                "OUR_TX_SIGNATURES_SENT",
                "THEIR_TX_SIGNATURES_SENT",
            } <= state_flags(rows["b1"])
            assert tx_status(ckb, funding1["tx_hash"]) != "committed"
            assert not offline_pubkeys & {
                peer["pubkey"] for peer in a.get_client().list_peers()["peers"]
            }
            assert rows["b2"]["state"]["state_name"] == "AwaitingChannelReady"
            assert not state_flags(rows["b2"]) & {
                "OUR_CHANNEL_READY",
                "THEIR_CHANNEL_READY",
            }
            assert tx_status(ckb, funding2["tx_hash"]) not in (
                "pending",
                "proposed",
                "committed",
            )
            assert rows["b3"]["state"]["state_name"] == "AwaitingChannelReady"
            assert "OUR_CHANNEL_READY" in state_flags(rows["b3"])
            assert "THEIR_CHANNEL_READY" not in state_flags(rows["b3"])
            assert tx_status(ckb, funding3["tx_hash"]) == "committed"
            assert rows["b4"]["state"]["state_name"] == "ChannelReady"
            assert (
                a.get_client().get_payment({"payment_hash": holds["b4"]})["status"]
                == "Inflight"
            )
            assert (
                b4.get_client().get_invoice({"payment_hash": holds["b4"]})["status"]
                == "Received"
            )
            for label in ("b4", "b5"):
                assert any(
                    t["payment_hash"] == holds[label] and int(t["amount"], 16) == CKB
                    for t in rows[label]["pending_tlcs"]
                ), (label, rows[label])
                assert any(
                    t["payment_hash"] == holds[label] and int(t["amount"], 16) == CKB
                    for t in get_channel(peers[label], channel_ids[label])[
                        "pending_tlcs"
                    ]
                ), label
            assert rows["b5"]["state"]["state_name"] == "ShuttingDown"
            assert (
                get_channel(b5, ready_ids["b5"])["state"]["state_name"]
                == "ShuttingDown"
            )
            assert rows["b6"]["state"]["state_name"] == "ShuttingDown"
            assert "WAITING_COMMITMENT_CONFIRMATION" in state_flags(rows["b6"])
            assert tx_status(ckb, closing6) in ("pending", "proposed")
            assert rows["b7"]["state"]["state_name"] == "ChannelReady"
            if time.monotonic() >= deadline:
                break
            time.sleep(2)

        # 6. 只停中心 A，在同一原库先由 v0.10.0 处理旧记录；矿工仍暂停。
        # B1～B7 不切版；①②的原 funding 此阶段既不主动提交，也不确认。
        old_ids = {"history": closed_history, **channel_ids}
        old_outpoints = {
            label: get_channel(a, channel_id)["channel_outpoint"]
            for label, channel_id in old_ids.items()
        }
        assert len(set(old_outpoints.values())) == 8, old_outpoints
        assert old_ids["history"] != old_ids["b4"]
        assert tx_status(ckb, history_close["hash"]) == "committed"
        a.stop()
        a.fiber_config_enum = FiberConfigPath.V0100_DEV
        start_with_confirm(a, fnn_log_level="info", timeout=90)
        assert a.get_client().node_info()["version"] == "0.10.0"
        for label, channel_id in old_ids.items():
            assert (
                get_channel(a, channel_id)["channel_outpoint"] == old_outpoints[label]
            )

        for label in ("b1", "b2"):
            with pytest.raises(Exception):
                a.get_client().shutdown_channel(
                    {"channel_id": channel_ids[label], "force": True}
                )
        assert tx_status(ckb, funding1["tx_hash"]) != "committed"
        # ②可能由旧节点自动重播；这里只保证本阶段没有确认原 funding。
        assert tx_status(ckb, funding2["tx_hash"]) != "committed"
        forced_old = {}
        for label in ("b3", "b4", "b5", "b7"):
            original = unpack_channel_outpoint(old_outpoints[label])
            try:
                a.get_client().shutdown_channel(
                    {"channel_id": channel_ids[label], "force": True}
                )
            except Exception as error:
                forced_old[label] = f"rejected: {error}"
                assert pool_spend(ckb, original) is None, (label, forced_old[label])
            else:
                spending_hash = wait_for_result(
                    f"v0.10.0 已受理的 {label} 强关消费原 funding",
                    lambda point=original: pool_spend(ckb, point),
                    120,
                )
                assert tx_status(ckb, spending_hash) in ("pending", "proposed")
                forced_old[label] = f"accepted: {spending_hash}"
        print("v0.10.0 旧通道逐条强关结果:", forced_old)
        assert tx_status(ckb, closing6) in ("pending", "proposed")
        assert tx_status(ckb, funding1["tx_hash"]) != "committed"
        assert tx_status(ckb, funding2["tx_hash"]) != "committed"

        # A 再以正式 v0.10.1 重开原库；C 也用该正式版，只建立 V2 新通道。
        release_binary = (
            Path(get_project_root()) / FiberConfigPath.V0101_DEV.fiber_bin_path
        )
        release_version = subprocess.check_output(
            [release_binary, "--version"], text=True, timeout=10
        ).strip()
        assert "Fiber v0.10.1 (d9b6bbd " in release_version, release_version
        a.stop()
        a.fiber_config_enum = FiberConfigPath.V0101_DEV
        start_with_confirm(a, fnn_log_level="info", timeout=90)
        release_info = a.get_client().node_info()
        assert release_info["version"] == "0.10.1" and release_info[
            "commit_hash"
        ].startswith("d9b6bbd"), release_info
        for label, channel_id in old_ids.items():
            assert (
                get_channel(a, channel_id)["channel_outpoint"] == old_outpoints[label]
            )

        self.node.start_miner()
        c = self.start_new_fiber(
            self.generate_account(600),
            fiber_version=FiberConfigPath.V0101_DEV,
            startup_timeout=90,
        )
        c.get_client().timeout = 10
        c.get_client().try_count = 1
        c_info = c.get_client().node_info()
        for info in (release_info, c_info):
            assert info["version"] == "0.10.1" and any(
                "CHANNEL_V2" in feature for feature in info["features"]
            ), info
        assert c_info["commit_hash"].startswith("d9b6bbd"), c_info
        # C 另留一格已确认的输入，三条通道的预留不挤占后续链上费用。
        self.faucet(c.account_private, 400)
        v2_ids = {
            "cooperative": self.open_channel(
                a, c, 200 * CKB, 0, other_config={"public": True}
            ),
            "force": self.open_channel(
                c, a, 200 * CKB, 0, other_config={"public": True}
            ),
            "payment": self.open_channel(
                a, c, 200 * CKB, 0, other_config={"public": True}
            ),
        }
        v2_outpoints = {}
        for purpose, channel_id in v2_ids.items():
            v2_outpoints[purpose] = get_channel(a, channel_id)["channel_outpoint"]
            assert (
                get_channel(c, channel_id)["channel_outpoint"] == v2_outpoints[purpose]
            )
            funding = unpack_channel_outpoint(v2_outpoints[purpose])
            assert (
                ckb.get_live_cell(funding["index"], funding["tx_hash"])["status"]
                == "live"
            )
        assert len(set(v2_ids.values()) | set(old_ids.values())) == 11
        assert len(set(v2_outpoints.values()) | set(old_outpoints.values())) == 11

        cooperative_point = unpack_channel_outpoint(v2_outpoints["cooperative"])
        a.get_client().shutdown_channel(
            {"channel_id": v2_ids["cooperative"], "force": False, "fee_rate": hex(1000)}
        )
        cooperative_spend = wait_for_result(
            "v0.10.1 V2 合作关闭交易确认消费原 funding",
            lambda: observer.find_spending_transaction(cooperative_point),
            120,
        )
        assert any(
            inp["previous_output"] == cooperative_point
            for inp in cooperative_spend["inputs"]
        ), cooperative_spend
        for peer in (a, c):
            channel_state(
                peer, v2_ids["cooperative"], "Closed", required=("COOPERATIVE",)
            )
        for purpose in ("force", "payment"):
            for peer in (a, c):
                channel_state(peer, v2_ids[purpose], "ChannelReady")
            funding = unpack_channel_outpoint(v2_outpoints[purpose])
            assert (
                ckb.get_live_cell(funding["index"], funding["tx_hash"])["status"]
                == "live"
            )
        # 7. 原像只在测试端。C 用原 force 出资点向 A 付持单，不能走健康通道。
        force_id = v2_ids["force"]
        edge = observer.snapshot_channel(c, a, force_id)
        force_point = edge["funding"]
        payer_lock, receiver_lock = [
            self.get_account_script(peer.account_private) for peer in (c, a)
        ]
        payer_principal, receiver_principal = [
            int(row["local_balance"], 16) + DEFAULT_MIN_DEPOSIT_CKB
            for row in edge["before"]
        ]
        assert payer_principal + receiver_principal == int(
            observer.get_output(force_point)["capacity"], 16
        )
        hold_amount = 100 * CKB
        hold_preimage = "0x" + secrets.token_hex(32)
        hold_hash = calculate_payment_hash(hold_preimage, "sha256")
        expiry_delta = hex(9_600_000)
        hold_invoice = a.get_client().new_invoice(
            {
                "amount": hex(hold_amount),
                "currency": "Fibd",
                "payment_hash": hold_hash,
                "hash_algorithm": "sha256",
                "allow_mpp": False,
                "expiry": hex(6 * 3600),
                "final_expiry_delta": expiry_delta,
            }
        )
        hops = self._direct_route(
            c, a, v2_outpoints["force"], hold_amount, expiry_delta=expiry_delta
        )
        sent = c.get_client().send_payment_with_router(
            {"router": hops, "invoice": hold_invoice["invoice_address"]}
        )
        assert sent["payment_hash"] == hold_hash, sent
        self.wait_payment_state(c, hold_hash, "Inflight", timeout=120)
        self.wait_invoice_state(a, hold_hash, "Received", timeout=120)
        observer.record_committed_tlcs(edge, hold_hash)
        observer.assert_payment_locked(edge, hold_hash)
        assert len(edge["tlcs"]) == 1 and edge["sent"] == hold_amount, edge["tlcs"]
        expiry_ms = int(edge["tlcs"][0]["expiry"], 16)
        tip_time = int(ckb.get_block_median_time(ckb.get_tip_header()["hash"]), 16)
        assert expiry_ms - tip_time > SETTLEMENT_TIMEOUT * 1000

        self.node.stop_miner()
        signed = get_channel(c, force_id)["latest_commitment_transaction_hash"]
        assert signed
        c.get_client().shutdown_channel({"channel_id": force_id, "force": True})
        closing = wait_for_result(
            "旧版 C 的承诺消费目标 funding", lambda: pool_spend(ckb, force_point), 120
        )
        mine_until(
            ckb,
            "旧版 C 的原承诺确认",
            lambda: tx_status(ckb, closing) == "committed",
            timeout=120,
        )
        for _ in range(4):  # FNN 的确认深度；到此停矿，不推进结算 epoch。
            ckb.generate_block()
        channel_state(
            c,
            force_id,
            "Closed",
            required=("UNCOOPERATIVE_LOCAL", "WAITING_ONCHAIN_SETTLEMENT"),
        )
        # v0.10.1 的对端强关扫描每 300 秒一次；停矿等 A 认出它，不追加 epoch。
        channel_state(
            a,
            force_id,
            "Closed",
            required=("UNCOOPERATIVE_REMOTE", "WAITING_ONCHAIN_SETTLEMENT"),
            timeout=360,
        )
        chain = observer.track_commitment(force_point, [payer_lock, receiver_lock])
        original_output = chain["outpoint"].copy()
        assert original_output["tx_hash"] == closing and chain["version"] == "v1", chain
        assert (
            commitment_hash_without_deps(
                ckb.get_transaction(closing, "0x0")["transaction"]
            )
            == signed
        )
        confirmed_in = ckb.get_transaction(closing)["tx_status"]["block_hash"]
        assert ckb.get_live_cell(original_output["index"], closing)["status"] == "live"
        assert pool_spend(ckb, original_output) is None
        c.stop()
        a.stop()

        # 8. 停矿、C 离线；同一 A 库首次迁移被拒，只归档诊断命中的原七条 V1。
        a.fiber_config_enum = FiberConfigPath.CURRENT_DEV
        with (Path(a.tmp_path) / "node.log").open("rb") as log:
            log.seek(0, os.SEEK_END)
            with pytest.raises(FiberExitedBeforeRpc) as rejected:
                start_with_confirm(a, fnn_log_level="info", timeout=90)
            startup_output = log.read().decode(errors="replace")
        assert rejected.value.returncode != 0 and not check_port(int(a.rpc_port))
        assert (
            "Close these channels and finish pending settlement/delivery with the old "
            "binary, then retry this upgrade. No records or database version were "
            "changed."
        ) in startup_output, startup_output[-5000:]
        blocking_ids = {
            label: channel_ids[label]
            for label in channel_ids
            if channel_ids[label].removeprefix("0x").lower() in startup_output.lower()
        }
        assert blocking_ids, startup_output[-5000:]
        assert not any(
            channel_id.removeprefix("0x").lower() in startup_output.lower()
            for channel_id in v2_ids.values()
        ), startup_output[-5000:]

        backup = Path(
            mkdtemp(
                prefix="v091-mixed-before-v1-archive-", dir=Path(a.tmp_path).parents[1]
            )
        )
        if not self.first_debug:
            self.addCleanup(shutil.rmtree, backup)
        shutil.copytree(a.tmp_path, backup / "node")
        assert (backup / "node/fiber/store/CURRENT").is_file(), backup
        self.logger.info("归档前的 A 原库备份：%s", backup)
        current_binary = (
            Path(get_project_root()) / FiberConfigPath.CURRENT_DEV.fiber_bin_path
        )
        store_path = Path(a.tmp_path) / "fiber/store"
        command_env = {
            **os.environ,
            **a.extra_env,
            "FIBER_SECRET_KEY_PASSWORD": "password0",
        }
        for label, channel_id in blocking_ids.items():
            channel_hex = channel_id.removeprefix("0x").lower()
            command = [
                current_binary,
                "drop-v1-channel",
                "--store-path",
                store_path,
                "--channel-id",
                channel_id,
            ]
            preview = subprocess.run(
                [*command, "--dry-run"],
                capture_output=True,
                text=True,
                timeout=90,
                env=command_env,
            )
            preview_output = preview.stdout + preview.stderr
            original = unpack_channel_outpoint(old_outpoints[label])
            assert preview.returncode == 0 and channel_hex in preview_output.lower(), (
                label,
                preview.returncode,
                preview_output,
            )
            assert (
                f"funding_outpoint: {original['tx_hash']}:{int(original['index'], 16)}"
                in {line.strip().lower() for line in preview_output.splitlines()}
            ), (
                label,
                original,
                preview_output,
            )
            archived = subprocess.run(
                [*command, "--yes"],
                capture_output=True,
                text=True,
                timeout=90,
                env=command_env,
            )
            assert (
                archived.returncode == 0
                and channel_hex in (archived.stdout + archived.stderr).lower()
            ), (label, archived.returncode, archived.stdout, archived.stderr)
        print("仅归档首次诊断中的原 V1 ID:", blocking_ids)

        # 不从备份运行。原像仍未交给 A，旧承诺及其未花费输出应与停机前一致。
        start_with_confirm(a, fnn_log_level="info", timeout=90)
        current_info = a.get_client().node_info()
        assert current_info["version"] != release_info["version"], current_info
        assert current_info["pubkey"] == release_info["pubkey"], current_info
        for purpose, channel_id in v2_ids.items():
            assert (
                get_channel(a, channel_id)["channel_outpoint"] == v2_outpoints[purpose]
            )
        active_after = {
            row["channel_id"]
            for row in a.get_client().list_channels({"include_closed": True})[
                "channels"
            ]
        }
        assert not set(blocking_ids.values()) & active_after, active_after

        assert ckb.get_transaction(closing)["tx_status"]["block_hash"] == confirmed_in
        assert ckb.get_live_cell(original_output["index"], closing)["status"] == "live"
        assert pool_spend(ckb, original_output) is None

        # 9. C 仍离线。只有新 A 收到原像；从同一已确认承诺逐笔跟踪，先证实领取再恢复 C。
        assert not check_port(int(c.rpc_port))
        assert (
            int(ckb.get_block_median_time(ckb.get_tip_header()["hash"]), 16) // 1000
            < expiry_ms // 1000
        )
        deadline = time.monotonic() + SETTLEMENT_TIMEOUT
        a.get_client().settle_invoice(
            {"payment_hash": hold_hash, "payment_preimage": hold_preimage}
        )
        observer.wait(
            chain,
            hold_hash,
            hold_amount,
            hold_preimage,
            until_claim=True,
            timeout=deadline - time.monotonic(),
        )
        assert (
            chain["claimed"]
            and not chain["timed_out"]
            and not check_port(int(c.rpc_port))
        )
        _, claim_tx, witness, _ = chain["spends"][-1]
        # 验证实际解锁的条目，而非余额解锁、找零或总到账碰巧相同。
        claims = [u for u in witness.unlocks if u.unlock_type < len(witness.tlcs)]
        assert len(claims) == 1 and claims[0].preimage == bytes.fromhex(
            hold_preimage[2:]
        )
        tlc = witness.tlcs[claims[0].unlock_type]
        assert tlc.tlc_type & 2  # SHA256
        assert (tlc.payment_hash, tlc.amount, tlc.expiry) == (
            bytes.fromhex(hold_hash[2:]),
            hold_amount,
            0x4000000000000000 | (expiry_ms // 1000),
        )
        payouts = [
            o["lock"]
            for o in claim_tx["outputs"]
            if o["lock"]["code_hash"] != COMMIT_LOCK_CODE_HASH
        ]
        assert payouts and all(lock == receiver_lock for lock in payouts), claim_tx[
            "hash"
        ]
        status = ckb.get_transaction(claim_tx["hash"])["tx_status"]
        assert status["status"] == "committed", status
        parent = ckb.get_block(status["block_hash"])["header"]["parent_hash"]
        assert int(ckb.get_block_median_time(parent), 16) // 1000 < expiry_ms // 1000

        c.start(fnn_log_level=self.fnn_log_level, timeout=90)
        assert c.get_client().node_info()["pubkey"] == c_info["pubkey"]
        observer.wait(
            chain,
            hold_hash,
            hold_amount,
            hold_preimage,
            timeout=deadline - time.monotonic(),
        )
        payer_fee, receiver_fee = observer.settlement_fees_by_owner(chain)
        assert chain["done"] and not chain["timed_out"]
        assert chain["net"] == [
            payer_principal - hold_amount - payer_fee,
            receiver_principal + hold_amount - receiver_fee,
        ], (chain["net"], payer_fee, receiver_fee)
        assert sum(chain["net"]) + chain["fee"] == chain["funding"]
        assert chain["fee"] < CKB // 100

        # 10. 健康 V2 独立付款：原 outpoint 上 A→C 付 1 CKB，两端分别扣款、入账。
        self.node.start_miner()
        a.connect_peer(c)
        payment_id = v2_ids["payment"]
        payment_point = unpack_channel_outpoint(v2_outpoints["payment"])
        before_payment = [get_channel(peer, payment_id) for peer in (a, c)]
        assert all(
            row["state"]["state_name"] == "ChannelReady" for row in before_payment
        ), before_payment
        assert (
            ckb.get_live_cell(payment_point["index"], payment_point["tx_hash"])[
                "status"
            ]
            == "live"
        )
        amount = CKB
        preimage = "0x" + secrets.token_hex(32)
        payment_hash = calculate_payment_hash(preimage, "sha256")
        invoice = c.get_client().new_invoice(
            {
                "amount": hex(amount),
                "currency": "Fibd",
                "payment_preimage": preimage,
                "hash_algorithm": "sha256",
                "allow_mpp": False,
            }
        )
        route = self._direct_route(a, c, v2_outpoints["payment"], amount)
        sent = a.get_client().send_payment_with_router(
            {"router": route, "invoice": invoice["invoice_address"]}
        )
        assert sent["payment_hash"] == payment_hash, sent

        def read_payment_outcome():
            payment = a.get_client().get_payment({"payment_hash": payment_hash})
            channel = get_channel(a, payment_id)
            funding_status = ckb.get_live_cell(
                payment_point["index"], payment_point["tx_hash"]
            )["status"]
            if (
                payment["status"] in ("Success", "Failed")
                or channel["state"]["state_name"] != "ChannelReady"
                or funding_status != "live"
            ):
                return payment["status"], channel["state"], funding_status

        payment_status, channel_status, funding_status = wait_for_result(
            "保留 V2 通道付款完成或出现外部可见的关闭",
            read_payment_outcome,
            120,
        )
        assert payment_status == "Success", (
            payment_hash,
            payment_status,
            channel_status,
            funding_status,
        )
        self.wait_invoice_state(c, payment_hash, "Paid", timeout=120)
        expected = (
            int(before_payment[0]["local_balance"], 16) - amount,
            int(before_payment[1]["local_balance"], 16) + amount,
        )
        for peer, value in zip((a, c), expected):
            row = self.wait_channel_tlcs_settled(
                peer, payment_id, timeout=120, expected_local_balance=value
            )
            assert row["channel_outpoint"] == v2_outpoints["payment"]
        assert (
            ckb.get_live_cell(payment_point["index"], payment_point["tx_hash"])[
                "status"
            ]
            == "live"
        )
        print("保留的 V2 通道付款成功:", payment_id, payment_hash, expected)
