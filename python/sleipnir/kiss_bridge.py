# SPDX-License-Identifier: GPL-3.0-or-later
"""M17 KISS TNC adapter for sleipnir 64-byte TEXT frames (full packet mode, port 1)."""

from __future__ import annotations

import threading
from typing import Callable, Optional

FEND = 0xC0
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD

_FULL_PACKET_PORT = 1
_TYPE_DATA = 0x00
M17_KISS_TYPE_BYTE = (_FULL_PACKET_PORT << 4) | _TYPE_DATA
LSF_SIZE = 30
TEXT_FRAME_BYTES = 64


def _kiss_escape(raw: bytes) -> bytes:
    out = bytearray()
    for b in raw:
        if b == FEND:
            out.extend((FESC, TFEND))
        elif b == FESC:
            out.extend((FESC, TFESC))
        else:
            out.append(b)
    return bytes(out)


def _kiss_unescape(escaped: bytes) -> bytes:
    out = bytearray()
    i = 0
    n = len(escaped)
    while i < n:
        if escaped[i] == FESC and i + 1 < n:
            nxt = escaped[i + 1]
            if nxt == TFEND:
                out.append(FEND)
            elif nxt == TFESC:
                out.append(FESC)
            else:
                out.extend((FESC, nxt))
            i += 2
            continue
        out.append(escaped[i])
        i += 1
    return bytes(out)


class SleipnirKissBridge:
    """
    Bridges gr-sleipnir text frames to/from M17 KISS TNC format.

    M17 appendix: full packet mode uses KISS port 1. The KISS type indicator
    is ``(port << 4) | command`` (high nibble port, low nibble command 0 for
    payload), so port 1 yields type byte ``0x10``.

    The modem payload is ``LSF (30 bytes) + host packet data``. For sleipnir
    interoperability the host packet data is exactly one 64-byte TEXT frame.
    """

    def __init__(
        self,
        zmq_pub_endpoint: str = "tcp://*:17000",
        zmq_sub_endpoint: str = "tcp://localhost:17001",
        lsf_builder: Optional[Callable[[bytes], bytes]] = None,
    ) -> None:
        self._zmq_pub = zmq_pub_endpoint
        self._zmq_sub = zmq_sub_endpoint
        self._lsf_builder = lsf_builder
        self._pub_thread: Optional[threading.Thread] = None
        self._sub_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    @staticmethod
    def encode_m17_callsign(callsign: str) -> bytes:
        alphabet = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-/"
        if not callsign or callsign.upper() in ("ALL", "BROADCAST"):
            return bytes([0xFF]) * 10
        norm = []
        for ch in callsign.upper():
            if len(norm) >= 9:
                break
            norm.append(ch)
        while len(norm) < 9:
            norm.append(" ")
        vals = [alphabet.index(ch) for ch in norm]
        acc = 0
        for i in range(9):
            acc = acc * 40 + vals[8 - i]
        out = bytearray(10)
        for i in range(6):
            out[i] = (acc >> (8 * (5 - i))) & 0xFF
        return bytes(out)

    @staticmethod
    def decode_m17_callsign(encoded: bytes) -> str:
        alphabet = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-/"
        if len(encoded) < 10:
            return ""
        if encoded[:10] == bytes([0xFF]) * 10:
            return "ALL"
        acc = 0
        for i in range(6):
            acc = (acc << 8) | encoded[i]
        vals = []
        tmp = acc
        for _ in range(9):
            vals.append(int(tmp % 40))
            tmp //= 40
        s = "".join(alphabet[v] for v in vals)
        return s.rstrip()

    def _make_lsf(self, text_frame: bytes) -> bytes:
        if self._lsf_builder is not None:
            return self._lsf_builder(text_frame).ljust(LSF_SIZE, b"\x00")[:LSF_SIZE]
        dst = text_frame[1:11]
        src = text_frame[11:21]
        lsf = bytearray(LSF_SIZE)
        lsf[0:6] = dst[:6]
        lsf[6:12] = src[:6]
        return bytes(lsf)

    def sleipnir_to_kiss(self, text_frame: bytes) -> bytes:
        """Convert gr-sleipnir 64-byte text frame to one M17 KISS-framed full-packet message."""
        if len(text_frame) != TEXT_FRAME_BYTES:
            raise ValueError("text_frame must be exactly 64 bytes")
        inner = bytes([M17_KISS_TYPE_BYTE]) + self._make_lsf(text_frame) + text_frame
        escaped = _kiss_escape(inner)
        return bytes([FEND]) + escaped + bytes([FEND])

    def kiss_to_sleipnir(self, kiss_frame: bytes) -> bytes:
        """Decode a KISS frame and return the embedded 64-byte sleipnir TEXT frame."""
        kiss_frame = bytes(kiss_frame).strip()
        if len(kiss_frame) < 3 or kiss_frame[0] != FEND:
            raise ValueError("invalid KISS frame opening")
        if kiss_frame[-1] != FEND:
            raise ValueError("malformed KISS frame (missing end marker)")
        escaped = kiss_frame[1:-1]
        inner = _kiss_unescape(escaped)
        if len(inner) < 1 + LSF_SIZE + TEXT_FRAME_BYTES:
            raise ValueError("KISS payload too short for LSF + text frame")
        pkt = inner[1 + LSF_SIZE :]
        if len(pkt) < TEXT_FRAME_BYTES:
            raise ValueError("truncated text frame payload")
        return pkt[:TEXT_FRAME_BYTES]

    def start_zmq_bridge(self) -> None:
        """Start ZeroMQ PUB/SUB bridge threads for LinHT-style IPC (optional dependency: pyzmq)."""
        try:
            import zmq  # type: ignore import-not-found
        except ImportError as exc:
            raise ImportError("start_zmq_bridge requires pyzmq installed") from exc
        self._stop.clear()

        def pub_worker() -> None:
            ctx = zmq.Context.instance()
            sock = ctx.socket(zmq.PUB)
            sock.bind(self._zmq_pub)
            assert sock is not None
            while not self._stop.is_set():
                # Placeholder: application should push frames via IPC; this keeps socket open.
                self._stop.wait(timeout=0.25)

        def sub_worker() -> None:
            ctx = zmq.Context.instance()
            sock = ctx.socket(zmq.SUB)
            sock.connect(self._zmq_sub)
            sock.setsockopt(zmq.SUBSCRIBE, b"")
            sock.setsockopt(zmq.RCVTIMEO, 250)
            while not self._stop.is_set():
                try:
                    sock.recv(flags=zmq.NOBLOCK)
                except Exception:
                    continue

        self._pub_thread = threading.Thread(target=pub_worker, name="sleipnir-kiss-pub", daemon=True)
        self._sub_thread = threading.Thread(target=sub_worker, name="sleipnir-kiss-sub", daemon=True)
        self._pub_thread.start()
        self._sub_thread.start()

    def stop_zmq_bridge(self) -> None:
        self._stop.set()
        if self._pub_thread is not None:
            self._pub_thread.join(timeout=2.0)
        if self._sub_thread is not None:
            self._sub_thread.join(timeout=2.0)
        self._pub_thread = None
        self._sub_thread = None
