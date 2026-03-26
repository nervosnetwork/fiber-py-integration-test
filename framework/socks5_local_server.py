"""
Minimal SOCKS5 (RFC 1928 / 1929) TCP server for local integration tests.

Used by PR #1228 (outbound P2P over SOCKS5 / Tor) to verify that Fiber
actually dials peers through the configured proxy.
"""

from __future__ import annotations

import socket
import struct
import threading
from typing import Any, Dict


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("unexpected EOF")
        buf += chunk
    return buf


def _pipe(src: socket.socket, dst: socket.socket) -> None:
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass


def _handle_client(client: socket.socket, stats: Dict[str, Any]) -> None:
    remote: socket.socket | None = None
    try:
        ver, nmethods = struct.unpack("!BB", _recv_exact(client, 2))
        if ver != 5:
            return
        methods = _recv_exact(client, nmethods)

        if 0 in methods:
            client.sendall(b"\x05\x00")
        elif 2 in methods:
            client.sendall(b"\x05\x02")
            sub_ver = struct.unpack("B", _recv_exact(client, 1))[0]
            if sub_ver != 1:
                return
            ulen = struct.unpack("B", _recv_exact(client, 1))[0]
            _recv_exact(client, ulen)
            plen = struct.unpack("B", _recv_exact(client, 1))[0]
            _recv_exact(client, plen)
            client.sendall(b"\x01\x00")
        else:
            client.sendall(b"\x05\xff")
            return

        ver, cmd, _, atyp = struct.unpack("!BBBB", _recv_exact(client, 4))
        if ver != 5 or cmd != 1:
            return

        if atyp == 1:
            host = socket.inet_ntoa(_recv_exact(client, 4))
            port = struct.unpack("!H", _recv_exact(client, 2))[0]
        elif atyp == 3:
            ln = struct.unpack("B", _recv_exact(client, 1))[0]
            name = _recv_exact(client, ln).decode("ascii", errors="replace")
            port = struct.unpack("!H", _recv_exact(client, 2))[0]
            infos = socket.getaddrinfo(name, port, socket.AF_INET, socket.SOCK_STREAM)
            host = infos[0][4][0]
        else:
            return

        remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote.settimeout(120)
        try:
            remote.connect((host, port))
        except OSError:
            client.sendall(
                b"\x05\x05\x00\x01" + socket.inet_aton("0.0.0.0") + struct.pack("!H", 0)
            )
            return

        client.sendall(
            b"\x05\x00\x00\x01" + socket.inet_aton("0.0.0.0") + struct.pack("!H", 0)
        )
        stats["connects"] = stats.get("connects", 0) + 1

        t1 = threading.Thread(target=_pipe, args=(client, remote), daemon=True)
        t2 = threading.Thread(target=_pipe, args=(remote, client), daemon=True)
        t1.start()
        t2.start()
        t1.join(timeout=300)
        t2.join(timeout=1)
    except (ConnectionError, struct.error, OSError):
        pass
    finally:
        try:
            client.close()
        except OSError:
            pass
        if remote is not None:
            try:
                remote.close()
            except OSError:
                pass


class LocalSocks5Server:
    """Binds 127.0.0.1:0; use ``port`` after ``start()``."""

    def __init__(self) -> None:
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self.port: int | None = None
        self.stats: Dict[str, Any] = {"connects": 0}

    def start(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        sock.listen(64)
        sock.settimeout(0.5)
        self._sock = sock
        self.port = sock.getsockname()[1]
        self._running = True

        def accept_loop() -> None:
            assert self._sock is not None
            while self._running:
                try:
                    conn, _ = self._sock.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                conn.settimeout(300)
                threading.Thread(
                    target=_handle_client,
                    args=(conn, self.stats),
                    daemon=True,
                ).start()

        self._thread = threading.Thread(target=accept_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
