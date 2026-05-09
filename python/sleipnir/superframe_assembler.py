# SPDX-License-Identifier: GPL-3.0-or-later
"""Python analogue of gnuradio4 SuperframeAssembler (opcode-free, for tooling and offline tests)."""

from __future__ import annotations

from . import frame_format


class SuperframeAssembler:
    def __init__(
        self,
        callsign: str = "N0CALL",
        enable_signing: bool = False,
        private_key_path: str = "",
        enable_sync_frames: bool = True,
        sync_frame_interval: int = 5,
    ) -> None:
        self.callsign = callsign
        self.enable_signing = enable_signing
        self.private_key_path = private_key_path
        self.enable_sync_frames = enable_sync_frames
        self.sync_frame_interval = int(sync_frame_interval)
        self._superframe_counter: int = 0

    def reset(self) -> None:
        self._superframe_counter = 0

    def assemble(self, opus_pdu_bytes: bytes, text_frames_concat: bytes = b"") -> bytes:
        """
        opus_pdu_bytes: concatenation of exactly 24 * 40 = 960 bytes (Opus packet bytes).
        Returns assembled superframe pdu_bytes (without signing frame; matches C++ when signing off).
        """
        if len(opus_pdu_bytes) < frame_format.OPUS_BYTES_PER_FRAME * frame_format.VOICE_FRAMES_PER_SF:
            opus_pdu_bytes = opus_pdu_bytes.ljust(
                frame_format.OPUS_BYTES_PER_FRAME * frame_format.VOICE_FRAMES_PER_SF, b"\x00"
            )

        opus_pdu_bytes = opus_pdu_bytes[
            : frame_format.OPUS_BYTES_PER_FRAME * frame_format.VOICE_FRAMES_PER_SF
        ]

        if self.enable_signing:
            # C++ inserts auth frame only with OpenSSL; Python path keeps behaviour explicit.
            raise NotImplementedError(
                "assemble(): enable_signing is not implemented in Python; use C++/OpenSSL blocks."
            )

        interval = int(self.sync_frame_interval) if self.enable_sync_frames else 0
        prepend_sync = bool(
            self.enable_sync_frames
            and interval > 0
            and (self._superframe_counter % interval == 0)
        )

        out = frame_format.assemble_frames(
            opus_pdu_bytes,
            self.callsign,
            prepend_sync,
            self._superframe_counter & 0xFFFFFFFF,
        )
        self._superframe_counter = (self._superframe_counter + 1) & 0xFFFFFFFF
        return frame_format.append_text_trailer(out, text_frames_concat)
