import time

from framework.basic_fiber import FiberTest


class TestRestart(FiberTest):
    debug = True

    def test_node_restart(self):
        self.open_channel(self.fiber1,self.fiber2,1000 * 100000000,1000 * 100000000)
        self.open_channel(self.fiber1,self.fiber2,1000 * 100000000,1000 * 100000000)
        for j in range(100):
            for i in range(100):
                self.send_payment(self.fiber1, self.fiber2, 1, False)
                self.send_invoice_payment(self.fiber1, self.fiber2, 1, False)

                self.send_payment(self.fiber2, self.fiber1, 1, False)
                self.send_invoice_payment(self.fiber2, self.fiber1, 1, False)
            self.fiber1.stop()
            self.fiber1.start()
            time.sleep(10)
            self.send_payment(self.fiber1, self.fiber2, 1)
            self.send_invoice_payment(self.fiber1, self.fiber2, 1)

            self.send_payment(self.fiber2, self.fiber1, 1)
            self.send_invoice_payment(self.fiber2, self.fiber1, 1)

    def test_long_item1(self):
        self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        self.fiber4 = self.start_new_fiber(self.generate_account(10000))
        self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 1000 * 100000000,0,0)
        self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 1000 * 100000000,0,0)
        self.open_channel(self.fiber3, self.fiber4, 1000 * 100000000, 1000 * 100000000,0,0)
        self.open_channel(self.fiber4, self.fiber1, 1000 * 100000000, 1000 * 100000000,0,0)
        balances = self.get_fibers_balance_message()
        # for b in balances:
        #     print(b)

    def test_22213131(self):
        self.fiber3 = self.start_new_mock_fiber("")
        self.fiber4 = self.start_new_mock_fiber("")
        self.get_fibers_balance_message()
        # self.send_payment(self.fiber2, self.fiber1, 1)
        # self.fiber1.connect_peer(self.fiber2)
        # self.fiber2.connect_peer(self.fiber3)
        # self.fiber3.connect_peer(self.fiber4)
        # self.fiber4.connect_peer(self.fiber1)



    def test_long_item(self):
        self.fiber3 = self.start_new_mock_fiber("")
        self.fiber4 = self.start_new_mock_fiber("")

        # self.fiber3 = self.start_new_fiber(self.generate_account(10000))
        # self.fiber4 = self.start_new_fiber(self.generate_account(10000))
        #
        # self.open_channel(self.fiber1, self.fiber2, 1000 * 100000000, 1000 * 100000000)
        # self.open_channel(self.fiber2, self.fiber3, 1000 * 100000000, 1000 * 100000000)
        # self.open_channel(self.fiber3, self.fiber4, 1000 * 100000000, 1000 * 100000000)
        # self.open_channel(self.fiber4, self.fiber1, 1000 * 100000000, 1000 * 100000000)

        for j in range(1):
            for i in range(100):
                for fiber in self.fibers:
                    self.send_payment(fiber, fiber, 1, False)
                    self.send_invoice_payment(fiber, fiber, 1, False)
            self.fiber1.stop()
            self.fiber4.stop()
            self.fiber4.start()
            self.fiber1.start()
            time.sleep(10)
            for fiber in self.fibers:
                self.send_payment(fiber, fiber, 1, True)
                self.send_invoice_payment(fiber, fiber, 1, True)
            balances = self.get_fibers_balance()
            for balance in balances:
                assert balance['ckb'] == {'local_balance': 200000000000, 'offered_tlc_balance': 0, 'received_tlc_balance': 0}


    def test_000000(self):
        self.start_new_mock_fiber("")
        self.start_new_mock_fiber("")
        # for fiber in self.fibers:
        #     self.send_payment(fiber, fiber, 1)
        # self.get_fiber_graph_balance()

        #     fiber.stop()
        #     fiber.start()

        # self.send_payment(self.fiber2, self.fiber2, 1)
        balances = self.get_fibers_balance()
        for b in balances:
            print(b)