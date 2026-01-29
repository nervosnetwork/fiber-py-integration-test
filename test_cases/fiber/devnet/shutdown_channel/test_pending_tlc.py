"""
Test cases for shutdown_channel with pending TLC (add_tlc / remove_tlc scenarios).
Scenario: channel with pending TLCs; shutdown with force or cooperative close. Currently disabled.
"""
import pytest

from framework.basic_fiber import FiberTest


class TestPendingTlc(FiberTest):
    """
    Test shutdown_channel when channel has pending TLCs (add_tlc, remove_tlc, force close).
    Test body commented out; re-enable when scenario is restored.
    """

    @pytest.mark.skip("Scenario commented out; restore when re-enabled")
    def test_pending_tlc_shutdown(self):
        """
        Placeholder: pending TLC shutdown scenario (commented out).
        Step 1: (When enabled) Open channel, add TLC, shutdown with force or cooperative.
        Step 2: (When enabled) Assert close tx and TLC handling.
        """
        pass
