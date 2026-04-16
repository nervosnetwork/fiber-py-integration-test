# PR-1270: connect_peer 的 addr_type（ws / wss）

import time

import pytest

from framework.basic_share_fiber import SharedFiberTest
from framework.test_fiber import Fiber
from framework.util import generate_account_privakey


class TestPR1270ConnectPeerAddrType(SharedFiberTest):
    fiber3: Fiber
    fiber4: Fiber
    shared_fiber2_extra_config = {"fiber_reuse_port_for_websocket": False}

    def setUp(self):
        if getattr(TestPR1270ConnectPeerAddrType, "_done", False):
            return
        TestPR1270ConnectPeerAddrType._done = True

        self.__class__.fiber3 = self.start_new_fiber(generate_account_privakey())
        self.fiber1.connect_peer(self.fiber3)
        time.sleep(1)

        addr = self.fiber3.get_client().node_info()["addresses"][0]
        addr = addr.replace("0.0.0.0", "127.0.0.1").replace("0。0.0.0", "127.0.0.1")
        i = addr.index("/p2p/")
        wss_addr = addr[:i] + "/wss" + addr[i:]

        self.fiber3.stop()
        dh, di = self.udtContract.get_deploy_hash_and_index()
        cfg = {
            "ckb_rpc_url": self.node.rpcUrl,
            "ckb_udt_whitelist": True,
            "xudt_script_code_hash": self.Contract.get_ckb_contract_codehash(
                dh, di, True, self.node.rpcUrl
            ),
            "xudt_cell_deps_tx_hash": dh,
            "xudt_cell_deps_index": di,
            "fiber_announced_addrs": [wss_addr],
        }
        cfg.update(self.start_fiber_config)
        self.fiber3.prepare(update_config=cfg)
        self.fiber3.start(fnn_log_level=self.fnn_log_level)
        self.fiber1.connect_peer(self.fiber3)

        self.__class__.fiber4 = self.start_new_fiber(generate_account_privakey())
        self.fiber1.connect_peer(self.fiber4)

        pk3 = self.fiber3.get_pubkey()
        pk4 = self.fiber4.get_pubkey()
        for _ in range(90):
            nodes = self.fiber2.get_client().graph_nodes()["nodes"]
            pks = {n["pubkey"] for n in nodes}
            if pk3 in pks and pk4 in pks:
                break
            time.sleep(1)
        else:
            assert False, "graph_nodes 未同步到 fiber3/fiber4"

    def test_connect_pubkey_addr_type_ws_uses_ws_address(self):
        for p in self.fiber2.get_client().list_peers()["peers"]:
            if p["pubkey"] == self.fiber3.get_pubkey():
                self.fiber2.get_client().disconnect_peer({"pubkey": self.fiber3.get_pubkey()})
                time.sleep(1)
                break

        self.fiber2.get_client().connect_peer(
            {"pubkey": self.fiber3.get_pubkey(), "addr_type": "ws"}
        )
        time.sleep(2)

        for p in self.fiber2.get_client().list_peers()["peers"]:
            if p["pubkey"] == self.fiber3.get_pubkey():
                assert "/ws" in p["address"]
                return
        assert False, "未连上 fiber3"

    def test_connect_pubkey_addr_type_wss_fails_when_peer_has_no_wss(self):
        with pytest.raises(Exception):
            self.fiber4.get_client().connect_peer(
                {"pubkey": self.fiber2.get_pubkey(), "addr_type": "wss"}
            )
