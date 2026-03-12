import json
import os
import subprocess
import logging

import yaml

from framework.util import get_project_root

LOGGER = logging.getLogger(__name__)


class FnnCli:
    """Helper to invoke fnn-cli binary and parse its output."""

    def __init__(self, rpc_url, bin_path=None, auth_token=None, auth_token_file=None):
        if bin_path is None:
            bin_path = f"{get_project_root()}/download/fiber/current/fnn-cli"
        if auth_token is not None and auth_token_file is not None:
            raise ValueError(
                "auth_token and auth_token_file are mutually exclusive"
            )
        self.bin_path = bin_path
        self.rpc_url = rpc_url
        self.auth_token = auth_token
        self.auth_token_file = auth_token_file

    def _run(self, args, output_format="json", raw_data=False, timeout=30, env_override=None):
        cmd = [
            self.bin_path,
            "--url",
            self.rpc_url,
            "--output-format",
            output_format,
            "--color",
            "never",
        ]
        if self.auth_token is not None:
            cmd.extend(["--auth-token", self.auth_token])
        if self.auth_token_file is not None:
            cmd.extend(["--auth-token-file", self.auth_token_file])
        if raw_data:
            cmd.append("--raw-data")
        cmd.extend(args)

        LOGGER.debug("fnn-cli cmd: %s", " ".join(cmd))
        run_env = None
        if env_override:
            run_env = os.environ.copy()
            run_env.update(env_override)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=run_env,
        )
        LOGGER.debug("fnn-cli stdout: %s", result.stdout)
        if result.returncode != 0:
            LOGGER.debug("fnn-cli stderr: %s", result.stderr)
            raise Exception(
                f"fnn-cli failed (exit {result.returncode}): {result.stderr.strip()}"
            )
        return result.stdout.strip()

    def _run_json(self, args, **kwargs):
        out = self._run(args, output_format="json", **kwargs)
        if not out:
            return None
        return json.loads(out)

    def _run_yaml(self, args, **kwargs):
        out = self._run(args, output_format="yaml", **kwargs)
        if not out:
            return None
        return yaml.safe_load(out)

    # ── info ──────────────────────────────────────────────────────────
    def node_info(self):
        return self._run_json(["info", "node_info"])

    # ── peer ──────────────────────────────────────────────────────────
    def connect_peer(self, address, save=None):
        args = ["peer", "connect_peer", "--address", address]
        if save is not None:
            args.extend(["--save", str(save).lower()])
        return self._run_json(args)

    def disconnect_peer(self, peer_id):
        return self._run_json(["peer", "disconnect_peer", "--peer-id", peer_id])

    def list_peers(self):
        return self._run_json(["peer", "list_peers"])

    # ── channel ───────────────────────────────────────────────────────
    def open_channel(self, peer_id, funding_amount, **kwargs):
        args = [
            "channel",
            "open_channel",
            "--peer-id",
            peer_id,
            "--funding-amount",
            str(funding_amount),
        ]
        flag_map = {
            "public": "--public",
            "one_way": "--one-way",
        }
        str_map = {
            "funding_udt_type_script": "--funding-udt-type-script",
            "shutdown_script": "--shutdown-script",
            "commitment_delay_epoch": "--commitment-delay-epoch",
            "commitment_fee_rate": "--commitment-fee-rate",
            "funding_fee_rate": "--funding-fee-rate",
            "tlc_expiry_delta": "--tlc-expiry-delta",
            "tlc_min_value": "--tlc-min-value",
            "tlc_fee_proportional_millionths": "--tlc-fee-proportional-millionths",
            "max_tlc_value_in_flight": "--max-tlc-value-in-flight",
            "max_tlc_number_in_flight": "--max-tlc-number-in-flight",
        }
        for k, flag in flag_map.items():
            if k in kwargs:
                args.extend([flag, str(kwargs[k]).lower()])
        for k, flag in str_map.items():
            if k in kwargs:
                val = kwargs[k]
                args.extend(
                    [flag, json.dumps(val) if isinstance(val, dict) else str(val)]
                )
        return self._run_json(args)

    def accept_channel(self, temporary_channel_id, funding_amount, **kwargs):
        args = [
            "channel",
            "accept_channel",
            "--temporary-channel-id",
            temporary_channel_id,
            "--funding-amount",
            str(funding_amount),
        ]
        str_map = {
            "shutdown_script": "--shutdown-script",
            "max_tlc_value_in_flight": "--max-tlc-value-in-flight",
            "max_tlc_number_in_flight": "--max-tlc-number-in-flight",
            "tlc_min_value": "--tlc-min-value",
            "tlc_fee_proportional_millionths": "--tlc-fee-proportional-millionths",
            "tlc_expiry_delta": "--tlc-expiry-delta",
        }
        for k, flag in str_map.items():
            if k in kwargs:
                val = kwargs[k]
                args.extend(
                    [flag, json.dumps(val) if isinstance(val, dict) else str(val)]
                )
        return self._run_json(args)

    def list_channels(self, peer_id=None, include_closed=None, only_pending=None):
        args = ["channel", "list_channels"]
        if peer_id is not None:
            args.extend(["--peer-id", peer_id])
        if include_closed is not None:
            args.extend(["--include-closed", str(include_closed).lower()])
        if only_pending is not None:
            args.extend(["--only-pending", str(only_pending).lower()])
        return self._run_json(args)

    def shutdown_channel(
        self, channel_id, close_script=None, fee_rate=None, force=None
    ):
        args = ["channel", "shutdown_channel", "--channel-id", channel_id]
        if close_script is not None:
            args.extend(["--close-script", json.dumps(close_script)])
        if fee_rate is not None:
            args.extend(["--fee-rate", str(fee_rate)])
        if force is not None:
            args.extend(["--force", str(force).lower()])
        return self._run_json(args)

    def update_channel(self, channel_id, **kwargs):
        args = ["channel", "update_channel", "--channel-id", channel_id]
        str_map = {
            "enabled": "--enabled",
            "tlc_expiry_delta": "--tlc-expiry-delta",
            "tlc_minimum_value": "--tlc-minimum-value",
            "tlc_fee_proportional_millionths": "--tlc-fee-proportional-millionths",
        }
        for k, flag in str_map.items():
            if k in kwargs:
                args.extend(
                    [
                        flag,
                        (
                            str(kwargs[k]).lower()
                            if isinstance(kwargs[k], bool)
                            else str(kwargs[k])
                        ),
                    ]
                )
        return self._run_json(args)

    def abandon_channel(self, channel_id):
        return self._run_json(
            ["channel", "abandon_channel", "--channel-id", channel_id]
        )

    # ── invoice ───────────────────────────────────────────────────────
    def new_invoice(self, amount, currency, **kwargs):
        args = [
            "invoice",
            "new_invoice",
            "--amount",
            str(amount),
            "--currency",
            currency,
        ]
        str_map = {
            "description": "--description",
            "payment_preimage": "--payment-preimage",
            "payment_hash": "--payment-hash",
            "expiry": "--expiry",
            "fallback_address": "--fallback-address",
            "final_expiry_delta": "--final-expiry-delta",
            "udt_type_script": "--udt-type-script",
            "hash_algorithm": "--hash-algorithm",
        }
        flag_map = {
            "allow_mpp": "--allow-mpp",
            "allow_trampoline_routing": "--allow-trampoline-routing",
        }
        for k, flag in str_map.items():
            if k in kwargs:
                val = kwargs[k]
                args.extend(
                    [flag, json.dumps(val) if isinstance(val, dict) else str(val)]
                )
        for k, flag in flag_map.items():
            if k in kwargs:
                args.extend([flag, str(kwargs[k]).lower()])
        return self._run_json(args)

    def parse_invoice(self, invoice):
        return self._run_json(["invoice", "parse_invoice", "--invoice", invoice])

    def get_invoice(self, payment_hash):
        return self._run_json(
            ["invoice", "get_invoice", "--payment-hash", payment_hash]
        )

    def cancel_invoice(self, payment_hash):
        return self._run_json(
            ["invoice", "cancel_invoice", "--payment-hash", payment_hash]
        )

    def settle_invoice(self, payment_hash, payment_preimage):
        return self._run_json(
            [
                "invoice",
                "settle_invoice",
                "--payment-hash",
                payment_hash,
                "--payment-preimage",
                payment_preimage,
            ]
        )

    # ── payment ───────────────────────────────────────────────────────
    def send_payment(self, **kwargs):
        args = ["payment", "send_payment"]
        str_map = {
            "target_pubkey": "--target-pubkey",
            "amount": "--amount",
            "payment_hash": "--payment-hash",
            "final_tlc_expiry_delta": "--final-tlc-expiry-delta",
            "tlc_expiry_limit": "--tlc-expiry-limit",
            "invoice": "--invoice",
            "timeout": "--timeout",
            "max_fee_amount": "--max-fee-amount",
            "max_fee_rate": "--max-fee-rate",
            "max_parts": "--max-parts",
            "udt_type_script": "--udt-type-script",
            "trampoline_hops": "--trampoline-hops",
            "custom_records": "--custom-records",
            "hop_hints": "--hop-hints",
        }
        flag_map = {
            "keysend": "--keysend",
            "allow_self_payment": "--allow-self-payment",
            "dry_run": "--dry-run",
        }
        for k, flag in str_map.items():
            if k in kwargs:
                val = kwargs[k]
                args.extend(
                    [
                        flag,
                        json.dumps(val) if isinstance(val, (dict, list)) else str(val),
                    ]
                )
        for k, flag in flag_map.items():
            if k in kwargs:
                args.extend([flag, str(kwargs[k]).lower()])
        return self._run_json(args)

    def get_payment(self, payment_hash):
        return self._run_json(
            ["payment", "get_payment", "--payment-hash", payment_hash]
        )

    def list_payments(self, status=None, limit=None, after=None):
        args = ["payment", "list_payments"]
        if status is not None:
            args.extend(["--status", status])
        if limit is not None:
            args.extend(["--limit", str(limit)])
        if after is not None:
            args.extend(["--after", after])
        return self._run_json(args)

    def build_router(self, hops_info, amount=None, udt_type_script=None, final_tlc_expiry_delta=None):
        args = ["payment", "build_router", "--hops-info", json.dumps(hops_info)]
        if amount is not None:
            args.extend(["--amount", str(amount)])
        if udt_type_script is not None:
            args.extend(["--udt-type-script", json.dumps(udt_type_script)])
        if final_tlc_expiry_delta is not None:
            args.extend(["--final-tlc-expiry-delta", str(final_tlc_expiry_delta)])
        return self._run_json(args)

    def send_payment_with_router(self, router, **kwargs):
        args = ["payment", "send_payment_with_router", "--router", json.dumps(router)]
        str_map = {
            "payment_hash": "--payment-hash",
            "invoice": "--invoice",
            "custom_records": "--custom-records",
        }
        flag_map = {
            "keysend": "--keysend",
            "dry_run": "--dry-run",
        }
        for k, flag in str_map.items():
            if k in kwargs:
                val = kwargs[k]
                args.extend(
                    [flag, json.dumps(val) if isinstance(val, (dict, list)) else str(val)]
                )
        for k, flag in flag_map.items():
            if k in kwargs:
                args.extend([flag, str(kwargs[k]).lower()])
        return self._run_json(args)

    # ── graph ─────────────────────────────────────────────────────────
    def graph_nodes(self, limit=None, after=None):
        args = ["graph", "graph_nodes"]
        if limit is not None:
            args.extend(["--limit", str(limit)])
        if after is not None:
            args.extend(["--after", after])
        return self._run_json(args)

    def graph_channels(self, limit=None, after=None):
        args = ["graph", "graph_channels"]
        if limit is not None:
            args.extend(["--limit", str(limit)])
        if after is not None:
            args.extend(["--after", after])
        return self._run_json(args)

    # ── dev ──────────────────────────────────────────────────────────
    def add_tlc(self, channel_id, amount, payment_hash, expiry):
        args = [
            "dev",
            "add_tlc",
            "--channel-id",
            channel_id,
            "--amount",
            str(amount),
            "--payment-hash",
            payment_hash,
            "--expiry",
            str(expiry),
        ]
        return self._run_json(args)

    def remove_tlc(self, channel_id, tlc_id, reason):
        args = [
            "dev",
            "remove_tlc",
            "--channel-id",
            channel_id,
            "--tlc-id",
            str(tlc_id),
            "--reason",
            json.dumps(reason) if isinstance(reason, dict) else str(reason),
        ]
        return self._run_json(args)

    # ── raw output ────────────────────────────────────────────────────
    def run_raw(self, args, env_override=None):
        """Run arbitrary fnn-cli args and return raw stdout."""
        return self._run(args, env_override=env_override)

    def run_yaml(self, args, env_override=None):
        """Run arbitrary fnn-cli args and return parsed YAML."""
        return self._run_yaml(args, env_override=env_override)
