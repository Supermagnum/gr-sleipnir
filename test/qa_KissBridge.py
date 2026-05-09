# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for python/sleipnir/kiss_bridge.py (M17 KISS full packet mode, port 1)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PY = _REPO_ROOT / "python"
if str(_PY) not in sys.path:
    sys.path.insert(0, str(_PY))

from sleipnir.kiss_bridge import (  # noqa: E402
    FEND,
    M17_KISS_TYPE_BYTE,
    TEXT_FRAME_BYTES,
    SleipnirKissBridge,
)


def test_callsign_encode_decode_roundtrip() -> None:
    bridge = SleipnirKissBridge()
    for cs in ("N0CALL", "K1ABC", "W1AW"):
        raw = bridge.encode_m17_callsign(cs)
        assert len(raw) == 10
        assert bridge.decode_m17_callsign(raw) == cs


def test_broadcast_address() -> None:
    bridge = SleipnirKissBridge()
    b = bridge.encode_m17_callsign("ALL")
    assert b == bytes([0xFF]) * 10
    assert bridge.decode_m17_callsign(b) == "ALL"


def test_kiss_type_byte_is_port1_data_command() -> None:
    # M17 KISS appendix: port in high nibble, command 0 for user data.
    assert M17_KISS_TYPE_BYTE == 0x10


def test_sleipnir_to_kiss_round_trip() -> None:
    bridge = SleipnirKissBridge()
    frame = bytearray(TEXT_FRAME_BYTES)
    frame[0] = 0x02
    frame[1:11] = bridge.encode_m17_callsign("SRC")
    frame[11:21] = bridge.encode_m17_callsign("DST")
    kiss = bridge.sleipnir_to_kiss(bytes(frame))
    assert kiss[0] == FEND and kiss[-1] == FEND
    back = bridge.kiss_to_sleipnir(kiss)
    assert back == bytes(frame)


def test_kiss_malformed_no_end_marker_raises() -> None:
    bridge = SleipnirKissBridge()
    frame = bytes([0x02]) + bytes(TEXT_FRAME_BYTES - 1)
    kiss = bridge.sleipnir_to_kiss(frame.ljust(TEXT_FRAME_BYTES, b"\x00"))
    bad = kiss[:-1]
    with pytest.raises(ValueError, match="missing end marker"):
        bridge.kiss_to_sleipnir(bad)
