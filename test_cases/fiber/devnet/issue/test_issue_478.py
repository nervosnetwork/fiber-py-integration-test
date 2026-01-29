"""
Test for Fiber issue 478: graph_nodes with mixed fiber versions (testnet vs dev).
Ref: https://github.com/nervosnetwork/fiber/pull/478
"""
import time

from framework.basic_fiber import FiberTest
from framework.constants import Timeout
from framework.test_fiber import FiberConfigPath


class TestIssue478(FiberTest):
    """
    Test issue 478: start fiber3 (testnet) and fiber4 (dev), connect and call graph_nodes.
    """

    def test_issue_478(self):
        """
        Start two fibers with different versions (testnet vs dev), connect and query graph_nodes.
        Step 1: Start fiber3 (testnet) and fiber4 (dev) with funded accounts.
        Step 2: Connect fiber3 to fiber4 and call graph_nodes on both.
        """
        # Step 1: Start new fibers with different versions
        self.fiber3 = self.start_new_fiber(
            self.generate_account(10000),
            config=None,
            fiber_version=FiberConfigPath.CURRENT_TESTNET,
        )
        self.fiber4 = self.start_new_fiber(
            self.generate_account(10000),
            config=None,
            fiber_version=FiberConfigPath.CURRENT_DEV,
        )

        # Step 2: Connect and query graph_nodes
        self.fiber3.connect_peer(self.fiber4)
        time.sleep(Timeout.POLL_INTERVAL * 2)
        self.fiber3.get_client().graph_nodes({})
        self.fiber4.get_client().graph_nodes({})
