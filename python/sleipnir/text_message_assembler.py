# SPDX-License-Identifier: GPL-3.0-or-later
"""Python analogue of gnuradio4 TextMessageAssembler (offline / tooling)."""

from __future__ import annotations

from typing import List, Optional

from . import frame_format


class TextMessageAssembler:
    def __init__(
        self,
        src_callsign: str = "N0CALL",
        enable_signing: bool = False,
        enable_encryption: bool = False,
    ) -> None:
        self.src_callsign = src_callsign
        self.enable_signing = enable_signing
        self.enable_encryption = enable_encryption
        self._msg_seq = 1

    def assemble(
        self,
        text: str,
        dst: str = "ALL",
        src: Optional[str] = None,
    ) -> List[bytes]:
        """
        Fragment UTF-8 text into 64-byte TEXT frames.

        Returns a list of frame bytes suitable for SuperframeAssembler.text_frame_in
        or concatenation into a superframe TEXT trailer.
        """
        if self.enable_signing or self.enable_encryption:
            # Crypto requires gr-linux-crypto in C++; Python path is plaintext only.
            pass

        body = text[:800] if len(text) > 800 else text
        src_eff = (src or self.src_callsign).strip() or self.src_callsign
        msg_id = self._msg_seq
        self._msg_seq = 1 if self._msg_seq >= 65535 else self._msg_seq + 1

        n = len(body.encode("utf-8"))
        frag_total = 1 if n == 0 else (n + frame_format.TEXT_PAYLOAD_BYTES - 1) // frame_format.TEXT_PAYLOAD_BYTES
        raw = body.encode("utf-8")
        frames: List[bytes] = []

        for fi in range(frag_total):
            off = fi * frame_format.TEXT_PAYLOAD_BYTES
            chunk = raw[off : off + frame_format.TEXT_PAYLOAD_BYTES] if raw else b""
            frames.append(
                frame_format.build_text_frame(
                    src_eff,
                    dst,
                    msg_id,
                    fi,
                    frag_total,
                    chunk,
                )
            )
        return frames
