"""
Test cases for node backup and restore: stop node, replace/restore data, restart and verify payment.
"""
import shutil
import time

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Timeout


class TestBackup(FiberTest):
    """
    Test backup/restore scenarios: stop node then change listening addr and restart;
    copy data while node running then restore after stop and verify send_payment.
    """

    def test_backup(self):
        """
        Stop node, change listening address, restart and verify graph + send_payment.
        Step 1: Open channel between fiber1 and fiber2.
        Step 2: Record graph_nodes from fiber2.
        Step 3: Stop fiber1, change listening addr, start and connect.
        Step 4: Wait for sync then send payment.
        Step 5: Assert fiber2 graph addresses match fiber1 node_info addresses.
        """
        # Step 1: Open channel between fiber1 and fiber2
        self.open_channel(
            self.fiber1, self.fiber2,
            Amount.ckb(1000),
            Amount.ckb(1),
        )
        # Step 2: Record graph_nodes from fiber2
        before_graph_nodes = self.fiber2.get_client().graph_nodes()
        # Step 3: Stop fiber1, change listening addr, start and connect
        self.fiber1.stop()
        self.fiber1.prepare({"fiber_listening_addr": "/ip4/127.0.0.1/tcp/8238"})
        self.fiber1.start()
        self.fiber1.connect_peer(self.fiber2)
        time.sleep(Timeout.POLL_INTERVAL * 5)
        # Step 4: Send payment after restart
        self.send_payment(self.fiber1, self.fiber2, Amount.ckb(1))
        # Step 5: Assert fiber2 graph addresses match fiber1 node_info addresses
        after_graph_nodes = self.fiber2.get_client().graph_nodes()
        assert (
            after_graph_nodes["nodes"][1]["addresses"]
            == self.fiber1.get_client().node_info()["addresses"]
        ), "Graph node addresses should match restarted node"

    def test_backup2(self):
        """
        Backup data while node is running, then restore after stop and verify send_payment.
        Step 1: Open channel between fiber1 and fiber2.
        Step 2: Copy fiber data dir to backup (node still running).
        Step 3: Stop fiber1, remove data, restore from backup, start and connect.
        Step 4: Wait then send payment to verify state restored.
        """
        # Step 1: Open channel between fiber1 and fiber2
        self.open_channel(
            self.fiber1, self.fiber2,
            Amount.ckb(1000),
            Amount.ckb(1),
        )
        # Step 2: Copy fiber data dir to backup (node still running)
        shutil.copytree(
            f"{self.fiber1.tmp_path}/fiber", f"{self.fiber1.tmp_path}/fiber.bak"
        )
        # Step 3: Stop fiber1, remove data, restore from backup, start and connect
        self.fiber1.stop()
        shutil.rmtree(f"{self.fiber1.tmp_path}/fiber")
        shutil.copytree(
            f"{self.fiber1.tmp_path}/fiber.bak", f"{self.fiber1.tmp_path}/fiber"
        )
        self.fiber1.start()
        self.fiber1.connect_peer(self.fiber2)
        time.sleep(Timeout.POLL_INTERVAL * 5)
        # Step 4: Send payment to verify state restored
        self.send_payment(self.fiber1, self.fiber2, Amount.ckb(1))

    @pytest.mark.skip("restart: list_peers empty after restart, unstable")
    def test_backup3(self):
        """
        Restart with new password and verify list_peers and send_payment (skipped: unstable).
        Step 1: Open channel, stop, prepare new addr, start with new password.
        Step 2: Send payment, stop, start again, check list_peers.
        Step 3: Connect peer and send payment.
        """
        # Step 1: Open channel, stop, prepare new addr, start with new password
        self.open_channel(
            self.fiber1, self.fiber2,
            Amount.ckb(1000),
            Amount.ckb(1),
        )
        self.fiber1.stop()
        self.fiber1.prepare({"fiber_listening_addr": "/ip4/127.0.0.1/tcp/8238"})
        self.fiber1.start("newPassword2")
        time.sleep(Timeout.POLL_INTERVAL * 5)
        self.send_payment(self.fiber1, self.fiber2, Amount.ckb(1))
        self.fiber1.stop()
        self.fiber1.start("newPassword2")
        time.sleep(Timeout.POLL_INTERVAL * 5)
        # Step 2: Check list_peers (may be empty after restart)
        peers = self.fiber1.get_client().list_peers()
        self.fiber1.stop()
        self.fiber1.start("newPassword2")
        self.fiber1.connect_peer(self.fiber2)
        time.sleep(Timeout.VERY_SHORT)
        peers = self.fiber1.get_client().list_peers()
        assert len(peers["peers"]) > 0, "Expect at least one peer after connect"
        # Step 3: Send payment
        self.send_payment(self.fiber1, self.fiber2, Amount.ckb(1))
