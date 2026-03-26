"""测试用本地 Tor：仅用命令行拉起进程，不写入 torrc。

未指定 ``-f`` 时 tor 会按系统惯例读取默认 ``torrc``；下列项由命令行覆盖：

``RunAsDaemon``、``SocksPort``、``ControlPort``、``HashedControlPassword``。

``data_dir`` 只用于把该子进程的 stdout/stderr 记到 ``tor.log``，不传 ``--DataDirectory``，
数据目录沿用系统 torrc。默认可执行文件为 PATH 中的 ``tor``。"""

from __future__ import annotations

import os
import re
import shutil
import signal
import socket
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Optional


def _resolve_tor(explicit: Optional[str]) -> str:
    p = explicit or shutil.which("tor")
    if not p:
        raise FileNotFoundError("未在 PATH 中找到 tor，请先安装（如 brew install tor）")
    return p


def _hash_control_password(tor_bin: str, password: str) -> str:
    proc = subprocess.run(
        [tor_bin, "--hash-password", password],
        capture_output=True,
        text=True,
        check=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("16:"):
            return s
    raise RuntimeError("tor --hash-password 无有效输出:\n" + out)


def _control_read_reply(rf: Any) -> list[str]:
    lines: list[str] = []
    while True:
        raw = rf.readline()
        if not raw:
            raise ConnectionError("control EOF")
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        lines.append(line)
        if line.startswith("515") or line.startswith("552"):
            return lines
        if len(line) >= 4 and line[:3].isdigit() and line[3] == " ":
            return lines


def _control_request(
    host: str, port: int, password: str, command: str, timeout: float = 10.0
) -> list[str]:
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        rf = sock.makefile("rb")
        sock.sendall(f'AUTHENTICATE "{password}"\r\n'.encode())
        auth = _control_read_reply(rf)
        if any(ln.startswith("515") for ln in auth):
            raise RuntimeError("Tor Control 认证失败")
        sock.sendall((command + "\r\n").encode())
        return _control_read_reply(rf)


def _control_getinfo(
    host: str, port: int, password: str, key: str, timeout: float = 10.0
) -> str:
    lines = _control_request(host, port, password, f"GETINFO {key}", timeout)
    prefix = f"250-{key}="
    for ln in lines:
        if ln.startswith(prefix):
            return ln[len(prefix) :]
    return ""


def _wait_tcp(host: str, port: int, timeout: float) -> None:
    deadline = time.time() + timeout
    last: Optional[OSError] = None
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2.0):
                return
        except OSError as e:
            last = e
            time.sleep(0.2)
    raise TimeoutError(f"{timeout}s 内无法连接 {host}:{port} ({last!r})")


def _wait_control(host: str, port: int, password: str, timeout: float) -> None:
    deadline = time.time() + timeout
    err: Optional[Exception] = None
    while time.time() < deadline:
        try:
            _control_request(host, port, password, "GETINFO version", timeout=5.0)
            return
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(0.3)
    raise TimeoutError(f"{timeout}s 内 Control 未就绪: {err!r}")


def _bootstrap_pct(phase: str) -> Optional[int]:
    m = re.search(r"PROGRESS=(\d+)", phase)
    if m:
        return int(m.group(1))
    if "TAG=done" in phase:
        return 100
    return None


def _wait_bootstrap(
    host: str, port: int, password: str, timeout: float, interval: float
) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            phase = _control_getinfo(host, port, password, "status/bootstrap-phase")
            p = _bootstrap_pct(phase)
            if p is not None and p >= 100:
                return
        except (OSError, RuntimeError):
            pass
        time.sleep(interval)
    raise TimeoutError(f"{timeout}s 内 Tor 未完成 bootstrap")


@dataclass
class TorDaemon:
    """data_dir：仅写子进程日志 tor.log（非 tor 的 DataDirectory）。"""

    data_dir: str
    control_password: str
    socks_port: int = 9050
    control_port: int = 9051
    tor_binary: Optional[str] = None
    extra_tor_args: Optional[list[str]] = None
    _proc: Optional[subprocess.Popen] = None
    _tor: str = field(init=False)
    _hashed: str = field(init=False)

    def __post_init__(self) -> None:
        self._tor = _resolve_tor(self.tor_binary)
        self._hashed = _hash_control_password(self._tor, self.control_password)

    def start(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        log_dir = os.path.abspath(self.data_dir)
        os.makedirs(log_dir, mode=0o700, exist_ok=True)
        args = [
            self._tor,
            "--RunAsDaemon",
            "0",
            "--SocksPort",
            str(self.socks_port),
            "--ControlPort",
            str(self.control_port),
            "--HashedControlPassword",
            self._hashed,
        ]
        if self.extra_tor_args:
            args.extend(self.extra_tor_args)
        log_f = open(os.path.join(log_dir, "tor.log"), "ab", buffering=0)
        self._proc = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    def wait_ready(
        self,
        host: str = "127.0.0.1",
        timeout: float = 60.0,
        wait_bootstrap: bool = False,
        bootstrap_timeout: float = 300.0,
    ) -> None:
        _wait_tcp(host, self.socks_port, timeout)
        _wait_control(host, self.control_port, self.control_password, timeout)
        if wait_bootstrap:
            _wait_bootstrap(
                host, self.control_port, self.control_password, bootstrap_timeout, 1.0
            )

    def stop(self, host: str = "127.0.0.1", timeout: float = 15.0) -> None:
        try:
            _control_request(
                host, self.control_port, self.control_password, "SIGNAL SHUTDOWN", 5.0
            )
        except (OSError, RuntimeError, ConnectionError):
            if self._proc:
                try:
                    self._proc.send_signal(signal.SIGTERM)
                except ProcessLookupError:
                    pass
        if self._proc:
            try:
                self._proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5.0)
            self._proc = None
