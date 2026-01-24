# import pytest
#
# from framework.basic_fiber import FiberTest
# from framework.basic_share_fiber import SharedFiberTest
# from framework.test_fiber import Fiber
#
#
# class TestFeeRate(FiberTest):
#     # setup_method_only_once = True
#     N = 2
#     # 0-》1-》2-》3-》4
#     # 0-》5 -》4
#     # 0 -》6 -》5 -》4
#     # debug = True
#     fiber3: Fiber
#     fiber4: Fiber
#
#     # fiber5: Fiber
#     # fiber6: Fiber
#     # fiber7: Fiber
#     # fiber8: Fiber
#
#     # 建立N个节点
#     def init(self):
#         # for i in range(2):
#         self.fiber3 = self.start_new_fiber(self.generate_account(10000))
#         self.fiber4 = self.start_new_fiber(self.generate_account(10000))
#
#         for i in range(3):
#             self.open_channel(
#                 self.fibers[i], self.fibers[(i + 1)], 1000 * 100000000, 1000 * 100000000
#             )
#             self.open_channel(
#                 self.fibers[i],
#                 self.fibers[(i + 1)],
#                 1000 * 100000000,
#                 1000 * 100000000,
#                 other_config={
#                     "public": False,
#                     "one_way": True,
#                 },
#             )
#
#     def test_fee_rate_too_bigger(self):
#         """
#         fee rate 设置特别大会怎么样
#         fee_rate设置特别大，有没有溢出的可能
#         Returns:
#         """
#         self.init()
#         before_balance = self.get_fibers_balance()
#         with pytest.raises(Exception) as exc_info:
#             payment = self.fiber1.get_client().send_payment(
#                 {
#                     "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
#                     "currency": "Fibd",
#                     "amount": hex(1 * 100000000),
#                     "keysend": True,
#                     "trampoline_hops": [
#                         {
#                             "pubkey": self.fiber2.get_client().node_info()["node_id"],
#                             "fee_rate": hex((1 << 64) - 1),
#                         }
#                     ],
#                 }
#             )
#         expected_error_message = "no path found"
#         assert expected_error_message in exc_info.value.args[0], (
#             f"Expected substring '{expected_error_message}' "
#             f"not found in actual string '{exc_info.value.args[0]}'"
#         )
#
#         # self.wait_payment_state(self.fiber1, payment['payment_hash'], "Success")
#         # after_balance = self.get_fibers_balance()
#         # diff_balance = self.get_channel_balance_change(before_balance, after_balance)
#         # print("diff_balance", diff_balance)
#         # # print("before_balance", before_balance)
#         # # print("after_balance", after_balance)
#
#     def test_trampoline_hops_contains_target_pubkey(self):
#         self.init()
#         with pytest.raises(Exception) as exc_info:
#             self.fiber1.get_client().send_payment(
#                 {
#                     "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
#                     "currency": "Fibd",
#                     "amount": hex(1 * 100000000),
#                     "keysend": True,
#                     "trampoline_hops": [
#                         {
#                             "pubkey": self.fiber2.get_client().node_info()["node_id"],
#                             # "fee_rate": hex(1000),
#                         },
#                         {
#                             "pubkey": self.fiber3.get_client().node_info()["node_id"],
#                             "fee_rate": hex(1000),
#                         },
#                     ],
#                 }
#             )
#         expected_error_message = "trampoline_hops must not contain target_pubkey"
#         assert expected_error_message in exc_info.value.args[0], (
#             f"Expected substring '{expected_error_message}' "
#             f"not found in actual string '{exc_info.value.args[0]}'"
#         )
#
#     def test_path_too_long(self):
#         self.init()
#         self.send_payment(self.fiber2, self.fiber4, 1 * 100000000)
#         # todo 发送到节点4 失败
#         # keysend:发送到Trampoline节点成功，但是Trampoline节点发送金额不考虑手续费导致失败
#         payment = self.fiber1.get_client().send_payment(
#             {
#                 "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
#                 "currency": "Fibd",
#                 "amount": hex(1 * 100000000),
#                 "keysend": True,
#                 "trampoline_hops": [
#                     {
#                         "pubkey": self.fiber2.get_client().node_info()["node_id"],
#                         # "fee_rate": hex(1000),
#                     },
#                 ],
#             }
#         )
#         self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
#         payment = self.fiber1.get_client().get_payment(
#             {"payment_hash": payment["payment_hash"]}
#         )
#         print("payment", payment)
#
#     def test_fee_rate_check(self):
#         """
#         设置了fee rate ，检查fee 是否收取正常
#             fee_rate is none
#                 默认为1000 *2
#             fee_rate is set
#                 默认为set的值
#
#         设置了2个节点
#
#
#         Returns:
#         """
#         # key send
#         # fee_rate is none
#         self.init()
#         payment = self.fiber1.get_client().send_payment(
#             {
#                 "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
#                 "currency": "Fibd",
#                 "amount": hex(1 * 100000000),
#                 "keysend": True,
#                 "trampoline_hops": [
#                     {
#                         "pubkey": self.fiber2.get_client().node_info()["node_id"],
#                         # "fee_rate": hex((1 << 64) - 1),
#                     },
#                 ],
#                 "dry_run": True,
#             }
#         )
#         # todo  是否该为0？
#         assert payment["fee"] == hex(300200)
#         self.send_payment(self.fiber2, self.fiber4, 1 * 100000000)
#         # todo 发送到节点4 失败
#         # keysend:发送到Trampoline节点成功，但是Trampoline节点发送金额不考虑手续费导致失败
#         payment = self.fiber1.get_client().send_payment(
#             {
#                 "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
#                 "currency": "Fibd",
#                 "amount": hex(1 * 100000000),
#                 "keysend": True,
#                 "trampoline_hops": [
#                     {
#                         "pubkey": self.fiber2.get_client().node_info()["node_id"],
#                         "fee_rate": hex(1000),
#                     },
#                 ],
#             }
#         )
#         self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
#         payment = self.fiber1.get_client().get_payment(
#             {"payment_hash": payment["payment_hash"]}
#         )
#         # print("payment", payment)
#         before_balances = self.get_fibers_balance()
#         payment = self.fiber1.get_client().send_payment(
#             {
#                 "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
#                 "currency": "Fibd",
#                 "amount": hex(1 * 100000000),
#                 "keysend": True,
#                 "trampoline_hops": [
#                     {
#                         "pubkey": self.fiber2.get_client().node_info()["node_id"],
#                         # "fee_rate": hex(1000),
#                     },
#                 ],
#             }
#         )
#         self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
#         payment = self.fiber1.get_client().get_payment(
#             {"payment_hash": payment["payment_hash"]}
#         )
#         print("payment", payment)
#         # todo fee == 0 ,但实际不是0
#         assert payment["fee"] == hex(0)
#         after_balances = self.get_fibers_balance()
#         result = self.get_channel_balance_change(before_balances, after_balances)
#         print(result)
#         # fee = 2000
#         assert result == [
#             {
#                 "local_balance": 100200000,
#                 "offered_tlc_balance": 0,
#                 "received_tlc_balance": 0,
#             },
#             {
#                 "local_balance": -200000,
#                 "offered_tlc_balance": 0,
#                 "received_tlc_balance": 0,
#             },
#             {
#                 "local_balance": -100000000,
#                 "offered_tlc_balance": 0,
#                 "received_tlc_balance": 0,
#             },
#             {"local_balance": 0, "offered_tlc_balance": 0, "received_tlc_balance": 0},
#         ]
#         # fee_rate is set = 0
#         before_balances = self.get_fibers_balance()
#         payment = self.fiber1.get_client().send_payment(
#             {
#                 "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
#                 "currency": "Fibd",
#                 "amount": hex(1 * 100000000),
#                 "keysend": True,
#                 "trampoline_hops": [
#                     {
#                         "pubkey": self.fiber2.get_client().node_info()["node_id"],
#                         "fee_rate": hex(0),
#                     },
#                 ],
#             }
#         )
#         self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
#         payment = self.fiber1.get_client().get_payment(
#             {"payment_hash": payment["payment_hash"]}
#         )
#         print("payment", payment)
#         assert payment["fee"] == hex(0)
#         after_balances = self.get_fibers_balance()
#         result = self.get_channel_balance_change(before_balances, after_balances)
#         print(result)
#         # fee = 2000
#         assert result == [
#             {
#                 "local_balance": 100000000,
#                 "offered_tlc_balance": 0,
#                 "received_tlc_balance": 0,
#             },
#             {"local_balance": 0, "offered_tlc_balance": 0, "received_tlc_balance": 0},
#             {
#                 "local_balance": -100000000,
#                 "offered_tlc_balance": 0,
#                 "received_tlc_balance": 0,
#             },
#             {"local_balance": 0, "offered_tlc_balance": 0, "received_tlc_balance": 0},
#         ]
#         # 设置了2个节点
#         before_balances = self.get_fibers_balance()
#         payment = self.fiber1.get_client().send_payment(
#             {
#                 "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
#                 "currency": "Fibd",
#                 "amount": hex(1 * 100000000),
#                 "keysend": True,
#                 "trampoline_hops": [
#                     {
#                         "pubkey": self.fiber2.get_client().node_info()["node_id"],
#                         # "fee_rate": hex(1000),
#                     },
#                     {
#                         "pubkey": self.fiber3.get_client().node_info()["node_id"],
#                         # "fee_rate": hex(1000),
#                     },
#                 ],
#             }
#         )
#         self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
#         payment = self.fiber1.get_client().get_payment(
#             {"payment_hash": payment["payment_hash"]}
#         )
#         print("payment", payment)
#         # todo fee == 0 ,但实际不是0
#         assert payment["fee"] == hex(0)
#         after_balances = self.get_fibers_balance()
#         result = self.get_channel_balance_change(before_balances, after_balances)
#         print(result)
#         assert result == [
#             {
#                 "local_balance": 100400400,
#                 "offered_tlc_balance": 0,
#                 "received_tlc_balance": 0,
#             },
#             {
#                 "local_balance": -200400,
#                 "offered_tlc_balance": 0,
#                 "received_tlc_balance": 0,
#             },
#             {
#                 "local_balance": -200000,
#                 "offered_tlc_balance": 0,
#                 "received_tlc_balance": 0,
#             },
#             {
#                 "local_balance": -100000000,
#                 "offered_tlc_balance": 0,
#                 "received_tlc_balance": 0,
#             },
#         ]
#
#     def test_fee_rate_too_small(self):
#         """
#         fee rate 为0 就不收手续费
#         Returns:
#         """
#         self.init()
#
#         before_balances = self.get_fibers_balance()
#         payment = self.fiber1.get_client().send_payment(
#             {
#                 "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
#                 "currency": "Fibd",
#                 "amount": hex(1 * 100000000),
#                 "keysend": True,
#                 "trampoline_hops": [
#                     {
#                         "pubkey": self.fiber2.get_client().node_info()["node_id"],
#                         "fee_rate": hex(0),
#                     },
#                 ],
#             }
#         )
#         self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
#         payment = self.fiber1.get_client().get_payment(
#             {"payment_hash": payment["payment_hash"]}
#         )
#         print("payment", payment)
#         assert payment["fee"] == hex(0)
#         after_balances = self.get_fibers_balance()
#         result = self.get_channel_balance_change(before_balances, after_balances)
#         print(result)
#         # fee = 2000
#         assert result == [
#             {
#                 "local_balance": 100000000,
#                 "offered_tlc_balance": 0,
#                 "received_tlc_balance": 0,
#             },
#             {"local_balance": 0, "offered_tlc_balance": 0, "received_tlc_balance": 0},
#             {
#                 "local_balance": -100000000,
#                 "offered_tlc_balance": 0,
#                 "received_tlc_balance": 0,
#             },
#             {"local_balance": 0, "offered_tlc_balance": 0, "received_tlc_balance": 0},
#         ]
#
#     def test_fee_rate_with_dry_run(self):
#         """
#         check dry run fee rate result is correct
#         todo fee rate 不准
#         1. fee rate 是否准确
#             都返回0
#         2. trampoline_hops 没直连
#             no path found
#         3. trampoline_hops 到达不了target
#             调用成功
#         Returns:
#         """
#         # 1. fee rate 不准
#         self.init()
#         payment = self.fiber1.get_client().send_payment(
#             {
#                 "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
#                 "currency": "Fibd",
#                 "amount": hex(1 * 100000000),
#                 "keysend": True,
#                 "trampoline_hops": [
#                     {
#                         "pubkey": self.fiber2.get_client().node_info()["node_id"],
#                         # "fee_rate": hex((1 << 64) - 1),
#                     },
#                 ],
#                 "dry_run": True,
#             }
#         )
#         assert payment["fee"] == hex(0)
#         # 2. trampoline_hops 没直连
#         with pytest.raises(Exception) as exc_info:
#             payment = self.fiber1.get_client().send_payment(
#                 {
#                     "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
#                     "currency": "Fibd",
#                     "amount": hex(1 * 100000000),
#                     "keysend": True,
#                     "trampoline_hops": [
#                         {
#                             "pubkey": self.fiber3.get_client().node_info()["node_id"],
#                             # "fee_rate": hex((1 << 64) - 1),
#                         },
#                     ],
#                     "dry_run": True,
#                 }
#             )
#         expected_error_message = "no path found"
#         assert expected_error_message in exc_info.value.args[0], (
#             f"Expected substring '{expected_error_message}' "
#             f"not found in actual string '{exc_info.value.args[0]}'"
#         )
#
#         # 029adbab369add822cf2f30bdcbc22421958619b693a3deb9899f19fbae37b12ac rand pubkey
#         payment = self.fiber1.get_client().send_payment(
#             {
#                 "target_pubkey": "029adbab369add822cf2f30bdcbc22421958619b693a3deb9899f19fbae37b12ac",
#                 "currency": "Fibd",
#                 "amount": hex(1 * 100000000),
#                 "keysend": True,
#                 "trampoline_hops": [
#                     {
#                         "pubkey": self.fiber2.get_client().node_info()["node_id"],
#                         # "fee_rate": hex((1 << 64) - 1),
#                     },
#                 ],
#                 "dry_run": True,
#             }
#         )
#
#     def test_fee_rate_with_max_fee_amount(self):
#         """
#         max fee 给太低报错,拼写错误 budget=1
#         检查 max_fee_amount 限制是否是正确的
#             max_fee_amount >= trampoline_routing+ 整个路由
#         Returns:
#         """
#         self.init()
#         with pytest.raises(Exception) as exc_info:
#             payment = self.fiber1.get_client().send_payment(
#                 {
#                     "target_pubkey": self.fiber3.get_client().node_info()["node_id"],
#                     "currency": "Fibd",
#                     "amount": hex(1 * 100000000),
#                     "keysend": True,
#                     "max_fee_amount": hex(200001),
#                     "trampoline_hops": [
#                         {
#                             "pubkey": self.fiber2.get_client().node_info()["node_id"],
#                             "fee_rate": hex(100000),
#                         },
#                     ],
#                 }
#             )
#         expected_error_message = " max_fee_amount too low for trampoline service fees"
#         assert expected_error_message in exc_info.value.args[0], (
#             f"Expected substring '{expected_error_message}' "
#             f"not found in actual string '{exc_info.value.args[0]}'"
#         )
#
#         # 不给tp节点到fiber4的路由费看能不能成功
#         with pytest.raises(Exception) as exc_info:
#             payment = self.fiber1.get_client().send_payment(
#                 {
#                     "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
#                     "currency": "Fibd",
#                     "amount": hex(1 * 100000000),
#                     "keysend": True,
#                     "max_fee_amount": hex(200000),
#                     "trampoline_hops": [
#                         {
#                             "pubkey": self.fiber2.get_client().node_info()["node_id"],
#                             # "fee_rate": hex(100000),
#                         },
#                     ],
#                 }
#             )
#             self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
#         expected_error_message = "Failed"
#         assert expected_error_message in exc_info.value.args[0], (
#             f"Expected substring '{expected_error_message}' "
#             f"not found in actual string '{exc_info.value.args[0]}'"
#         )
#         before_balances = self.get_fibers_balance()
#
#         # todo 目前修改max_fee_amount 会调整用户支出
#         payment = self.fiber1.get_client().send_payment(
#             {
#                 "target_pubkey": self.fiber4.get_client().node_info()["node_id"],
#                 "currency": "Fibd",
#                 "amount": hex(1 * 100000000),
#                 "keysend": True,
#                 "max_fee_amount": hex(400300),
#                 "trampoline_hops": [
#                     {
#                         "pubkey": self.fiber2.get_client().node_info()["node_id"],
#                         # "fee_rate": hex(100000),
#                     },
#                 ],
#             }
#         )
#         self.wait_payment_state(self.fiber1, payment["payment_hash"], "Success")
#         after_balances = self.get_fibers_balance()
#         result = self.get_channel_balance_change(before_balances, after_balances)
#         print(result)
