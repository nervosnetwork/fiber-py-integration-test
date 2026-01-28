"""
Trampoline routing tests: new_invoice allow_trampoline_routing None/False/True and attrs.
"""

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Currency, HashAlgorithm


class TestNewInvoice(FiberTest):
    """
    new_invoice allow_trampoline_routing: None (no TRAMPOLINE_ROUTING_OPTIONAL in attrs),
    False (same), True (TRAMPOLINE_ROUTING_OPTIONAL in attrs). node_info has TRAMPOLINE_ROUTING_REQUIRED.
    """

    def test_new_invoice(self):
        """
        Assert node_info has TRAMPOLINE_ROUTING_REQUIRED; new_invoice None/False/True
        and attrs contain or not TRAMPOLINE_ROUTING_OPTIONAL.
        Step 1: node_info; new_invoice allow_trampoline_routing=None; assert attrs lack OPTIONAL.
        Step 2: new_invoice allow_trampoline_routing=False; assert attrs lack OPTIONAL.
        Step 3: new_invoice allow_trampoline_routing=True; assert attrs contain OPTIONAL.
        """
        # Step 1: node_info; new_invoice allow_trampoline_routing=None; assert attrs lack OPTIONAL
        node_info = self.fiber1.get_client().node_info()
        allow_none = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(1),
                "currency": Currency.FIBD,
                "description": "test invoice",
                "payment_preimage": self.generate_random_preimage(),
                "hash_algorithm": HashAlgorithm.SHA256,
            }
        )
        assert "TRAMPOLINE_ROUTING_REQUIRED" in node_info["features"]
        assert "TRAMPOLINE_ROUTING_OPTIONAL" not in str(
            allow_none["invoice"]["data"]["attrs"]
        )

        # Step 2: new_invoice allow_trampoline_routing=False; assert attrs lack OPTIONAL
        allow_false = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(1),
                "currency": Currency.FIBD,
                "description": "test invoice",
                "payment_preimage": self.generate_random_preimage(),
                "hash_algorithm": HashAlgorithm.SHA256,
                "allow_trampoline_routing": False,
            }
        )
        assert "TRAMPOLINE_ROUTING_OPTIONAL" not in str(
            allow_false["invoice"]["data"]["attrs"]
        )

        # Step 3: new_invoice allow_trampoline_routing=True; assert attrs contain OPTIONAL
        allow_true = self.fiber1.get_client().new_invoice(
            {
                "amount": hex(1),
                "currency": Currency.FIBD,
                "description": "test invoice",
                "payment_preimage": self.generate_random_preimage(),
                "hash_algorithm": HashAlgorithm.SHA256,
                "allow_trampoline_routing": True,
            }
        )
        assert "TRAMPOLINE_ROUTING_OPTIONAL" in str(
            allow_true["invoice"]["data"]["attrs"]
        )
