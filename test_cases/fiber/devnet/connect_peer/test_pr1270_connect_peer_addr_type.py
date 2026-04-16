"""
PR-1270: connect_peer optional addr_type (tcp / ws / wss) when dialing by pubkey.

Regression: WASM clients need to pick a WebSocket-capable multiaddr from the graph;
native nodes must reject addr_type=wss when the peer has no WSS address advertised.
"""

import time

import pytest

from framework.basic_share_fiber import SharedFiberTest
from framework.test_fiber import Fiber
from framework.util import generate_account_privakey


def _normalize_listen_addr(addr: str) -> str:
    return addr.replace("0.0.0.0", "127.0.0.1").replace("0。0.0.0", "127.0.0.1")


def _multiaddr_with_transport_before_p2p(addr: str, transport: str) -> str:
    """Insert /ws or /wss immediately before /p2p/... (tentacle multiaddr)."""
    addr = _normalize_listen_addr(addr)
    needle = f"/{transport}/"
    if needle in addr or addr.endswith(f"/{transport}"):
        return addr
    p2p = addr.find("/p2p/")
    assert p2p != -1, f"multiaddr missing /p2p/: {addr!r}"
    return addr[:p2p] + f"/{transport}" + addr[p2p:]


class TestPR1270ConnectPeerAddrType(SharedFiberTest):
    """
    fiber1 为中心：连接 fiber2、fiber3、fiber4；fiber2 关闭与监听端口复用的 WS，
    使图上仅有 TCP；fiber3 额外通告 WSS，使图上有 WSS。
    """

    fiber3: Fiber
    fiber4: Fiber

    shared_fiber2_extra_config = {"fiber_reuse_port_for_websocket": False}

    def setUp(self):
        if getattr(TestPR1270ConnectPeerAddrType, "_topology_ready", False):
            return
        TestPR1270ConnectPeerAddrType._topology_ready = True

        self.__class__.fiber3 = self.start_new_fiber(generate_account_privakey())
        self.fiber1.connect_peer(self.fiber3)
        time.sleep(1)

        base_addr = _normalize_listen_addr(
            self.fiber3.get_client().node_info()["addresses"][0]
        )
        wss_announced = _multiaddr_with_transport_before_p2p(base_addr, "wss")

        self.fiber3.stop()
        deploy_hash, deploy_index = self.udtContract.get_deploy_hash_and_index()
        restart_cfg = {
            "ckb_rpc_url": self.node.rpcUrl,
            "ckb_udt_whitelist": True,
            "xudt_script_code_hash": self.Contract.get_ckb_contract_codehash(
                deploy_hash, deploy_index, True, self.node.rpcUrl
            ),
            "xudt_cell_deps_tx_hash": deploy_hash,
            "xudt_cell_deps_index": deploy_index,
            "fiber_announced_addrs": [wss_announced],
        }
        restart_cfg.update(self.start_fiber_config)
        self.fiber3.prepare(update_config=restart_cfg)
        self.fiber3.start(fnn_log_level=self.fnn_log_level)
        self.fiber1.connect_peer(self.fiber3)

        self.__class__.fiber4 = self.start_new_fiber(generate_account_privakey())
        self.fiber1.connect_peer(self.fiber4)

        self._wait_graph_sees_pubkeys(
            self.fiber2,
            {self.fiber3.get_pubkey(), self.fiber4.get_pubkey()},
            timeout=90,
        )

    def _wait_graph_sees_pubkeys(self, fiber, pubkeys: set, timeout: int = 90):
        deadline = time.time() + timeout
        need = set(pubkeys)
        while time.time() < deadline:
            nodes = fiber.get_client().graph_nodes().get("nodes") or []
            seen = {n["pubkey"] for n in nodes}
            if need.issubset(seen):
                return
            time.sleep(1)
        nodes = fiber.get_client().graph_nodes().get("nodes") or []
        raise AssertionError(
            f"timeout waiting graph on fiber2; need {need}, have "
            f"{ {n['pubkey'] for n in nodes} }"
        )

    def _disconnect_if_connected(self, client, pubkey: str):
        peers = client.list_peers().get("peers") or []
        for p in peers:
            if p.get("pubkey") == pubkey:
                client.disconnect_peer({"pubkey": pubkey})
                time.sleep(1)
                return

    def test_ws_addr_type_connects_over_ws(self):
        """fiber2 按 pubkey + addr_type=ws 连接 fiber3 后，list_peers 应显示 ws 多地址。"""
        self._disconnect_if_connected(
            self.fiber2.get_client(), self.fiber3.get_pubkey()
        )

        self.fiber2.get_client().connect_peer(
            {"pubkey": self.fiber3.get_pubkey(), "addr_type": "ws"}
        )
        time.sleep(2)

        peers = self.fiber2.get_client().list_peers()["peers"]
        match = [p for p in peers if p["pubkey"] == self.fiber3.get_pubkey()]
        assert len(match) == 1, peers
        dial_addr = match[0]["address"]
        assert "/ws" in dial_addr, dial_addr

    def test_wss_addr_type_errors_when_peer_has_no_wss_address(self):
        """fiber2 未通告 WSS 时，fiber4 使用 addr_type=wss 按 pubkey 连接应失败。"""
        with pytest.raises(Exception) as exc_info:
            self.fiber4.get_client().connect_peer(
                {"pubkey": self.fiber2.get_pubkey(), "addr_type": "wss"}
            )
        err = str(exc_info.value).lower()
        assert (
            "wss" in err
            or "address" in err
            or "transport" in err
            or "resolve" in err
            or "not found" in err
            or "match" in err
            or "error" in err
        ), str(exc_info.value)
