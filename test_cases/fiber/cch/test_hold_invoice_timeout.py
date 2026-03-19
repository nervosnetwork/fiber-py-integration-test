import time

import pytest

from framework.basic_fiber_with_cch import FiberCchTest
from test_cases.fiber.devnet.settle_invoice.test_settle_invoice import sha256_hex


class HoldInvoiceTimeout(FiberCchTest):

    # @pytest.mark.skip("https://github.com/nervosnetwork/fiber/issues/1029")
    def test_0000(self):
        """

        Returns:

        """
        self.fiber1.stop()
        self.fiber1.prepare(
            {
                "cch": True,
                "cch_lnd_cert_path": f"{self.LNDs[0].tmp_path}/tls.cert",
                "cch_lnd_rpc_url": f"https://localhost:{self.LNDs[0].rpc_port}",
                "cch_min_outgoing_invoice_expiry_delta_seconds": 1,
            }
        )
        self.fiber1.start()
        # # lnd new hold invoice
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
        preimage = self.generate_random_preimage()
        payment_hash = sha256_hex(preimage)
        lndInvoice = self.LNDs[1].addholdinvoice(
            payment_hash.replace("0x", ""), 1000, "demo  --expiry 20"
        )
        payreq = self.LNDs[0].ln_cli_with_cmd(
            f"decodepayreq {lndInvoice["payment_request"]}",
        )
        print("payreq:", payreq)
        # lndInvoice = self.LNDs[0].addinvoice(1000000 * 10000000)
        send_payment_response = self.fiber1.get_client().send_btc(
            {
                "btc_pay_req": lndInvoice["payment_request"],
                "currency": "Fibd",
            }
        )
        invoice = self.fiber2.get_client().parse_invoice(
            {"invoice": send_payment_response["incoming_invoice"]["Fiber"]}
        )
        print("invoice:", invoice)
        payment = self.fiber2.get_client().send_payment(
            {"invoice": send_payment_response["incoming_invoice"]["Fiber"]}
        )
        time.sleep(30)
        # settle invoice
        self.LNDs[1].ln_cli_with_cmd(f"settleinvoice {preimage.replace('0x', '')}")
        time.sleep(1)
        invoice = self.LNDs[1].ln_cli_with_cmd(
            f"lookupinvoice {payment_hash.replace("0x", "")}"
        )
        assert invoice["state"] == "SETTLED"
        time.sleep(5)
        order = self.fiber1.get_client().get_cch_order({"payment_hash": payment_hash})
        assert order["status"] == "Succeeded"
