"""
Test cases for CKB node stop: multiple open_channel while CKB node is running, then stop CKB and verify fiber node_info.
"""
from framework.basic_fiber import FiberTest
from framework.constants import Amount


class CkbStopTest(FiberTest):
    """
    Test CKB node stop: repeatedly open channel, stop CKB node, then call fiber node_info.
    """

    def test_stop(self):
        """
        Open channel multiple times, stop CKB node, then call node_info on both fibers.
        Step 1: Loop open_channel (fiber1-fiber2) 10 times.
        Step 2: Stop CKB node.
        Step 3: Call node_info on fiber1 and fiber2.
        """
        # Step 1: Loop open_channel 10 times
        for i in range(10):
            self.open_channel(
                self.fiber1, self.fiber2,
                Amount.ckb(1000),
                0,
            )
        # Step 2: Stop CKB node
        self.node.stop()
        # Step 3: Call node_info on both fibers
        self.fiber1.get_client().node_info()
        self.fiber2.get_client().node_info()

    def test_balala(self):
        """Call node_info on fiber1 (CKB may be stopped)."""
        self.fiber1.get_client().node_info()
