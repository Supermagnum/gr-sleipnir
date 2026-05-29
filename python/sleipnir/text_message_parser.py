# SPDX-License-Identifier: GPL-3.0-or-later
"""Python analogue of gnuradio4 TextMessageParser (offline / tooling)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from . import frame_format


@dataclass
class ParsedTextMessage:
    text: str
    src: str
    dst: str
    msg_id: int
    verified: bool = False
    decrypted: bool = False


@dataclass
class _Pending:
    frags: List[Optional[bytes]] = field(default_factory=list)
    total: int = 0
    last_mono: float = 0.0
    dst: str = ""


class TextMessageParser:
    def __init__(
        self,
        local_callsign: str = "N0CALL",
        timeout_s: float = 30.0,
        enable_verification: bool = False,
        enable_decryption: bool = False,
    ) -> None:
        self.local_callsign = local_callsign
        self.timeout_s = timeout_s
        self.enable_verification = enable_verification
        self.enable_decryption = enable_decryption
        self._partials: Dict[Tuple[bytes, int], _Pending] = {}
        self._emitted: Set[Tuple[bytes, int]] = set()

    def _purge_timeout(self, now: float) -> None:
        if self.timeout_s <= 0:
            return
        dead = [
            k
            for k, p in self._partials.items()
            if p.total and len([f for f in p.frags if f is not None]) < p.total
            and (now - p.last_mono) > self.timeout_s
        ]
        for k in dead:
            del self._partials[k]

    def _dest_ok(self, dst: str) -> bool:
        if dst == "ALL":
            return True
        local = frame_format.encode_callsign_bytes(self.local_callsign)
        enc = frame_format.encode_callsign_bytes(dst)
        return local == enc

    def feed_frame(self, frame: bytes) -> Optional[ParsedTextMessage]:
        """Ingest one 64-byte TEXT frame; returns a completed message or None."""
        now = time.monotonic()
        self._purge_timeout(now)
        parsed = frame_format.parse_text_frame(frame)
        if parsed is None:
            return None
        if not self._dest_ok(parsed["dst"]):
            return None

        src_key = frame[1:11]
        mid = int(parsed["msg_id"])
        key = (src_key, mid)
        if key in self._emitted:
            return None

        pend = self._partials.get(key)
        if pend is None:
            pend = _Pending(
                frags=[None] * int(parsed["fragment_total"]),
                total=int(parsed["fragment_total"]),
                last_mono=now,
                dst=parsed["dst"],
            )
            self._partials[key] = pend
        else:
            if pend.total != parsed["fragment_total"] or pend.dst != parsed["dst"]:
                return None

        fi = int(parsed["fragment_index"])
        if fi >= pend.total:
            return None
        pend.frags[fi] = parsed["payload"]
        pend.last_mono = now

        if any(f is None for f in pend.frags):
            return None

        text = b"".join(f or b"" for f in pend.frags).decode("utf-8", errors="replace")
        self._emitted.add(key)
        del self._partials[key]
        return ParsedTextMessage(
            text=text,
            src=parsed["src"],
            dst=pend.dst,
            msg_id=mid,
        )
