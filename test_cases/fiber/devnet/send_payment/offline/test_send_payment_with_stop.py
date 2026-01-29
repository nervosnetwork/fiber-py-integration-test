"""
Test cases for send_payment with node stop during payment.
Intended scenarios: send multiple payments without wait, stop nodes, verify behavior.
"""
import pytest

from framework.basic_fiber import FiberTest


class TestSendPaymentWithStop(FiberTest):
    """
    Test send_payment behavior when nodes are stopped during payment.
    Original tests were commented out; placeholder kept for future implementation.
    """

    @pytest.mark.skip("Tests under development - original implementation commented out")
    def test_placeholder_send_payment_with_stop(self):
        """
        Placeholder for send_payment with stop scenarios.
        Step 1: (Intended) Build multi-hop topology.
        Step 2: (Intended) Send payments without wait.
        Step 3: (Intended) Stop sender/receiver nodes and verify.
        """
        pass
