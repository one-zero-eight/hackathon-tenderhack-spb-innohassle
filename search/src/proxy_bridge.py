"""Local HTTP proxy bridge for SOCKS5 proxies with auth (macOS CloakBrowser)."""

from __future__ import annotations

import asyncio
import logging
import socket
import subprocess
import sys
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def socks5_proxy_has_auth(raw: str | None) -> bool:
    if not raw:
        return False
    value = raw.strip()
    if "://" not in value:
        value = f"socks5://{value}"
    parsed = urlparse(value)
    return parsed.scheme.lower() in ("socks5", "socks5h") and bool(parsed.username)


def needs_socks_proxy_bridge(raw: str | None) -> bool:
    return sys.platform == "darwin" and socks5_proxy_has_auth(raw)


def pproxy_remote_url(raw: str) -> str:
    value = raw.strip()
    if "://" not in value:
        value = f"socks5://{value}"
    parsed = urlparse(value)
    host = parsed.hostname or ""
    port = parsed.port or 1080
    if parsed.username:
        return f"socks5://{host}:{port}#{parsed.username}:{parsed.password or ''}"
    return f"socks5://{host}:{port}"


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass
class _BridgeEntry:
    local_url: str
    process: subprocess.Popen[bytes]
    refs: int = 0


class SocksProxyBridgeManager:
    def __init__(self) -> None:
        self._bridges: dict[str, _BridgeEntry] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, upstream: str) -> str:
        async with self._lock:
            entry = self._bridges.get(upstream)
            if entry is None:
                entry = await asyncio.to_thread(self._start_bridge, upstream)
                self._bridges[upstream] = entry
                logger.info(
                    "SOCKS5 proxy bridge: %s -> %s (pid=%s)",
                    _mask_proxy(upstream),
                    entry.local_url,
                    entry.process.pid,
                )
            entry.refs += 1
            return entry.local_url

    async def release(self, upstream: str | None) -> None:
        if not upstream:
            return
        async with self._lock:
            entry = self._bridges.get(upstream)
            if entry is None:
                return
            entry.refs -= 1
            if entry.refs > 0:
                return
            self._stop_entry(upstream, entry)

    async def shutdown_all(self) -> None:
        async with self._lock:
            for key, entry in list(self._bridges.items()):
                self._stop_entry(key, entry)

    def _start_bridge(self, upstream: str) -> _BridgeEntry:
        port = _free_local_port()
        process = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-m",
                "pproxy",
                "-l",
                f"http://127.0.0.1:{port}",
                "-r",
                pproxy_remote_url(upstream),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if not self._wait_until_ready(port, process):
            stderr = (process.stderr.read() if process.stderr else b"").decode(
                "utf-8",
                errors="replace",
            ).strip()
            raise RuntimeError(
                f"SOCKS5 proxy bridge failed on port {port}"
                + (f": {stderr}" if stderr else ""),
            )
        return _BridgeEntry(local_url=f"http://127.0.0.1:{port}", process=process)

    @staticmethod
    def _wait_until_ready(port: int, process: subprocess.Popen[bytes]) -> bool:
        for _ in range(40):
            if process.poll() is not None:
                return False
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                    return True
            except OSError:
                pass
        return process.poll() is None

    def _stop_entry(self, upstream: str, entry: _BridgeEntry) -> None:
        self._bridges.pop(upstream, None)
        if entry.process.poll() is None:
            entry.process.terminate()
            try:
                entry.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                entry.process.kill()


def _mask_proxy(raw: str) -> str:
    parsed = urlparse(raw if "://" in raw else f"socks5://{raw}")
    host = parsed.hostname or "?"
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://***@{host}{port}"


bridge_manager = SocksProxyBridgeManager()
