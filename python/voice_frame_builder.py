#!/usr/bin/env python3
"""
Voice Frame Builder for gr-sleipnir

Builds voice frame payloads (384 bits) from Opus audio and metadata.
Handles Opus encoding and frame segmentation.
"""

import struct
from typing import Optional
try:
    from .crypto_helpers import compute_chacha20_mac, get_callsign_bytes
except ImportError:
    from crypto_helpers import compute_chacha20_mac, get_callsign_bytes


class VoiceFrameBuilder:
    """
    Builds voice frame payloads for gr-sleipnir superframe.

    Each voice frame contains:
    - Opus voice: 320 bits (40 bytes)
    - ChaCha20-Poly1305 MAC: 128 bits (16 bytes)
    - Callsign: 40 bits (5 bytes)
    - Frame counter: 8 bits (1 byte)
    - Reserved: 24 bits (3 bytes)
    Total: 384 bits (48 bytes) before LDPC encoding
    """

    OPUS_BYTES = 40  # 320 bits
    MAC_BYTES = 8    # 64 bits (truncated from 128 bits to fit 48-byte payload)
    CALLSIGN_BYTES = 5  # 40 bits
    FRAME_COUNTER_BYTES = 1  # 8 bits
    RESERVED_BYTES = 0  # 0 bits (removed to fit 48-byte payload)
    TOTAL_PAYLOAD_BYTES = 48  # 384 bits (40 + 8 + 5 + 1 + 0 = 54, but we'll use 48)

    # Adjusted structure to fit 48 bytes:
    # Opus: 40 bytes (320 bits)
    # MAC: 8 bytes (64 bits) - truncated
    # Callsign: 5 bytes (40 bits) - but we'll use 3 bytes to fit
    # Counter: 1 byte (8 bits)
    # Total: 40 + 8 + 3 + 1 = 52 bytes...
    # Actually, let's use the spec: MAC is 16 bytes, so we need to adjust
    # Revised: Opus 40 + MAC 8 (truncated) = 48 bytes total
    # Or: Opus 32 + MAC 16 = 48 bytes

    def __init__(
        self,
        callsign: str = "N0CALL",
        mac_key: Optional[bytes] = None,
        enable_mac: bool = True
    ):
        """
        Initialize voice frame builder.

        Args:
            callsign: Station callsign (5 bytes max)
            mac_key: MAC key for ChaCha20-Poly1305 (32 bytes)
            enable_mac: Enable MAC computation
        """
        self.callsign = callsign[:5].upper().ljust(5)
        self.mac_key = mac_key
        self.enable_mac = enable_mac and (mac_key is not None)

    def build_frame(
        self,
        opus_data: bytes,
        frame_num: int
    ) -> bytes:
        """
        Build a voice frame payload.

        Args:
            opus_data: Opus-encoded audio (exactly 40 bytes)
            frame_num: Frame number within superframe (1-24)

        Returns:
            48-byte payload ready for LDPC encoding
        """
        # Accept 40-byte Opus input, truncate/pad to fit payload
        if len(opus_data) > self.OPUS_BYTES:
            opus_data = opus_data[:self.OPUS_BYTES]
        elif len(opus_data) < self.OPUS_BYTES:
            opus_data = opus_data.ljust(self.OPUS_BYTES, b'\x00')

        if frame_num < 1 or frame_num > 24:
            raise ValueError(f"Frame number must be 1-24, got {frame_num}")

        # Build payload (48 bytes total)
        payload = bytearray(self.TOTAL_PAYLOAD_BYTES)

        # Opus voice data (32 bytes, offset 0)
        payload[0:self.OPUS_BYTES] = opus_data[:self.OPUS_BYTES]

        # Compute MAC if enabled (covers Opus data + callsign + frame_counter)
        if self.enable_mac:
            mac_data = (
                opus_data[:self.OPUS_BYTES] +
                get_callsign_bytes(self.callsign) +
                bytes([frame_num])
            )
            mac = compute_chacha20_mac(mac_data, self.mac_key)
            payload[self.OPUS_BYTES:self.OPUS_BYTES + self.MAC_BYTES] = mac[:self.MAC_BYTES]
        else:
            # Zero MAC if disabled
            payload[self.OPUS_BYTES:self.OPUS_BYTES + self.MAC_BYTES] = b'\x00' * self.MAC_BYTES

        # Note: Callsign and frame counter are in metadata, not frame payload
        # This keeps payload at exactly 48 bytes (384 bits) for LDPC encoding

        return bytes(payload)

    def parse_frame(self, payload: bytes) -> dict:
        """
        Parse a voice frame payload.

        Args:
            payload: 48-byte payload (after LDPC decoding)

        Returns:
            Dictionary with parsed fields
        """
        if len(payload) != self.TOTAL_PAYLOAD_BYTES:
            raise ValueError(
                f"Payload must be exactly {self.TOTAL_PAYLOAD_BYTES} bytes, "
                f"got {len(payload)}"
            )

        return {
            'opus_data': payload[0:self.OPUS_BYTES],
            'mac': payload[self.OPUS_BYTES:self.OPUS_BYTES + self.MAC_BYTES],
            'callsign': self.callsign,  # From builder, not payload
            'frame_counter': 0,  # From metadata, not payload
            'reserved': b''
        }

    def verify_mac(self, payload: bytes) -> bool:
        """
        Verify MAC in voice frame payload.

        Args:
            payload: 48-byte payload

        Returns:
            True if MAC is valid, False otherwise
        """
        if not self.enable_mac or not self.mac_key:
            return True  # MAC verification disabled

        parsed = self.parse_frame(payload)

        # Recompute MAC
        mac_data = (
            parsed['opus_data'] +
            get_callsign_bytes(parsed['callsign']) +
            bytes([parsed['frame_counter']])
        )
        computed_mac = compute_chacha20_mac(mac_data, self.mac_key)

        return computed_mac == parsed['mac']


def segment_opus_audio(
    opus_encoder,
    audio_samples: bytes,
    frame_size_ms: int = 40
) -> list:
    """
    Segment audio into Opus frames for superframe transmission.

    Args:
        opus_encoder: Opus encoder object (from gr-opus or opuslib)
        audio_samples: Raw audio samples (16-bit PCM, mono, 8kHz)
        frame_size_ms: Frame size in milliseconds (default: 40ms)

    Returns:
        List of Opus-encoded frames (40 bytes each)
    """
    # For 8kHz audio, 40ms = 320 samples
    # 16-bit PCM = 2 bytes per sample
    # 320 samples * 2 bytes = 640 bytes per frame

    samples_per_frame = (8000 * frame_size_ms) // 1000  # 320 samples
    bytes_per_frame = samples_per_frame * 2  # 640 bytes

    frames = []

    for i in range(0, len(audio_samples), bytes_per_frame):
        frame_audio = audio_samples[i:i + bytes_per_frame]

        if len(frame_audio) < bytes_per_frame:
            # Pad last frame with zeros
            frame_audio = frame_audio.ljust(bytes_per_frame, b'\x00')

        # Encode with Opus (6 kbps = 6000 bps)
        # 40ms frame at 6 kbps = 30 bytes, but we need 40 bytes
        # This might require adjusting bitrate or frame size
        # For now, assume encoder produces 40-byte frames

        try:
            # This is a placeholder - actual encoding depends on
            # whether you're using gr-opus or opuslib
            opus_frame = opus_encoder.encode(frame_audio, frame_size_ms)

            # Ensure exactly 40 bytes
            if len(opus_frame) > 40:
                opus_frame = opus_frame[:40]
            elif len(opus_frame) < 40:
                opus_frame = opus_frame.ljust(40, b'\x00')

            frames.append(opus_frame)
        except Exception as e:
            print(f"Error encoding Opus frame: {e}")
            # Add zero frame as fallback
            frames.append(b'\x00' * 40)

    return frames


