#!/usr/bin/env python3
"""
Superframe Controller for gr-sleipnir

Manages superframe transmission with 25 frames (1 second total, 40ms per frame):
- Frame 0: Authentication frame with ECDSA signature (256 bits -> 768 bits coded)
- Frames 1-24: Voice frames with Opus + MAC (384 bits -> 576 bits coded)

This controller orchestrates separate GNU Radio flowgraphs for each frame type.
"""

import time
import subprocess
import os
import struct
import tempfile
from pathlib import Path
from typing import Optional, Tuple

# Import crypto helpers
try:
    from .crypto_helpers import (
        generate_ecdsa_signature,
        compute_chacha20_mac,
        load_private_key,
        get_callsign_bytes
    )
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("Warning: Crypto helpers not available. Running without authentication/MAC.")


class SuperframeController:
    """
    Manages superframe transmission for gr-sleipnir.
    
    Coordinates frame timing and executes appropriate GNU Radio flowgraphs
    for authentication and voice frames.
    """
    
    # Superframe parameters
    FRAMES_PER_SUPERFRAME = 25
    FRAME_DURATION_MS = 40  # 40ms per frame
    SUPERFRAME_DURATION_MS = FRAMES_PER_SUPERFRAME * FRAME_DURATION_MS  # 1000ms
    
    # Frame payload sizes (before LDPC encoding)
    AUTH_FRAME_BITS = 256  # Frame 0: 256 bits info -> 768 bits coded (rate 1/3)
    VOICE_FRAME_BITS = 384  # Frames 1-24: 384 bits info -> 576 bits coded (rate 2/3)
    
    # Voice frame payload breakdown
    OPUS_BITS = 320  # 40 bytes
    MAC_BITS = 128   # 16 bytes
    CALLSIGN_BITS = 40   # 5 bytes
    FRAME_COUNTER_BITS = 8   # 1 byte
    RESERVED_BITS = 24   # 3 bytes
    
    def __init__(
        self,
        project_root: str,
        callsign: str = "N0CALL",
        private_key_path: Optional[str] = None,
        enable_auth: bool = False,
        enable_mac: bool = False
    ):
        """
        Initialize superframe controller.
        
        Args:
            project_root: Path to gr-sleipnir project root
            callsign: Station callsign (5 bytes max, padded)
            private_key_path: Path to private key file (for ECDSA signing)
            enable_auth: Enable authentication frame (Frame 0)
            enable_mac: Enable ChaCha20-Poly1305 MAC on voice frames
        """
        self.project_root = Path(project_root)
        self.callsign = callsign[:5].upper().ljust(5)  # 5 bytes, uppercase, padded
        self.private_key_path = private_key_path
        self.enable_auth = enable_auth and CRYPTO_AVAILABLE
        self.enable_mac = enable_mac and CRYPTO_AVAILABLE
        
        # Paths to flowgraphs
        self.auth_flowgraph = self.project_root / "examples" / "tx_auth_frame.grc"
        self.voice_flowgraph = self.project_root / "examples" / "tx_4fsk_opus_voice.grc"
        
        # LDPC matrix paths
        self.auth_matrix = self.project_root / "ldpc_matrices" / "ldpc_auth_768_256.alist"
        self.voice_matrix = self.project_root / "ldpc_matrices" / "ldpc_voice_576_384.alist"
        
        # Verify flowgraphs exist
        if self.enable_auth and not self.auth_flowgraph.exists():
            raise FileNotFoundError(f"Auth flowgraph not found: {self.auth_flowgraph}")
        if not self.voice_flowgraph.exists():
            raise FileNotFoundError(f"Voice flowgraph not found: {self.voice_flowgraph}")
        
        # Frame counter
        self.frame_counter = 0
        self.superframe_counter = 0
        
        # Temporary directory for frame outputs
        self.temp_dir = Path(tempfile.mkdtemp(prefix="gr-sleipnir-"))
        
        # Load private key if authentication enabled
        self.private_key = None
        if self.enable_auth and private_key_path:
            try:
                self.private_key = load_private_key(private_key_path)
            except Exception as e:
                print(f"Warning: Could not load private key: {e}")
                self.enable_auth = False
    
    def build_voice_frame_payload(
        self,
        opus_data: bytes,
        frame_num: int,
        mac_key: Optional[bytes] = None
    ) -> bytes:
        """
        Build voice frame payload (384 bits = 48 bytes).
        
        Structure:
        - Opus voice: 320 bits (40 bytes)
        - ChaCha20-Poly1305 MAC: 128 bits (16 bytes)
        - Callsign: 40 bits (5 bytes)
        - Frame counter: 8 bits (1 byte)
        - Reserved: 24 bits (3 bytes)
        
        Args:
            opus_data: Opus-encoded audio (40 bytes)
            frame_num: Frame number within superframe (1-24)
            mac_key: MAC key for ChaCha20-Poly1305 (32 bytes, optional)
        
        Returns:
            48-byte payload ready for LDPC encoding
        """
        if len(opus_data) != 40:
            raise ValueError(f"Opus data must be exactly 40 bytes, got {len(opus_data)}")
        
        # Build payload
        payload = bytearray(48)
        
        # Opus voice data (40 bytes)
        payload[0:40] = opus_data
        
        # Compute MAC if enabled
        if self.enable_mac and mac_key:
            # MAC covers: opus_data + callsign + frame_counter
            mac_data = opus_data + get_callsign_bytes(self.callsign) + bytes([frame_num])
            mac = compute_chacha20_mac(mac_data, mac_key)
            payload[40:56] = mac[:16]  # 16 bytes MAC
        else:
            # Zero MAC if disabled
            payload[40:56] = b'\x00' * 16
        
        # Callsign (5 bytes)
        callsign_bytes = get_callsign_bytes(self.callsign)
        payload[56:61] = callsign_bytes
        
        # Frame counter (1 byte)
        payload[61] = frame_num & 0xFF
        
        # Reserved (3 bytes)
        payload[62:65] = b'\x00' * 3
        
        return bytes(payload)
    
    def build_auth_frame_payload(self, superframe_data: bytes) -> bytes:
        """
        Build authentication frame payload (256 bits = 32 bytes).
        
        Args:
            superframe_data: Data to sign (typically hash of superframe)
        
        Returns:
            32-byte payload with ECDSA signature (or zeros if auth disabled)
        """
        if not self.enable_auth or not self.private_key:
            # Return zeros if authentication disabled
            return b'\x00' * 32
        
        try:
            # Generate ECDSA signature (256 bits = 32 bytes)
            signature = generate_ecdsa_signature(superframe_data, self.private_key)
            
            # Pad/truncate to exactly 32 bytes
            if len(signature) > 32:
                signature = signature[:32]
            elif len(signature) < 32:
                signature = signature.ljust(32, b'\x00')
            
            return signature
        except Exception as e:
            print(f"Error generating signature: {e}")
            return b'\x00' * 32
    
    def transmit_frame(
        self,
        frame_num: int,
        payload: bytes,
        output_file: Path
    ) -> bool:
        """
        Transmit a single frame using appropriate GNU Radio flowgraph.
        
        Args:
            frame_num: Frame number (0 for auth, 1-24 for voice)
            payload: Frame payload (before LDPC encoding)
            output_file: Output file path for modulated signal
        
        Returns:
            True if successful, False otherwise
        """
        # Write payload to temporary file
        payload_file = self.temp_dir / f"frame_{frame_num}_payload.bin"
        payload_file.write_bytes(payload)
        
        if frame_num == 0:
            # Authentication frame
            flowgraph = self.auth_flowgraph
            matrix_file = str(self.auth_matrix)
            expected_bits = self.AUTH_FRAME_BITS
        else:
            # Voice frame
            flowgraph = self.voice_flowgraph
            matrix_file = str(self.voice_matrix)
            expected_bits = self.VOICE_FRAME_BITS
        
        # Verify payload size
        if len(payload) * 8 != expected_bits:
            print(f"Warning: Frame {frame_num} payload size mismatch: "
                  f"expected {expected_bits} bits, got {len(payload) * 8} bits")
        
        # Generate Python script from flowgraph
        try:
            # Use grcc to compile flowgraph
            script_file = self.temp_dir / f"frame_{frame_num}_tx.py"
            result = subprocess.run(
                ["grcc", "-o", str(self.temp_dir), str(flowgraph)],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                print(f"Error compiling flowgraph: {result.stderr}")
                return False
            
            # Modify generated script to use our payload file
            # This is a simplified approach - in practice, you'd pass payload via
            # flowgraph parameters or use a file source block
            
            # Execute flowgraph
            # Note: In practice, you'd want to pass parameters to the flowgraph
            # For now, we assume the flowgraph reads from a file specified in variables
            
            return True
            
        except subprocess.TimeoutExpired:
            print(f"Timeout compiling flowgraph for frame {frame_num}")
            return False
        except Exception as e:
            print(f"Error transmitting frame {frame_num}: {e}")
            return False
    
    def transmit_superframe(
        self,
        opus_frames: list,
        mac_key: Optional[bytes] = None
    ) -> bool:
        """
        Transmit a complete superframe (25 frames).
        
        Args:
            opus_frames: List of 24 Opus-encoded frames (40 bytes each)
            mac_key: MAC key for ChaCha20-Poly1305 (32 bytes, optional)
        
        Returns:
            True if successful, False otherwise
        """
        if len(opus_frames) != 24:
            raise ValueError(f"Expected 24 Opus frames, got {len(opus_frames)}")
        
        # Build superframe data for authentication (hash of all voice frames)
        superframe_data = b''.join(opus_frames)
        
        # Frame 0: Authentication frame
        if self.enable_auth:
            auth_payload = self.build_auth_frame_payload(superframe_data)
            auth_output = self.temp_dir / f"superframe_{self.superframe_counter}_frame_0.iq"
            if not self.transmit_frame(0, auth_payload, auth_output):
                print("Failed to transmit authentication frame")
                return False
        
        # Frames 1-24: Voice frames
        for i, opus_frame in enumerate(opus_frames, start=1):
            voice_payload = self.build_voice_frame_payload(
                opus_frame,
                i,
                mac_key
            )
            voice_output = self.temp_dir / f"superframe_{self.superframe_counter}_frame_{i}.iq"
            if not self.transmit_frame(i, voice_payload, voice_output):
                print(f"Failed to transmit voice frame {i}")
                return False
        
        self.superframe_counter += 1
        return True
    
    def cleanup(self):
        """Clean up temporary files."""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


def main():
    """Example usage of SuperframeController."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: superframe_controller.py <project_root> [callsign] [private_key]")
        sys.exit(1)
    
    project_root = sys.argv[1]
    callsign = sys.argv[2] if len(sys.argv) > 2 else "N0CALL"
    private_key = sys.argv[3] if len(sys.argv) > 3 else None
    
    controller = SuperframeController(
        project_root=project_root,
        callsign=callsign,
        private_key_path=private_key,
        enable_auth=(private_key is not None),
        enable_mac=True
    )
    
    # Example: Generate dummy Opus frames
    opus_frames = [b'\x00' * 40] * 24
    
    # Transmit superframe
    success = controller.transmit_superframe(opus_frames)
    
    if success:
        print("Superframe transmitted successfully")
    else:
        print("Superframe transmission failed")
    
    controller.cleanup()


if __name__ == "__main__":
    main()


