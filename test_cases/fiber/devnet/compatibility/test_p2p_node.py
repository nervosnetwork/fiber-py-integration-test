"""验证 v0.10.1 节点逐端升级期间的公开 CKB 通道和双向付款。"""

from typing import NamedTuple

from parameterized import parameterized

from framework.basic_fiber import FiberTest
from framework.helper.fiber_ops import start_with_confirm, wait_for_result
from framework.test_fiber import FiberConfigPath

CKB = 100_000_000
SECOND_CHANNEL_OPENERS = ["upgraded_opens", "legacy_opens"]


class ChannelLedger(NamedTuple):
    # 双方角色始终按第一条通道命名，即使第二条由另一端发起。
    outpoint: str
    opener_balance: int
    acceptor_balance: int


class TestP2p(FiberTest):
    tmp_path_name = "tmp/p2p-node-rolling-upgrade"
    start_fiber_config = {
        "fiber_open_channel_auto_accept_min_ckb_funding_amount": 2_000 * CKB
    }

    # TEST-MAP: P2PUP-01
    def test_p2p_compatibility(self):
        """
        1. 两个 v0.10.1 节点共同出资，建立唯一的公开 CKB 通道。
        2. 原发起端先付 10 Shannon，记录已清账的非对称余额。
        3. 只升级原发起端，付款前核对两端保留原通道和原余额。
        4. 双方各付 1 Shannon，每笔只提交一次并逐笔核账。
        """
        # 1. 拓扑：opener ↔ acceptor；双方各出资 1,000 CKB（另加框架预留）。
        opener, acceptor = self._start_legacy_pair()
        original = self.open_channel(
            opener, acceptor, 1_000 * CKB, 1_000 * CKB, other_config={"public": True}
        )
        endpoints = self._single_attempt_endpoints(opener, acceptor)
        ledger = self._wait_ledgers(endpoints, [original])
        assert (
            ledger[original].opener_balance >= 11
            and ledger[original].acceptor_balance >= 1
        )

        # 2. 先在原通道单向付 10，不付回；让余额重置可被观察到。
        marker = self._keysend_once(opener, acceptor, 10)
        before = self._wait_transfer(
            endpoints, opener, marker, 10, ledger, via=original
        )
        assert before[original].opener_balance != before[original].acceptor_balance

        # 3. opener 原库升级，不重开通道；按原 ID 核对出资点及两端余额。
        opener.stop()
        opener.fiber_config_enum = FiberConfigPath.CURRENT_DEV
        start_with_confirm(opener, timeout=90)
        ledger = self._wait_ledgers(endpoints, [original])
        assert ledger == before

        # 4. 普通路由只有原通道可走；先证实去程扣款和入账，再发回程。
        for sender, receiver in ((opener, acceptor), (acceptor, opener)):
            payment = self._keysend_once(sender, receiver, 1)
            ledger = self._wait_transfer(
                endpoints, sender, payment, 1, ledger, via=original
            )

    # TEST-MAP: P2PUP-02
    @parameterized.expand(SECOND_CHANNEL_OPENERS)
    def test_second_channel_with_mixed_peers(self, second_opener):
        """
        1. 在两个旧节点间开一条公开 CKB 通道，单向付 10 Shannon 留下余额标记。
        2. 只升级原发起端，确认原通道就绪且资金未变。
        3. 分别由新版或旧版发起第二条公开通道，核对两条独立的出资点。
        4. 指定新通道双向各付 1 Shannon，原通道余额不动；再验证普通双向付款。
        """
        # 1. 拓扑：opener ↔ acceptor；两个 v0.10.1 节点在原通道各出资 1,000 CKB。
        opener, acceptor = self._start_legacy_pair()
        original = self.open_channel(
            opener, acceptor, 1_000 * CKB, 1_000 * CKB, other_config={"public": True}
        )
        endpoints = self._single_attempt_endpoints(opener, acceptor)
        ledger = self._wait_ledgers(endpoints, [original])
        assert (
            ledger[original].opener_balance >= 11
            and ledger[original].acceptor_balance >= 1
        )
        marker = self._keysend_once(opener, acceptor, 10)
        before = self._wait_transfer(
            endpoints, opener, marker, 10, ledger, via=original
        )
        assert before[original].opener_balance != before[original].acceptor_balance

        # 2. opener 保留原库升级，acceptor 留在 v0.10.1。
        opener.stop()
        opener.fiber_config_enum = FiberConfigPath.CURRENT_DEV
        start_with_confirm(opener, timeout=90)
        assert self._wait_ledgers(endpoints, [original]) == before

        # 3. 两种发起方向各用全新样本；原通道保持就绪且不参与新通道配资。
        funder, peer = (
            (opener, acceptor)
            if second_opener == "upgraded_opens"
            else (acceptor, opener)
        )
        second = self.open_channel(
            funder, peer, 1_000 * CKB, 1_000 * CKB, other_config={"public": True}
        )
        assert second != original
        ledger = self._wait_ledgers(endpoints, [original, second])
        assert ledger[original] == before[original]
        assert ledger[second].outpoint != ledger[original].outpoint
        assert min(ledger[second].opener_balance, ledger[second].acceptor_balance) >= 1

        # 4. 先指定第二条通道，两端逐笔清账；普通选路另测，不替代定向付款。
        for sender, receiver in ((opener, acceptor), (acceptor, opener)):
            payment = self._keysend_once(
                sender, receiver, 1, outpoint=ledger[second].outpoint
            )
            ledger = self._wait_transfer(
                endpoints, sender, payment, 1, ledger, via=second
            )
        for sender, receiver in ((opener, acceptor), (acceptor, opener)):
            payment = self._keysend_once(sender, receiver, 1)
            ledger = self._wait_transfer(endpoints, sender, payment, 1, ledger)

    # TEST-MAP: P2PUP-03
    @parameterized.expand(SECOND_CHANNEL_OPENERS)
    def test_both_channels_after_rolling_upgrade(self, second_opener):
        """
        1. 两个旧节点开公开 CKB 通道，原发起端单向付 10 Shannon 后原库升级。
        2. 新旧节点再开另一条公开通道，指定它单向付 20 Shannon，记录两套不同账本。
        3. 后升级的一端带原库启动，付款前逐条核对两端的通道身份与余额。
        4. 逐条指定原通道和第二条通道双向实付；再验证普通双向付款。
        """
        # 1. 拓扑：opener ↔ acceptor；原通道双方各出资 1,000 CKB，先升级 opener。
        opener, acceptor = self._start_legacy_pair()
        original = self.open_channel(
            opener, acceptor, 1_000 * CKB, 1_000 * CKB, other_config={"public": True}
        )
        endpoints = self._single_attempt_endpoints(opener, acceptor)
        ledger = self._wait_ledgers(endpoints, [original])
        assert (
            ledger[original].opener_balance >= 11
            and ledger[original].acceptor_balance >= 1
        )
        marker = self._keysend_once(opener, acceptor, 10)
        before = self._wait_transfer(
            endpoints, opener, marker, 10, ledger, via=original
        )
        assert before[original].opener_balance != before[original].acceptor_balance
        opener.stop()
        opener.fiber_config_enum = FiberConfigPath.CURRENT_DEV
        start_with_confirm(opener, timeout=90)
        assert self._wait_ledgers(endpoints, [original]) == before

        # 2. 两端各出资 1,000 CKB；20 Shannon 只走第二条，与原通道的标记区分。
        funder, peer = (
            (opener, acceptor)
            if second_opener == "upgraded_opens"
            else (acceptor, opener)
        )
        second = self.open_channel(
            funder, peer, 1_000 * CKB, 1_000 * CKB, other_config={"public": True}
        )
        assert second != original
        ledger = self._wait_ledgers(endpoints, [original, second])
        assert ledger[original] == before[original]
        assert ledger[second].outpoint != ledger[original].outpoint
        assert (
            ledger[second].opener_balance >= 21 and ledger[second].acceptor_balance >= 1
        )
        marker = self._keysend_once(
            opener, acceptor, 20, outpoint=ledger[second].outpoint
        )
        before = self._wait_transfer(endpoints, opener, marker, 20, ledger, via=second)
        assert before[second].opener_balance != before[second].acceptor_balance
        assert before[original].opener_balance != before[second].opener_balance
        assert before[original].acceptor_balance != before[second].acceptor_balance

        # 3. 只升级 acceptor；还没再付款就要查回两个原 ID、完整 outpoint 和各端余额。
        acceptor.stop()
        acceptor.fiber_config_enum = FiberConfigPath.CURRENT_DEV
        start_with_confirm(acceptor, timeout=90)
        ledger = self._wait_ledgers(endpoints, [original, second])
        assert ledger == before

        # 4. 两条通道共四笔定向付款，逐笔要求另一条不动；普通路由另做往返。
        for channel_id in (original, second):
            for sender, receiver in ((opener, acceptor), (acceptor, opener)):
                payment = self._keysend_once(
                    sender, receiver, 1, outpoint=ledger[channel_id].outpoint
                )
                ledger = self._wait_transfer(
                    endpoints, sender, payment, 1, ledger, via=channel_id
                )
        for sender, receiver in ((opener, acceptor), (acceptor, opener)):
            payment = self._keysend_once(sender, receiver, 1)
            ledger = self._wait_transfer(endpoints, sender, payment, 1, ledger)

    def _start_legacy_pair(self):
        opener = self.start_new_fiber(
            self.generate_account(10_000), fiber_version=FiberConfigPath.V0101_DEV
        )
        acceptor = self.start_new_fiber(
            self.generate_account(10_000), fiber_version=FiberConfigPath.V0101_DEV
        )
        return opener, acceptor

    @staticmethod
    def _single_attempt_endpoints(opener, acceptor):
        # 保留升级前的对端公钥；底层 HTTP 客户端也只试一次，丢响应时不重发付款。
        for node in (opener, acceptor):
            node.get_client().try_count = 1
            node.get_client().timeout = 5
        return (
            (opener.get_client(), acceptor.get_pubkey()),
            (acceptor.get_client(), opener.get_pubkey()),
        )

    def _keysend_once(self, sender, receiver, amount, *, outpoint=None):
        """只提交一次，返回这次付款的 hash；指定出资点时先核对一跳路由。"""
        if outpoint is None:
            return self.send_payment(sender, receiver, amount, wait=False, try_count=0)
        client = sender.get_client()
        target = receiver.get_pubkey()
        hops = client.build_router(
            {
                "amount": hex(amount),
                "hops_info": [{"pubkey": target, "channel_outpoint": outpoint}],
            }
        )["router_hops"]
        assert len(hops) == 1, hops
        hop = hops[0]
        assert (
            hop["target"],
            hop["channel_outpoint"],
            int(hop["amount_received"], 16),
        ) == (target, outpoint, amount), hop
        return client.send_payment_with_router({"keysend": True, "router": hops})[
            "payment_hash"
        ]

    def _wait_transfer(
        self, endpoints, sender, payment_hash, amount, before, *, via=None
    ):
        """用付款前的两端账本独立计算期望；每种允许结果都只改变一条通道。"""
        self.wait_payment_state(sender, payment_hash, "Success", timeout=60)
        debit = amount if sender.get_client() is endpoints[0][0] else -amount
        allowed = []
        for channel_id in (before if via is None else (via,)):
            old = before[channel_id]
            expected = before.copy()
            expected[channel_id] = ChannelLedger(
                old.outpoint, old.opener_balance - debit, old.acceptor_balance + debit
            )
            allowed.append(expected)
        return self._wait_ledgers(endpoints, before, allowed=allowed, timeout=30)

    @staticmethod
    def _wait_ledgers(endpoints, channel_ids, *, allowed=None, timeout=180):
        """按原对端和通道 ID 读取两端已就绪、可见且无在途款的账本，不按 RPC 顺序配对。"""
        wanted = set(channel_ids)

        def read():
            views = []
            for client, peer_key in endpoints:
                if not any(
                    p["pubkey"] == peer_key for p in client.list_peers()["peers"]
                ):
                    return None
                rows = {
                    r["channel_id"]: r
                    for r in client.list_channels({"pubkey": peer_key})["channels"]
                }
                if rows.keys() != wanted:
                    return None
                visible = {
                    edge["channel_outpoint"]
                    for edge in client.graph_channels()["channels"]
                    if (edge.get("update_info_of_node1") or {}).get("enabled")
                    and (edge.get("update_info_of_node2") or {}).get("enabled")
                }
                for row in rows.values():
                    if (
                        row["state"]["state_name"] != "ChannelReady"
                        or not row["channel_outpoint"]
                        or row["channel_outpoint"] not in visible
                        or int(row["offered_tlc_balance"], 16)
                        or int(row["received_tlc_balance"], 16)
                    ):
                        return None
                views.append(rows)
            opener, acceptor = views
            ledger = {}
            for cid, row in opener.items():
                point = row["channel_outpoint"]
                assert point == acceptor[cid]["channel_outpoint"], (
                    cid,
                    row,
                    acceptor[cid],
                )
                ledger[cid] = ChannelLedger(
                    point,
                    int(row["local_balance"], 16),
                    int(acceptor[cid]["local_balance"], 16),
                )
            return ledger if allowed is None or ledger in allowed else None

        return wait_for_result(
            f"双方通道 {sorted(wanted)} 就绪并清账，预期账本={allowed}",
            read,
            timeout=timeout,
        )
