# SPDX-License-Identifier: GPL-3.0-or-later
"""Sleipnir voice/sync frame constants and assembly helpers (mirror of C++ SleipnirFrameFormat.hpp)."""

from __future__ import annotations

from typing import List

SYNC_PATTERN: int = 0xDEADBEEFCAFEBABE
VOICE_FRAME_SIZE: int = 49
SYNC_FRAME_SIZE: int = 49
OPUS_BYTES_PER_FRAME: int = 40
OPUS_STORED_BYTES: int = 39
MAC_BYTES: int = 8
FRAMES_PER_SUPERFRAME: int = 25
VOICE_FRAMES_PER_SF: int = 24
FRAME_TYPE_VOICE: int = 0x00
FRAME_TYPE_SYNC: int = 0xFF
FRAME_TYPE_TEXT: int = 0x02
TEXT_FRAME_BYTES: int = 64
TEXT_PAYLOAD_BYTES: int = 31
TEXT_TRAILER_MAGIC: bytes = b"TEXT"
TEXT_TRAILER_TAIL: int = 6  # MAGIC(4) + le16 length


def has_text_trailer(pdu: bytes) -> bool:
    if len(pdu) < TEXT_TRAILER_TAIL:
        return False
    return pdu[-6:-2] == TEXT_TRAILER_MAGIC


def split_voice_and_text_trailer(pdu: bytes) -> tuple[bytes, bytes]:
    """Return ``(voice_flat, text_concat)``. Invalid trailer parsing yields ``(pdu, b'')``."""
    n = len(pdu)
    if not has_text_trailer(pdu):
        return pdu, b""
    tl = pdu[-2] | (pdu[-1] << 8)
    if tl % TEXT_FRAME_BYTES != 0 or TEXT_TRAILER_TAIL + tl > n:
        return pdu, b""
    voice_len = n - TEXT_TRAILER_TAIL - tl
    return pdu[:voice_len], pdu[voice_len : voice_len + tl]


def append_text_trailer(voice_flat: bytes, text_concat: bytes) -> bytes:
    if not text_concat:
        return voice_flat
    out = bytearray(voice_flat)
    out.extend(text_concat)
    out.extend(TEXT_TRAILER_MAGIC)
    tl = len(text_concat)
    out.append(tl & 0xFF)
    out.append((tl >> 8) & 0xFF)
    return bytes(out)


def iter_text_frames(text_concat: bytes) -> List[bytes]:
    if not text_concat or len(text_concat) % TEXT_FRAME_BYTES != 0:
        return []
    return [text_concat[i : i + TEXT_FRAME_BYTES] for i in range(0, len(text_concat), TEXT_FRAME_BYTES)]


def build_voice_frame(opus_in: bytes, frame_num: int) -> bytes:
    """Return 49-byte voice frame; opus_in should be exactly 40 bytes (padded externally)."""
    buf = bytearray(VOICE_FRAME_SIZE)
    buf[0] = FRAME_TYPE_VOICE
    n = min(len(opus_in), OPUS_STORED_BYTES)
    buf[1 : 1 + n] = opus_in[:n]
    return bytes(buf)


def build_sync_frame(superframe_counter: int) -> bytes:
    """49-byte sync frame; pattern big-endian then counter BE at bytes 8-11."""
    buf = bytearray(SYNC_FRAME_SIZE)
    pat = SYNC_PATTERN
    for i in range(8):
        buf[i] = (pat >> (56 - i * 8)) & 0xFF
    c = superframe_counter & 0xFFFFFFFF
    buf[8] = (c >> 24) & 0xFF
    buf[9] = (c >> 16) & 0xFF
    buf[10] = (c >> 8) & 0xFF
    buf[11] = c & 0xFF
    return bytes(buf)


def is_sync_frame(data: bytes) -> bool:
    if len(data) < 8:
        return False
    pat = SYNC_PATTERN
    for i in range(8):
        if data[i] != ((pat >> (56 - i * 8)) & 0xFF):
            return False
    return True


def embed_callsign_marker(frame: bytearray, callsign: str) -> None:
    offset = 40
    n = min(len(callsign), 5)
    for i in range(5):
        frame[offset + i] = ord(callsign[i]) if i < n else ord(" ")


def assemble_frames(
    opus_data_960: bytes,
    callsign: str,
    prepend_sync: bool,
    superframe_counter: int,
) -> bytes:
    out = bytearray()
    if prepend_sync:
        out += build_sync_frame(superframe_counter)
    for f in range(VOICE_FRAMES_PER_SF):
        offset = f * OPUS_BYTES_PER_FRAME
        chunk = opus_data_960[offset : offset + OPUS_BYTES_PER_FRAME]
        padded = chunk.ljust(OPUS_BYTES_PER_FRAME, b"\x00")[:OPUS_BYTES_PER_FRAME]
        vf = bytearray(build_voice_frame(bytes(padded), f + 1))
        embed_callsign_marker(vf, callsign)
        out += vf
    return bytes(out)
