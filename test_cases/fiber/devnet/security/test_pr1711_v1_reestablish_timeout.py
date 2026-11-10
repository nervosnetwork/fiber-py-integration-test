"""PR #1711：V1（Legacy）通道对端重连后扣住 ReestablishChannel，受害方超时强关。

两端先用 v0.9.1 开 Legacy 通道，再把受害方升级为 stock FNN、攻击方升级为
attack FNN。攻击方丢弃自己发出的 ReestablishChannel，受害方在重连后超过
REESTABLISH_TIMEOUT（非 test 构建 300s）、并在随后的 MaintainChannelTlcs 检查
（CHECK_CHANNELS_INTERVAL：debug 构建 3s，release 60s）中强关。用例见
reviews/pr1711-v1-reestablish-timeout.md。
"""

import time

from framework.attack_fnn import LEGACY_COUNTERPARTY_ENV
from framework.basic_p2p import P2pFiberTest
from framework.p2p_peer import P2pPeer
from framework.test_fiber import FiberConfigPath
from test_cases.fiber.devnet.migration._helpers import start_with_confirm

CKB = 100000000
REESTABLISH_TIMEOUT_SECONDS = 300
# release 构建为 60s（CI 的 debug 构建为 3s），按 60s 取上界，两种构建都适用。
CHECK_CHANNELS_INTERVAL_SECONDS = 60
FORCE_CLOSE_DEADLINE_SECONDS = (
    REESTABLISH_TIMEOUT_SECONDS + 3 * CHECK_CHANNELS_INTERVAL_SECONDS
)
LOCAL_FORCE_CLOSE_STATES = {
    ("ShuttingDown", "WAITING_COMMITMENT_CONFIRMATION"),
    ("Closed", "UNCOOPERATIVE_LOCAL"),
}


def _is_local_force_close(state):
    flags = state.get("state_flags") or ""
    return any(
        state["state_name"] == name and flag in flags
        for name, flag in LOCAL_FORCE_CLOSE_STATES
    )


def _outpoint(channel_outpoint_hex):
    raw = bytes.fromhex(channel_outpoint_hex.removeprefix("0x"))
    assert len(raw) == 36, channel_outpoint_hex
    return "0x" + raw[:32].hex(), hex(int.from_bytes(raw[32:], "little"))


class TestPr1711V1ReestablishTimeout(P2pFiberTest):
    tmp_path_name = "tmp-p2p-pr1711"
    # 两端都用 v0.9.1 建通道，保证通道是 Legacy（session_v2=None）。
    fiber_version = FiberConfigPath.V091_DEV
    attacker_fiber_version = FiberConfigPath.V091_DEV
    channel_local_balance = 200 * CKB

    def setup_method(self, method):
        super().setup_method(method)
        if self.debug:
            return
        before = self.channel_of(self.victim)
        assert before["state"]["state_name"] == "ChannelReady", before

        # 升级：攻击方换成 attack FNN（Legacy 对端模式），受害方换成 stock FNN。
        self.victim.stop()
        self.attacker.stop()
        self.attacker.fiber_config_enum = FiberConfigPath.ATTACK_FULL_HASH_DEV
        self.attacker.extra_env = LEGACY_COUNTERPARTY_ENV
        start_with_confirm(self.attacker, confirm="y", timeout=60)
        self.victim.fiber_config_enum = FiberConfigPath.CURRENT_DEV
        start_with_confirm(self.victim, confirm="y", timeout=60)
        self.peer = P2pPeer(self.attacker)
        self.victim.connect_peer(self.attacker)
        self.wait_channel_state(self.victim, "ChannelReady", timeout=120)
        after = self.channel_of(self.victim)
        assert after["channel_outpoint"] == before["channel_outpoint"], (
            before,
            after,
        )

    # TEST-MAP: PR1711-01
    def test_peer_withholds_reestablish_victim_force_closes_after_timeout(self):
        """
        1. 升级后的 Legacy 通道上受害方给攻击方付 1 CKB，确认通道可用并记录资金 outpoint。
        2. 攻击方丢弃自己发出的 ReestablishChannel；受害方断开后重新连接。
        3. 最长等待 T+3I，检查受害方本端强关，且距断开不早于 T。
        4. 检查资金 cell 已被一笔已上链的交易花费（受害方强关的承诺交易）。
        """
        # 1. 付一笔款确认通道可用，记录资金 outpoint。
        self.send_payment(self.victim, self.attacker, 1 * CKB)
        ready = self.channel_of(self.victim)
        assert ready["state"]["state_name"] == "ChannelReady", ready
        funding_tx_hash, funding_index = _outpoint(ready["channel_outpoint"])
        ckb = self.node.getClient()
        assert ckb.get_live_cell(funding_index, funding_tx_hash)["status"] == "live"

        # 2. 攻击方丢弃自己的 ReestablishChannel，受害方断开再重连，确认对端确实重新连上。
        self.peer.intercept(self.channel_id, drop_out=["ReestablishChannel"])
        attacker_pubkey = self.attacker.get_pubkey()
        disconnected_at = time.time()
        self.disconnect_peers()
        # 受害方可能立即自动重连，看不到断开窗口也继续；下界从断开时刻算。
        self._wait_victim_peer(
            attacker_pubkey, connected=False, timeout=10, strict=False
        )
        self.reconnect_peers()
        self._wait_victim_peer(attacker_pubkey, connected=True, timeout=60)
        reconnected_at = time.time()
        self.logger.info(
            f"reconnected {reconnected_at - disconnected_at:.1f}s after disconnect"
        )

        # 3. 等受害方本端强关；不早于断开后 T，不晚于重连后 T+3I。
        deadline = reconnected_at + FORCE_CLOSE_DEADLINE_SECONDS
        state = self.channel_of(self.victim)["state"]
        while not _is_local_force_close(state) and time.time() < deadline:
            time.sleep(5)
            state = self.channel_of(self.victim)["state"]
        assert _is_local_force_close(state), (
            f"peer withheld ReestablishChannel, but victim channel is still "
            f"{state} {time.time() - reconnected_at:.0f}s after reconnect; "
            f"victim log:\n{self._log_tail(self.victim, 'eestablish')}"
        )
        closed_after = time.time() - disconnected_at
        self.logger.info(
            f"victim force-closed {closed_after:.0f}s after disconnect: {state}"
        )
        assert closed_after >= REESTABLISH_TIMEOUT_SECONDS, (
            f"victim force-closed {closed_after:.0f}s after disconnect, "
            f"before REESTABLISH_TIMEOUT={REESTABLISH_TIMEOUT_SECONDS}s"
        )

        # 4. 资金 cell 被花费，花费它的交易已上链（节点 setup 已开自动出块）。
        funding_tx = ckb.get_transaction(funding_tx_hash)
        funding_lock = funding_tx["transaction"]["outputs"][int(funding_index, 16)][
            "lock"
        ]
        spending_tx_hash = None
        chain_deadline = time.time() + 300
        while time.time() < chain_deadline:
            spending_tx_hash = self._funding_spender(
                funding_lock, funding_tx_hash, funding_index
            )
            if spending_tx_hash is not None:
                break
            time.sleep(3)
        assert spending_tx_hash is not None, (
            f"funding cell {funding_tx_hash}:{funding_index} not spent on chain; "
            f"victim state {self.channel_of(self.victim)['state']}, "
            f"tx pool {ckb.get_raw_tx_pool()}"
        )
        assert ckb.get_transaction(spending_tx_hash)["tx_status"]["status"] == (
            "committed"
        )
        assert ckb.get_live_cell(funding_index, funding_tx_hash)["status"] != "live"
        self.logger.info(
            f"funding cell spent by committed tx {spending_tx_hash}; victim "
            f"latest_commitment_transaction_hash="
            f"{self.channel_of(self.victim)['latest_commitment_transaction_hash']}"
        )

    def _wait_victim_peer(self, pubkey, connected, timeout, strict=True):
        deadline = time.time() + timeout
        while time.time() < deadline:
            peers = self.victim.get_client().list_peers()["peers"]
            if (pubkey in {peer["pubkey"] for peer in peers}) == connected:
                return True
            time.sleep(0.2)
        if strict:
            raise TimeoutError(f"victim peer {pubkey} connected != {connected}")
        return False

    @staticmethod
    def _log_tail(fiber, keyword, lines=40):
        """失败信息用：节点日志中含 keyword 的最后若干行，不作判据。"""
        try:
            with open(f"{fiber.tmp_path}/node.log", errors="replace") as log:
                hits = [line.rstrip() for line in log if keyword in line]
        except FileNotFoundError:
            return "<no node.log>"
        return "\n".join(hits[-lines:])

    def _funding_spender(self, funding_lock, funding_tx_hash, funding_index):
        """返回已上链、花费资金 outpoint 的交易 hash；尚未花费时返回 None。"""
        ckb = self.node.getClient()
        txs = ckb.get_transactions(
            {
                "script": funding_lock,
                "script_type": "lock",
                "script_search_mode": "exact",
            },
            "asc",
            "0xff",
            None,
        )
        for item in txs["objects"]:
            if item.get("io_type") != "input":
                continue
            tx = ckb.get_transaction(item["tx_hash"])
            for cell_input in tx["transaction"]["inputs"]:
                previous = cell_input["previous_output"]
                if (previous["tx_hash"], previous["index"]) == (
                    funding_tx_hash,
                    funding_index,
                ):
                    return item["tx_hash"]
        return None
