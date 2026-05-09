# SPDX-License-Identifier: GPL-3.0-or-later
"""Python analogue of gnuradio4 SuperframeParser (offline / CI)."""

from __future__ import annotations

from typing import Dict, List, Tuple

from . import frame_format


class SuperframeParser:
    def __init__(
        self,
        local_callsign: str = "N0CALL",
        require_signatures: bool = False,
        enable_sync_detection: bool = True,
        mac_key: bytes | None = None,
    ) -> None:
        self.local_callsign = local_callsign
        self.require_signatures = require_signatures
        self.enable_sync_detection = enable_sync_detection
        self.mac_key = mac_key or b""
        self.frame_error_count: int = 0
        self.total_frames_received: int = 0
        self._sync_detected: bool = False

    def reset(self) -> None:
        self.frame_error_count = 0
        self.total_frames_received = 0
        self._sync_detected = False

    def parse(self, pdu_bytes: bytes) -> Tuple[bytes, Dict[str, object], List[bytes]]:
        """
        Parse superframe pdu. Returns ``(opus_aggregate, status_dict, text_frames)``.
        ``opus_aggregate`` concatenates OPUS_STORED_BYTES (39) payload bytes per good voice frame.

        ``text_frames`` is a list of 64-byte chunks from an optional TEXT trailer
        (matches the C++ SuperframeParser ``text_frame_out`` path).
        """
        if self.require_signatures:
            raise NotImplementedError(
                "parse(): require_signatures is not implemented in Python analogue."
            )
        _ = self.local_callsign
        _ = self.mac_key

        voice_flat, text_concat = frame_format.split_voice_and_text_trailer(bytes(pdu_bytes))
        text_frames: List[bytes] = frame_format.iter_text_frames(text_concat)
        raw = voice_flat
        frame_sz = frame_format.VOICE_FRAME_SIZE

        if not raw or len(raw) % frame_sz != 0:
            fer = (
                float(self.frame_error_count) / float(self.total_frames_received)
                if self.total_frames_received > 0
                else 0.0
            )
            return b"", {
                "fer": round(fer, 6),
                "frame_errors": self.frame_error_count,
                "total_frames": self.total_frames_received,
                "sync_detected": self._sync_detected,
            }, text_frames

        sync_this_call = False
        opus_out = bytearray()
        errors_this_call = 0
        nf = len(raw) // frame_sz

        for fi in range(nf):
            chunk = raw[fi * frame_sz : (fi + 1) * frame_sz]

            if self.enable_sync_detection and frame_format.is_sync_frame(chunk):
                sync_this_call = True
                self._sync_detected = True
                self.total_frames_received += 1
                continue

            self.total_frames_received += 1
            if chunk[0] != frame_format.FRAME_TYPE_VOICE:
                self.frame_error_count += 1
                errors_this_call += 1
                continue

            opus_out.extend(chunk[1 : 1 + frame_format.OPUS_STORED_BYTES])

        fer_all = (
            float(self.frame_error_count) / float(self.total_frames_received)
            if self.total_frames_received > 0
            else 0.0
        )
        stats: Dict[str, object] = {
            "fer": round(fer_all, 6),
            "frame_errors": self.frame_error_count,
            "total_frames": self.total_frames_received,
            "sync_detected": bool(sync_this_call or self._sync_detected),
            "errors_this_superframe": errors_this_call,
        }
        return bytes(opus_out), stats, text_frames
