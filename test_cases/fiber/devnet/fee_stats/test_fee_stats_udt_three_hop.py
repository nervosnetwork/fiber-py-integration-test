"""UDT 三跳 A→B→C：fee_report / forwarding_history 含 UDT 分组（Copilot F-4）。

UDT 节点配置对齐 `test_find_path.test_mul_path`（xudt_cell_deps、whitelist）；不复制其超大
`fiber_open_channel_auto_accept_min_ckb_funding_amount`，否则 `open_channel` 会误判走 CKB 分支（见文件内注释）。
"""

import time

from framework.basic_fiber import FiberTest
from test_cases.fiber.devnet.fee_stats._fee_stats_util import (
    scripts_equivalent,
    skip_if_fee_stats_unavailable,
    u128,
    u64,
    udt_asset_report,
)


class TestFeeStatsUdtThreeHop(FiberTest):
    def test_three_hop_udt_forwarding_and_reports(self):
        """F-4: UDT 转发后 B 上 fee_report / forwarding_history 带 udt_type_script。"""
        skip_if_fee_stats_unavailable(self.fiber1.get_client())

        deploy_hash, deploy_index = self.udtContract.get_deploy_hash_and_index()
        # UDT / XUDT deps (aligned with test_find_path.test_mul_path), but do NOT set
        # fiber_open_channel_auto_accept_min_ckb_funding_amount to a huge value here:
        # basic_fiber.open_channel compares fiber1_balance against that field; if it is
        # ~1e15 shannon, any normal funding amount takes the *CKB-only* branch and never
        # passes funding_udt_type_script — send_payment(udt=...) then sees 0 UDT liquidity.
        update_config = {
            "ckb_rpc_url": self.node.rpcUrl,
            "ckb_udt_whitelist": True,
            "xudt_script_code_hash": self.Contract.get_ckb_contract_codehash(
                deploy_hash, deploy_index, True, self.node.rpcUrl
            ),
            "xudt_cell_deps_tx_hash": deploy_hash,
            "xudt_cell_deps_index": deploy_index,
        }

        acc_a = self.generate_account(
            1000000, self.fiber1.account_private, 1000 * 100000000
        )
        acc_b = self.generate_account(
            1000000, self.fiber1.account_private, 1000 * 100000000
        )
        acc_c = self.generate_account(
            1000000, self.fiber1.account_private, 1000 * 100000000
        )
        fiber_a = self.start_new_fiber(acc_a, update_config)
        fiber_b = self.start_new_fiber(acc_b, update_config)
        fiber_c = self.start_new_fiber(acc_c, update_config)
        fiber_b.connect_peer(fiber_a)
        fiber_c.connect_peer(fiber_b)
        time.sleep(1)

        # Extra UDT on each node (same pattern as trampoline / watch_tower UDT tests).
        for acc in (acc_a, acc_b, acc_c):
            self.faucet(acc, 0, self.fiber1.account_private, 10000 * 100000000)

        udt_script = self.get_account_udt_script(self.fiber1.account_private)
        hop_fee = 1000
        # Use remote balance 0 on open so basic_fiber does NOT post-fund with
        # send_payment(fiber1→fiber2, fiber2_balance) — that sweep can zero A's
        # outbound UDT on A–B and break A→B→C (Insufficient balance: max outbound 0).
        ch_udt = 1000 * 100000000
        self.open_channel(fiber_a, fiber_b, ch_udt, 0, hop_fee, hop_fee, udt=udt_script)
        self.open_channel(fiber_b, fiber_c, ch_udt, 0, hop_fee, hop_fee, udt=udt_script)

        pay_amount = 10 * 100000000
        payment_hash = self.send_payment(fiber_a, fiber_c, pay_amount, udt=udt_script)

        fr_b = fiber_b.get_client().fee_report({})
        udt_fee = udt_asset_report(fr_b["asset_reports"], udt_script)
        assert udt_fee is not None, "expected UDT row in fee_report on hop node"
        assert u64(udt_fee["daily_event_count"]) >= 1
        assert u128(udt_fee["daily_fee_sum"]) > 0

        fh_b = fiber_b.get_client().forwarding_history(
            {"udt_type_script": udt_script, "limit": hex(50)}
        )
        match = [e for e in fh_b["events"] if e["payment_hash"] == payment_hash]
        assert len(match) >= 1
        ev = match[0]
        assert ev.get("udt_type_script") is not None
        assert scripts_equivalent(ev["udt_type_script"], udt_script)

        sr_a = fiber_a.get_client().sent_payment_report()
        udt_sent = udt_asset_report(sr_a["asset_reports"], udt_script)
        assert udt_sent is not None
        assert u64(udt_sent["daily_event_count"]) >= 1

        ph_a = fiber_a.get_client().payment_history(
            {"udt_type_script": udt_script, "limit": hex(50)}
        )
        sends = [
            e
            for e in ph_a["events"]
            if e.get("event_type") == "Send" and e["payment_hash"] == payment_hash
        ]
        assert len(sends) >= 1
        assert sends[0].get("udt_type_script") is not None
        assert scripts_equivalent(sends[0]["udt_type_script"], udt_script)

        rr_c = fiber_c.get_client().received_payment_report()
        udt_recv = udt_asset_report(rr_c["asset_reports"], udt_script)
        assert udt_recv is not None
        assert u64(udt_recv["daily_event_count"]) >= 1

        ph_c = fiber_c.get_client().payment_history(
            {"udt_type_script": udt_script, "limit": hex(50)}
        )
        recvs = [
            e
            for e in ph_c["events"]
            if e.get("event_type") == "Receive"
            and e["payment_hash"] == payment_hash
        ]
        assert len(recvs) >= 1
        assert scripts_equivalent(recvs[0]["udt_type_script"], udt_script)
