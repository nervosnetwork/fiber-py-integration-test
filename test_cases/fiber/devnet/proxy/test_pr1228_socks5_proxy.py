"""
PR #1228: SOCKS5 / Tor proxy for outbound Fiber P2P.

Requires an fnn binary built with proxy support (see nervosnetwork/fiber#1228).
https://github.com/nervosnetwork/fiber/pull/1228
"""

import os
import time

from framework.basic_fiber import FiberTest
from framework.socks5_local_server import LocalSocks5Server


class TestPR1228Socks5Proxy(FiberTest):
    """Outbound P2P through a local SOCKS5 relay."""

    def _base_fiber_update_config(self):
        deploy_hash, deploy_index = self.udtContract.get_deploy_hash_and_index()
        return {
            "ckb_rpc_url": self.node.rpcUrl,
            "ckb_udt_whitelist": True,
            "xudt_script_code_hash": self.Contract.get_ckb_contract_codehash(
                deploy_hash, deploy_index, True, self.node.rpcUrl
            ),
            "xudt_cell_deps_tx_hash": deploy_hash,
            "xudt_cell_deps_index": deploy_index,
        }

    def _wait_peer(self, client, remote_pubkey: str, timeout: float = 45.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            peers = client.list_peers().get("peers") or []
            for p in peers:
                if p.get("pubkey") == remote_pubkey:
                    return
            time.sleep(0.5)
        raise AssertionError(
            f"peer {remote_pubkey} not listed before timeout ({timeout}s)"
        )

    def _fiber2_dial_address(self) -> str:
        addr = self.fiber2.get_client().node_info()["addresses"][0]
        return addr.replace("0.0.0.0", "127.0.0.1").replace("0。0.0.0", "127.0.0.1")

    def test_outbound_p2p_via_socks5_proxy(self):
        """
        Third node uses fiber.proxy.proxy_url; connects to fiber2. Asserts:
        - peer relationship is established
        - SOCKS5 server saw at least one successful CONNECT
        - node log mentions tcp_proxy_config (fnn with PR #1228)
        """
        socks = LocalSocks5Server()
        socks.start()
        assert socks.port is not None
        try:
            account = self.generate_account(10000)
            cfg = self._base_fiber_update_config()
            cfg["fiber_proxy_url"] = f"socks5://127.0.0.1:{socks.port}"
            cfg["fiber_proxy_random_auth"] = True

            fiber3 = self.start_new_fiber(account, config=cfg)
            time.sleep(2)
            fiber3.get_client().connect_peer({"address": self._fiber2_dial_address()})
            self._wait_peer(self.fiber2.get_client(), fiber3.get_pubkey(), timeout=60.0)

            assert (
                socks.stats.get("connects", 0) >= 1
            ), "expected at least one SOCKS5 CONNECT (P2P via proxy)"

            log_path = os.path.join(fiber3.tmp_path, "node.log")
            with open(log_path, "r", errors="replace") as f:
                log_text = f.read()
            assert "tcp_proxy_config" in log_text, (
                "fnn log should record SOCKS5 proxy; "
                "if this fails on an older binary, upgrade fnn to a build that includes PR #1228"
            )
        finally:
            socks.stop()

    def test_socks5_proxy_without_random_auth(self):
        """Same as above with proxy_random_auth disabled (NO_AUTH path)."""
        socks = LocalSocks5Server()
        socks.start()
        try:
            account = self.generate_account(10000)
            cfg = self._base_fiber_update_config()
            cfg["fiber_proxy_url"] = f"socks5://127.0.0.1:{socks.port}"
            cfg["fiber_proxy_random_auth"] = False

            fiber3 = self.start_new_fiber(account, config=cfg)
            time.sleep(2)
            fiber3.get_client().connect_peer({"address": self._fiber2_dial_address()})
            self._wait_peer(self.fiber2.get_client(), fiber3.get_pubkey(), timeout=60.0)
            assert socks.stats.get("connects", 0) >= 1
        finally:
            socks.stop()


# Tor / hidden-service scenarios need a real tor daemon (ControlPort + SOCKS).
# See PR #1228 and config keys: listen_on_onion, onion_server, tor_controller, etc.
