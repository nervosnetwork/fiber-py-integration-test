import time

from framework.basic_fiber_with_cch import FiberCchTest


class TestLongPath(FiberCchTest):
    debug = True

    def test_long_path(self):
        """Build a long Fiber path and validate LND->Fiber reachability per hop.

        Env:
            FIBER_CCH_LONG_PATH_HOPS: total Fiber nodes in the line topology (default: 10).
        """
        total_nodes = 7
        assert total_nodes >= 2, "FIBER_CCH_LONG_PATH_HOPS must be >= 2"

        udt_script = self.get_account_udt_script(self.fiber1.account_private)
        channel_balance = 300 * 100000000
        payment_amount = 100000

        # Ensure existing nodes have enough UDT to open/forward through many channels.
        self.faucet(
            self.fiber2.account_private,
            0,
            self.fiber1.account_private,
            2000 * 100000000,
        )

        fibers = [self.fiber1, self.fiber2]
        for _ in range(total_nodes - 2):
            account_private = self.generate_account(
                10000,
                self.fiber1.account_private,
                2000 * 100000000,
            )
            fibers.append(self.start_new_fiber(account_private))
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            5000 * 100000000,
        )
        # Build line topology: fiber1 -> fiber2 -> ... -> fiberN.
        for i in range(len(fibers) - 1):
            self.open_channel(
                fibers[i],
                fibers[i + 1],
                channel_balance,
                0,
                udt=udt_script,
            )

        # Validate increasing route depth: lnd -> fiber1(CCH) -> fiber2...fiberN.
        for index, payee in enumerate(fibers[1:], start=1):
            self.send_payment(self.fiber1, payee, 1, True, udt_script)
            invoice = payee.get_client().new_invoice(
                {
                    "amount": hex(payment_amount),
                    "currency": "Fibd",
                    "description": f"long-path-hop-{index}",
                    "udt_type_script": udt_script,
                    "payment_preimage": self.generate_random_preimage(),
                    "hash_algorithm": "sha256",
                }
            )
            print(f"current i:{index}")

            order = self.fiber1.get_client().receive_btc(
                {"fiber_pay_req": invoice["invoice_address"]}
            )
            self.LNDs[1].payinvoice(order["incoming_invoice"]["Lightning"])
            self.wait_cch_order_state(self.fiber1, order["payment_hash"], "Success", 30)
            final_order = self.fiber1.get_client().get_cch_order(
                {"payment_hash": order["payment_hash"]}
            )
            assert final_order["status"] == "Success"

    def test_send_btc_long_path(self):
        """Build a long LND path and validate Fiber->LND reachability per hop.

        send_btc flow: fiber2 --pays--> fiber1(CCH/LND0) --pays--> LND1 -> ... -> LNDM

        Extends the LND side with multiple nodes to test increasing LND hop depth.
        """
        total_lnd_nodes = 7
        assert total_lnd_nodes >= 2, "total_lnd_nodes must be >= 2"

        udt_script = self.get_account_udt_script(self.fiber1.account_private)
        payment_amount = 100

        # Fiber side: open UDT channel fiber2 -> fiber1 with enough liquidity.
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
            udt=udt_script,
        )

        # LND side: build line topology LND0 -> LND1 -> LND2 -> ... -> LNDM.
        # LND0 <-> LND1 already have channels from setup_class.
        lnds = [self.LNDs[0], self.LNDs[1]]
        for _ in range(total_lnd_nodes - 2):
            new_lnd = self.start_new_lnd()
            # Fund the previous LND so it can open a channel to the new one.
            self.faucetBtc(lnds[-1], 5)
            lnds[-1].open_channel(new_lnd, 1000000, 1, 0)
            self.btcNode.miner(6)
            lnds.append(new_lnd)

        # Validate increasing route depth on LND side:
        # fiber2 -> fiber1(CCH/LND0) -> LND1 -> ... -> LND[index].
        for index, payee_lnd in enumerate(lnds[1:], start=1):
            lnd_invoice = payee_lnd.addinvoice(payment_amount)

            # fiber1 (CCH) creates a send_btc order bridging Fiber -> LND.
            send_btc_response = self.fiber1.get_client().send_btc(
                {
                    "btc_pay_req": lnd_invoice["payment_request"],
                    "currency": "Fibd",
                }
            )
            print(f"send_btc long path - current LND hop depth: {index}")

            # fiber2 pays the Fiber invoice issued by fiber1 (CCH).
            payment = self.fiber2.get_client().send_payment(
                {"invoice": send_btc_response["incoming_invoice"]["Fiber"]}
            )

            # Wait for CCH order to complete end-to-end.
            self.wait_cch_order_state(
                self.fiber1, send_btc_response["payment_hash"], "Success", 60
            )
            final_order = self.fiber1.get_client().get_cch_order(
                {"payment_hash": send_btc_response["payment_hash"]}
            )
            assert final_order["status"] == "Success"

            # Verify the payee LND node received the payment.
            lnd_invoice_status = payee_lnd.ln_cli_with_cmd(
                f"lookupinvoice {lnd_invoice['r_hash']}"
            )
            assert lnd_invoice_status["state"] == "SETTLED"


    def test_tttttt(self):
        for i in range(5):
            self.start_new_mock_lnd()
        for i in range(1,6):
            invoice = self.LNDs[i].addinvoice(1000)
            self.LNDs[0].payinvoice(invoice['payment_request'])

    def test_bbbb(self):
        for i in range(5):
            self.start_new_mock_lnd()
        self.LNDs[2].addinvoice(1000)

    def test_start_mock(self):
        for i in range(5):
            self.start_new_mock_lnd()

        payee_lnd = self.LNDs[2]
        lnd_invoice = payee_lnd.addinvoice(100,"demo")

        # fiber1 (CCH) creates a send_btc order bridging Fiber -> LND.
        send_btc_response = self.fiber1.get_client().send_btc(
            {
                "btc_pay_req": lnd_invoice["payment_request"],
                "currency": "Fibd",
            }
        )
        print(f"send_btc long path - current LND hop depth: {2}")
        self.fiber2.get_client().parse_invoice(
            {"invoice": send_btc_response["incoming_invoice"]["Fiber"]}
        )
        # fiber2 pays the Fiber invoice issued by fiber1 (CCH).
        payment = self.fiber2.get_client().send_payment(
            {"invoice": send_btc_response["incoming_invoice"]["Fiber"]}
        )

        # Wait for CCH order to complete end-to-end.
        self.wait_cch_order_state(
            self.fiber1, send_btc_response["payment_hash"], "Success", 60
        )
        final_order = self.fiber1.get_client().get_cch_order(
            {"payment_hash": send_btc_response["payment_hash"]}
        )
        assert final_order["status"] == "Success"

        # Verify the payee LND node received the payment.
        lnd_invoice_status = payee_lnd.ln_cli_with_cmd(
            f"lookupinvoice {lnd_invoice['r_hash']}"
        )
        assert lnd_invoice_status["state"] == "SETTLED"


    def test_send_btc_long_path_max_hops(self):
        """Build a longer LND path for send_btc and only test from the farthest LND node.

        This validates that send_btc can traverse the maximum LND hop depth in a single shot.
        """
        total_lnd_nodes = 10
        assert total_lnd_nodes >= 2, "total_lnd_nodes must be >= 2"

        udt_script = self.get_account_udt_script(self.fiber1.account_private)
        payment_amount = 100000

        # Fiber side: open UDT channel fiber2 -> fiber1.
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
            udt=udt_script,
        )

        # LND side: build line topology LND0 -> LND1 -> ... -> LNDM.
        lnds = [self.LNDs[0], self.LNDs[1]]
        for _ in range(total_lnd_nodes - 2):
            new_lnd = self.start_new_lnd()
            self.faucetBtc(lnds[-1], 5)
            lnds[-1].open_channel(new_lnd, 1000000, 1, 0)
            self.btcNode.miner(6)
            lnds.append(new_lnd)

        # Only test the farthest LND node.
        farthest_lnd = lnds[-1]
        lnd_invoice = farthest_lnd.addinvoice(payment_amount)
        send_btc_response = self.fiber1.get_client().send_btc(
            {
                "btc_pay_req": lnd_invoice["payment_request"],
                "currency": "Fibd",
            }
        )
        print(
            f"send_btc max hops - payee is LND[{total_lnd_nodes - 1}], "
            f"LND hops={total_lnd_nodes - 1}"
        )

        # fiber2 pays the Fiber invoice.
        payment = self.fiber2.get_client().send_payment(
            {"invoice": send_btc_response["incoming_invoice"]["Fiber"]}
        )

        self.wait_cch_order_state(
            self.fiber1, send_btc_response["payment_hash"], "Success", 60
        )
        final_order = self.fiber1.get_client().get_cch_order(
            {"payment_hash": send_btc_response["payment_hash"]}
        )
        assert final_order["status"] == "Success"

        lnd_invoice_status = farthest_lnd.ln_cli_with_cmd(
            f"lookupinvoice {lnd_invoice['r_hash']}"
        )
        assert lnd_invoice_status["state"] == "SETTLED"

    def test_send_btc_long_path_both_sides(self):
        """Build long paths on both Fiber and LND sides for send_btc.

        Full path: fiberN -> ... -> fiber2 -> fiber1(CCH/LND0) -> LND1 -> ... -> LNDM

        Tests the maximum end-to-end hop count across both networks.
        """
        total_fiber_nodes = 5
        total_lnd_nodes = 5
        udt_script = self.get_account_udt_script(self.fiber1.account_private)
        channel_balance = 300 * 100000000
        payment_amount = 100000

        # --- Fiber side: build long path toward fiber1 (CCH hub) ---
        self.faucet(
            self.fiber2.account_private,
            0,
            self.fiber1.account_private,
            2000 * 100000000,
        )
        fibers = [self.fiber1, self.fiber2]
        for _ in range(total_fiber_nodes - 2):
            account_private = self.generate_account(
                10000,
                self.fiber1.account_private,
                2000 * 100000000,
            )
            fibers.append(self.start_new_fiber(account_private))
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            5000 * 100000000,
        )
        # fibers[i+1] opens channel to fibers[i] => outbound liquidity toward fiber1.
        for i in range(len(fibers) - 1):
            self.open_channel(
                fibers[i + 1],
                fibers[i],
                channel_balance,
                0,
                udt=udt_script,
            )

        # --- LND side: build long path from LND0 outward ---
        lnds = [self.LNDs[0], self.LNDs[1]]
        for _ in range(total_lnd_nodes - 2):
            new_lnd = self.start_new_lnd()
            self.faucetBtc(lnds[-1], 5)
            lnds[-1].open_channel(new_lnd, 1000000, 1, 0)
            self.btcNode.miner(6)
            lnds.append(new_lnd)

        # Warm up Fiber routing with a small keysend.
        farthest_fiber = fibers[-1]
        self.send_payment(farthest_fiber, self.fiber1, 1, True, udt_script)

        # Invoice on the farthest LND node.
        farthest_lnd = lnds[-1]
        lnd_invoice = farthest_lnd.addinvoice(payment_amount)
        send_btc_response = self.fiber1.get_client().send_btc(
            {
                "btc_pay_req": lnd_invoice["payment_request"],
                "currency": "Fibd",
            }
        )
        print(
            f"send_btc both sides - Fiber hops={total_fiber_nodes - 1}, "
            f"LND hops={total_lnd_nodes - 1}"
        )

        # Farthest Fiber node pays the Fiber invoice through the full path.
        payment = farthest_fiber.get_client().send_payment(
            {"invoice": send_btc_response["incoming_invoice"]["Fiber"]}
        )

        self.wait_cch_order_state(
            self.fiber1, send_btc_response["payment_hash"], "Success", 60
        )
        final_order = self.fiber1.get_client().get_cch_order(
            {"payment_hash": send_btc_response["payment_hash"]}
        )
        assert final_order["status"] == "Success"

        lnd_invoice_status = farthest_lnd.ln_cli_with_cmd(
            f"lookupinvoice {lnd_invoice['r_hash']}"
        )
        assert lnd_invoice_status["state"] == "SETTLED"

    def test_0000(self):
        for i in range(5):
            self.start_new_mock_fiber("")
        i = 4
        payee = self.fibers[i]
        udt_script = self.get_account_udt_script(self.fiber1.account_private)
        invoice = payee.get_client().new_invoice(
            {
                "amount": hex(10000),
                "currency": "Fibd",
                "description": f"long-path-hop-{i}",
                "udt_type_script": udt_script,
                "payment_preimage": self.generate_random_preimage(),
                "hash_algorithm": "sha256",
            }
        )

        # print(f"current i:{i}")
        #
        order = self.fiber1.get_client().receive_btc(
            {"fiber_pay_req": invoice["invoice_address"]}
        )
        self.LNDs[1].payinvoice(order["incoming_invoice"]["Lightning"])
        # self.send_payment(self.fiber1,self.fibers[6],1000,udt=udt_script)

    def test_0003(self):
        self.fiber1.get_client().get_payment({
            "payment_hash": "0xbb9960f03f3cd247e631db3dbef9a8e4014af9ac50decc89d8adc268c928a14a",
        })

    def test_0001(self):
        for i in range(5):
            self.start_new_mock_fiber("")
        udt_script = self.get_account_udt_script(self.fiber1.account_private)
        self.send_payment(self.fiber1, self.fibers[5], 100000000, udt=udt_script)

    def test_rrr(self):
        for i in range(5):
            self.start_new_mock_lnd()

        payee_lnd = self.LNDs[2]
        payee_lnd.ln_cli_with_cmd(f"decodepayreq lnbcrt1u1p5aelrfpp5x2kwr5s99wws9jtzyxpgl3kc5w8qrm4upvfn25vaag0yp9j7gycsdq8v3jk6mccqzzsxqyz5vqsp582ydrey9mrpu24zncgqkag5a2jmcl0m8vkm8h6wfz79th46n603q9qxpqysgqgljhpknv2mzfrge9lahdk4pzqj2tf7e4dhdg9kkddrxjnmvmkl5zzjurzjfjdwz6yfld3wqayt4srkczh8elu2cv4qrxsqz3f9upd5sqh459f7")
        #



    def test_rs(self):
        self.fiber1.stop()
        self.fiber1.start()