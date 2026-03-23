"""
TUI data generator: opens multiple CKB & UDT channels and sends random payments.

Usage:
    pytest test_cases/fiber/devnet/fnn-cli/test_tui_data_generator.py -v -s

After execution the two local fiber nodes stay alive so you can inspect
the Dashboard / Channels / Payments tabs via fnn-cli --tui.
"""

import random
import time

from framework.basic_fiber import FiberTest
from framework.fnn_cli import FnnCli

AUTH_TOKEN = (
    "EsQCCtkBCghjaGFubmVscwoIbWVzc2FnZXMKBWNoYWluCgVncmFwaAoIaW52b2ljZXMK"
    "CHBheW1lbnRzCgVwZWVycwoKd2F0Y2h0b3dlchgDIgkKBwgBEgMYgAgiCQoHCAASAxiA"
    "CCIJCgcIARIDGIEIIgkKBwgBEgMYgggiCQoHCAASAxiDCCIICgYIABICGBgiCQoHCAES"
    "AxiECCIJCgcIABIDGIQIIgkKBwgBEgMYhQgiCQoHCAASAxiFCCIJCgcIARIDGIYIIgkK"
    "BwgAEgMYhggiCQoHCAESAxiHCBIkCAASINfXW27Y4O0VbCYm7ZmQdwAnTsHUzMX1vKt2"
    "ntZAm0knGkAEipd0kOQyxA9h6oq8OC_267N-V9ukmJsSKAPWbvsjtAwsqWftJq1DbM_j"
    "ZUOte00x_jqIrKsPwkKjo_Aaq14AIiIKIFbhKm3u63rug1IRE7jtW6uSHaZyrIS-6kiK"
    "olenfKHm"
)

NUM_CHANNELS = 4
PAYMENTS_PER_CHANNEL = 8


class TestTuiDataGenerator(FiberTest):
    """Generate rich multi-channel, mixed CKB/UDT data for TUI observation."""

    def _make_cli(self, fiber, auth_token=AUTH_TOKEN):
        return FnnCli(
            f"http://127.0.0.1:{fiber.rpc_port}",
            auth_token=auth_token,
        )

    def test_generate_tui_data(self):
        self.debug = True

        # ── Fund both nodes with CKB and UDT ───────────────────────
        self.faucet(
            self.fiber1.account_private,
            0,
            self.fiber1.account_private,
            50000 * 100000000,
        )
        self.faucet(
            self.fiber2.account_private,
            0,
            self.fiber1.account_private,
            50000 * 100000000,
        )
        time.sleep(10)

        udt_script = self.get_account_udt_script(self.fiber1.account_private)
        cli1 = self._make_cli(self.fiber1)
        cli2 = self._make_cli(self.fiber2)
        peer2_pubkey = cli2.node_info()["pubkey"]

        # ── Decide channel types randomly ───────────────────────────
        random.seed(42)
        channel_types = []
        for _ in range(NUM_CHANNELS):
            channel_types.append(random.choice(["CKB", "UDT"]))
        # Ensure at least one of each type
        if "CKB" not in channel_types:
            channel_types[0] = "CKB"
        if "UDT" not in channel_types:
            channel_types[1] = "UDT"

        print(f"\n{'='*60}")
        print(f"  TUI Data Generator")
        print(f"  Channels: {NUM_CHANNELS}  Types: {channel_types}")
        print(f"  Payments per channel: {PAYMENTS_PER_CHANNEL}")
        print(f"{'='*60}\n")

        channel_ids = []

        # ── Open channels ───────────────────────────────────────────
        for idx, ctype in enumerate(channel_types):
            existing = {
                ch["channel_id"] for ch in cli1.list_channels().get("channels", [])
            }

            if ctype == "UDT":
                funding = random.randint(500, 3000) * 100000000
                open_result = cli1.open_channel(
                    pubkey=peer2_pubkey,
                    funding_amount=funding,
                    public=True,
                    funding_udt_type_script=udt_script,
                )
            else:
                funding_ckb = random.randint(200, 800) * 100000000
                open_result = cli1.open_channel(
                    pubkey=peer2_pubkey,
                    funding_amount=funding_ckb,
                    public=True,
                )

            assert (
                "temporary_channel_id" in open_result
            ), f"Channel #{idx+1} ({ctype}) open failed: {open_result}"

            # Wait for the new channel to reach ChannelReady
            new_channel_id = self._wait_new_channel_ready(
                cli1,
                existing,
                timeout=120,
            )
            channel_ids.append((new_channel_id, ctype))
            print(
                f"  Channel #{idx+1}: {ctype}  id={new_channel_id[:20]}...  "
                f"funding={funding if ctype == 'UDT' else funding_ckb}"
            )

        print(f"\n  All {NUM_CHANNELS} channels ready.\n")

        # ── Send random payments on each channel ────────────────────
        total_sent = 0
        all_hashes = []

        for ch_idx, (channel_id, ctype) in enumerate(channel_ids):
            print(f"  --- Channel #{ch_idx+1} ({ctype}) {channel_id[:20]}... ---")

            for pay_idx in range(PAYMENTS_PER_CHANNEL):
                use_invoice = random.choice([True, False])
                if ctype == "UDT":
                    amount = random.randint(1, 20) * 100000000
                else:
                    amount = random.randint(1, 5) * 100000000

                if use_invoice:
                    payment_hash = self._send_invoice_payment(
                        cli1,
                        cli2,
                        amount,
                        ctype,
                        udt_script,
                    )
                else:
                    payment_hash = self._send_keysend_payment(
                        cli1,
                        peer2_pubkey,
                        amount,
                        ctype,
                        udt_script,
                    )

                all_hashes.append(payment_hash)
                total_sent += 1
                label = "inv" if use_invoice else "key"
                unit = "UDT" if ctype == "UDT" else "CKB"
                print(
                    f"    [{label}] #{pay_idx+1}: "
                    f"amount={amount // 100000000} {unit}  "
                    f"hash={payment_hash[:20]}..."
                )
                time.sleep(1)

        # ── Summary ─────────────────────────────────────────────────
        print(f"\n{'='*60}")
        print(f"  Done. Total channels: {NUM_CHANNELS}, total payments: {total_sent}")
        for ch_idx, (cid, ctype) in enumerate(channel_ids):
            print(f"    Channel #{ch_idx+1}: {ctype}  {cid[:24]}...")
        print(f"\n  Nodes remain alive for TUI observation.")
        print(f"  node1 RPC: http://127.0.0.1:{self.fiber1.rpc_port}")
        print(f"  node2 RPC: http://127.0.0.1:{self.fiber2.rpc_port}")
        print(f"\n  TUI command:")
        print(
            f"  ./download/fiber/current/fnn-cli "
            f"--url http://127.0.0.1:{self.fiber1.rpc_port}/ "
            f'--tui --auth-token "{AUTH_TOKEN}"'
        )
        print(f"{'='*60}\n")

    # ── helpers ──────────────────────────────────────────────────────

    def _wait_new_channel_ready(self, cli, existing_ids, timeout=120):
        """Poll until a channel not in *existing_ids* reaches ChannelReady."""
        for _ in range(timeout):
            channels = cli.list_channels().get("channels", [])
            for ch in channels:
                if ch["channel_id"] in existing_ids:
                    continue
                state = ch.get("state", {})
                state_name = (
                    state.get("state_name") if isinstance(state, dict) else str(state)
                )
                if state_name == "ChannelReady":
                    return ch["channel_id"]
            time.sleep(1)
        raise TimeoutError("New channel did not reach ChannelReady within timeout")

    def _send_keysend_payment(
        self, cli_sender, target_pubkey, amount, ctype, udt_script
    ):
        kwargs = {
            "target_pubkey": target_pubkey,
            "amount": amount,
            "keysend": True,
            "allow_self_payment": True,
        }
        if ctype == "UDT":
            kwargs["udt_type_script"] = udt_script
        result = cli_sender.send_payment(**kwargs)
        assert "payment_hash" in result, f"keysend failed: {result}"
        self.wait_payment_state(self.fiber1, result["payment_hash"], "Success")
        return result["payment_hash"]

    def _send_invoice_payment(
        self, cli_sender, cli_receiver, amount, ctype, udt_script
    ):
        preimage = self.generate_random_preimage()
        inv_kwargs = {
            "amount": amount,
            "currency": "Fibd",
            "description": f"gen-{ctype}-{random.randint(1000,9999)}",
            "payment_preimage": preimage,
            "hash_algorithm": "sha256",
        }
        if ctype == "UDT":
            inv_kwargs["udt_type_script"] = udt_script
        invoice = cli_receiver.new_invoice(**inv_kwargs)
        assert "invoice_address" in invoice, f"new_invoice failed: {invoice}"

        result = cli_sender.send_payment(invoice=invoice["invoice_address"])
        assert "payment_hash" in result, f"invoice payment failed: {result}"
        self.wait_payment_state(self.fiber1, result["payment_hash"], "Success")
        return result["payment_hash"]
