import time

import pytest

from framework.basic_fiber_with_cch import FiberCchTest


class TestCCHExpiryDeltaSeconds(FiberCchTest):
    """
    https://github.com/nervosnetwork/fiber/issues/1216
        Currently, when a CCH order expires due to expiry_delta_seconds in Fiber, only the order itself is marked as failed (CchOrder.status = Failed), but the associated incoming_invoice is not cleaned up. In business reality, if an expired order is failed but the incoming_invoice is not cancelled/failed, it can cause:

        Pending TLC or hold invoice resources remain locked
        Cooperative channel shutdown or Watchtower processes can be blocked
        Users may mistakenly attempt payments to invalid orders
        Suggested improvements:

        Add a CancelIncomingInvoice action, symmetric with the existing SettleIncomingInvoice
        When an order enters the Failed status, proactively trigger cancel/cleanup behavior for the incoming_invoice, covering both Fiber and Lightning types
        The scheduler expire_order logic should ideally route through the actor/state machine to ensure dispatcher actions can always be triggered (rather than a direct store update)
        Supplement integration tests to verify that after order expiry, incoming_invoice is appropriately cancelled/released
        Relevant code modules:

        crates/fiber-lib/src/cch/actions/mod.rs
        crates/fiber-lib/src/cch/actions/cancel_incoming_invoice.rs (recommended new module)
        scheduler / actor / state machine logic
        Improving this cleanup mechanism will ensure consistency on failed paths and more robust resource handling.


    """

    def _restart_fiber1_with_expiry(self, expiry_seconds):
        self.fiber1.stop()
        self.fiber1.prepare(
            {
                "cch": True,
                "cch_lnd_cert_path": f"{self.LNDs[0].tmp_path}/tls.cert",
                "cch_lnd_rpc_url": f"https://localhost:{self.LNDs[0].rpc_port}",
                "cch_order_expiry_delta_seconds": expiry_seconds,
            }
        )
        self.fiber1.start()

    def _wait_cch_order_failed(self, payment_hash, timeout):
        start = time.time()
        while time.time() - start < timeout:
            order = self.fiber1.get_client().get_cch_order(
                {"payment_hash": payment_hash}
            )
            if str(order["status"]).lower() == "failed":
                return order, time.time() - start
            time.sleep(1)
        raise TimeoutError(
            f"CCH order {payment_hash} did not become Failed in {timeout}s"
        )

    def _create_receive_btc_order(self):
        invoice = self.fiber2.get_client().new_invoice(
            {
                "amount": hex(1000),
                "currency": "Fibd",
                "description": "test cch order expiry",
                "udt_type_script": self.get_account_udt_script(
                    self.fiber1.account_private
                ),
                "payment_preimage": self.generate_random_preimage(),
                "hash_algorithm": "sha256",
            }
        )
        return self.fiber1.get_client().receive_btc(
            {
                "fiber_pay_req": invoice["invoice_address"],
            }
        )

    def test_order_expiry_delta_seconds_should_mark_order_failed(self):
        expiry_seconds = 10
        self._restart_fiber1_with_expiry(expiry_seconds)

        with open(self.fiber1.fiber_config_path, "r") as f:
            config_text = f.read()
        assert f"order_expiry_delta_seconds: {expiry_seconds}" in config_text

        receive_btc_result = self._create_receive_btc_order()
        payment_hash = receive_btc_result["payment_hash"]
        order = self.fiber1.get_client().get_cch_order({"payment_hash": payment_hash})

        assert "expiry_delta_seconds" in order
        actual_expiry = order["expiry_delta_seconds"]
        if isinstance(actual_expiry, str):
            actual_expiry = int(actual_expiry, 16)
        assert actual_expiry == expiry_seconds

        order, elapsed = self._wait_cch_order_failed(
            payment_hash=payment_hash,
            timeout=expiry_seconds + 30,
        )
        assert str(order["status"]).lower() == "failed"
        assert elapsed >= expiry_seconds - 1

    @pytest.mark.xfail(
        reason=(
            "Known gap: expired CCH order does not cancel associated incoming Lightning invoice yet"
        ),
        strict=False,
    )
    def test_expired_order_should_cancel_incoming_lightning_invoice(self):
        expiry_seconds = 10
        self._restart_fiber1_with_expiry(expiry_seconds)

        receive_btc_result = self._create_receive_btc_order()
        payment_hash = receive_btc_result["payment_hash"]

        self._wait_cch_order_failed(
            payment_hash=payment_hash, timeout=expiry_seconds + 30
        )
        lnd_invoice = self.LNDs[0].ln_cli_with_cmd(
            f"lookupinvoice {payment_hash.replace('0x', '')}"
        )
        assert lnd_invoice["state"] == "CANCELED"

    @pytest.mark.skip("https://github.com/nervosnetwork/fiber/issues/1216")
    def test_expired_order_should_cancel_incoming_fiber_invoice(self):

        expiry_seconds = 20
        self._restart_fiber1_with_expiry(expiry_seconds)
        self.faucet(
            self.fiber2.account_private,
            0,
            self.fiber1.account_private,
            10000 * 100000000,
        )
        self.open_channel(
            self.fiber2,
            self.fiber1,
            1000 * 100000000,
            1000 * 100000000,
            udt=self.get_account_udt_script(self.fiber1.account_private),
        )
        lndInvoice = self.LNDs[1].addholdinvoice(
            self.generate_random_preimage().replace("0x", ""),
            1000,
            "demo",
        )
        btc_response = self.fiber1.get_client().send_btc(
            {
                "btc_pay_req": lndInvoice["payment_request"],
                "currency": "Fibd",
            }
        )
        payment = self.fiber2.get_client().send_payment(
            {"invoice": btc_response["incoming_invoice"]["Fiber"]}
        )
        self.wait_payment_state(self.fiber2, payment["payment_hash"], "Inflight")
        self.wait_cch_order_state(
            self.fiber1, payment["payment_hash"], "OutgoingInFlight"
        )
        self.LNDs[1].ln_cli_with_cmd(
            f"cancelinvoice {payment["payment_hash"].replace('0x', '')}"
        )
        self.wait_cch_order_state(self.fiber1, payment["payment_hash"], "Failed")
        self.wait_payment_state(self.fiber2, payment["payment_hash"], "Failed")
