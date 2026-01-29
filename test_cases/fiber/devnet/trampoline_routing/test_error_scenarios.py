"""
Trampoline routing error scenarios: insufficient balance, capacity, no path,
max_fee_amount too low, duplicate/target/empty trampoline_hops.
"""

import pytest

from framework.basic_fiber import FiberTest
from framework.constants import Amount, Currency, PaymentStatus, Timeout


class TestErrorScenarios(FiberTest):
    """
    Trampoline routing error cases: insufficient balance, channel capacity,
    no path to trampoline or to target, max_fee_amount too low,
    duplicate/target-in/empty trampoline_hops.
    """

    def test_insufficient_balance(self):
        """
        Send amount exceeding path capacity; expect no path / failure.
        Step 1: Create fiber3; open channels with 1000 CKB each.
        Step 2: Keysend 2000 CKB via trampoline; assert error.
        """
        # Step 1: Create fiber3; open channels
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Keysend 2000 CKB; assert error
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "currency": Currency.FIBD,
                    "amount": hex(Amount.ckb(2000)),
                    "keysend": True,
                    "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
                }
            )
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert "no path found" in err or "Failed" in str(exc_info.value)

    def test_channel_capacity_insufficient(self):
        """
        First payment consumes capacity; second may exceed remaining; expect failure when insufficient.
        Step 1: Create fiber3..4; open 50 CKB channels.
        Step 2: Send 30 CKB; wait success.
        Step 3: Send another 30 CKB; expect exception or failure.
        """
        # Step 1: Create fiber3..4; open 50 CKB channels
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(50), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(50), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber3, self.fiber4,
            fiber1_balance=Amount.ckb(50), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Send 30 CKB; wait success
        payment1 = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(30)),
                "keysend": True,
                "trampoline_hops": [
                    self.fiber2.get_client().node_info()["node_id"],
                    self.fiber3.get_client().node_info()["node_id"],
                ],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment1["payment_hash"], PaymentStatus.SUCCESS,
            timeout=Timeout.PAYMENT_SUCCESS,
        )

        # Step 3: Send another 30 CKB; expect exception
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                    "currency": Currency.FIBD,
                    "amount": hex(Amount.ckb(30)),
                    "keysend": True,
                    "trampoline_hops": [
                        self.fiber2.get_client().node_info()["node_id"],
                        self.fiber3.get_client().node_info()["node_id"],
                    ],
                }
            )
        err = exc_info.value.args[0] if exc_info.value.args else ""
        assert "no path found" in err or "Failed" in str(exc_info.value)

    def test_no_path_to_trampoline(self):
        """
        No channel from source to trampoline; expect no path.
        Step 1: Open f2-f3, f3-f4 only (f1 not connected to f2).
        Step 2: Keysend via trampoline f2; assert error.
        """
        # Step 1: Open f2-f3, f3-f4 only
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber3, self.fiber4,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Keysend via trampoline f2; assert error
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                    "currency": Currency.FIBD,
                    "amount": hex(Amount.ckb(1)),
                    "keysend": True,
                    "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
                }
            )
        expected = "no path found"
        assert expected in (exc_info.value.args[0] if exc_info.value.args else ""), (
            f"Expected '{expected}' in error."
        )

    def test_no_path_from_trampoline_to_target(self):
        """
        Trampoline has no path to target; payment should fail.
        Step 1: Open f1-f2 only; f2 has no channel to f4.
        Step 2: Keysend via trampoline f2 to f4; wait Failed.
        """
        # Step 1: Open f1-f2 only
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))

        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Keysend via trampoline f2 to f4; wait Failed
        payment = self.fiber1.get_client().send_payment(
            {
                "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
                "currency": Currency.FIBD,
                "amount": hex(Amount.ckb(1)),
                "keysend": True,
                "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
            }
        )
        self.wait_payment_state(
            self.fiber1, payment["payment_hash"], PaymentStatus.FAILED,
            timeout=Timeout.PAYMENT_SUCCESS,
        )

    def test_max_fee_amount_too_low(self):
        """
        max_fee_amount=1; expect error.
        Step 1: Create fiber3; open channels.
        Step 2: Keysend with max_fee_amount=1; assert error.
        """
        # Step 1: Create fiber3; open channels
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Keysend with max_fee_amount=1; assert error
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "currency": Currency.FIBD,
                    "amount": hex(Amount.ckb(1)),
                    "keysend": True,
                    "max_fee_amount": hex(1),
                    "trampoline_hops": [self.fiber2.get_client().node_info()["node_id"]],
                }
            )
        expected = "max_fee_amount is too low"
        assert expected in (exc_info.value.args[0] if exc_info.value.args else ""), (
            f"Expected '{expected}' in error."
        )

    def test_duplicate_trampoline_hops(self):
        """
        Duplicate trampoline hop; expect error.
        Step 1: Create fiber3; open channels.
        Step 2: Keysend with duplicate hop; assert error.
        """
        # Step 1: Create fiber3; open channels
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Keysend with duplicate hop; assert error
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "currency": Currency.FIBD,
                    "amount": hex(Amount.ckb(1)),
                    "keysend": True,
                    "trampoline_hops": [
                        self.fiber2.get_client().node_info()["node_id"],
                        self.fiber2.get_client().node_info()["node_id"],
                    ],
                }
            )
        err = (exc_info.value.args[0] if exc_info.value.args else "").lower()
        assert "duplicate" in err or "Failed" in str(exc_info.value)

    def test_target_in_trampoline_hops(self):
        """
        Target in trampoline_hops; expect error.
        Step 1: Create fiber3; open channels.
        Step 2: Keysend with target in trampoline_hops; assert error.
        """
        # Step 1: Create fiber3; open channels
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Keysend with target in trampoline_hops; assert error
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "currency": Currency.FIBD,
                    "amount": hex(Amount.ckb(1)),
                    "keysend": True,
                    "trampoline_hops": [
                        self.fiber2.get_client().node_info()["node_id"],
                        self.fiber3.get_client().node_info()["node_id"],
                    ],
                }
            )
        err = (exc_info.value.args[0] if exc_info.value.args else "").lower()
        assert "target_pubkey" in err or "Failed" in str(exc_info.value)

    def test_empty_trampoline_hops(self):
        """
        Empty trampoline_hops; expect error.
        Step 1: Create fiber3; open channels.
        Step 2: Keysend with trampoline_hops=[]; assert error.
        """
        # Step 1: Create fiber3; open channels
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(
            self.fiber1, self.fiber2,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )
        self.open_channel(
            self.fiber2, self.fiber3,
            fiber1_balance=Amount.ckb(1000), fiber2_balance=Amount.ckb(0),
        )

        # Step 2: Keysend with trampoline_hops=[]; assert error
        with pytest.raises(Exception) as exc_info:
            self.fiber1.get_client().send_payment(
                {
                    "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
                    "currency": Currency.FIBD,
                    "amount": hex(Amount.ckb(1)),
                    "keysend": True,
                    "trampoline_hops": [],
                }
            )
        err = (exc_info.value.args[0] if exc_info.value.args else "").lower()
        assert "empty" in err or "Failed" in str(exc_info.value)
