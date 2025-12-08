#!/usr/bin/env python3
"""
Example: Superframe Transmission

Demonstrates how to use the superframe controller to transmit
a complete superframe with authentication and MAC.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from python.superframe_controller import SuperframeController


def generate_dummy_opus_frames(num_frames=24):
    """
    Generate dummy Opus frames for testing.

    In production, you would:
    1. Read audio from microphone or file
    2. Encode with gr-opus Opus encoder
    3. Segment into 40ms frames (40 bytes each at 6 kbps)
    """
    return [b'\x00' * 40] * num_frames


def main():
    """Example superframe transmission."""

    # Configuration
    project_root = str(Path(__file__).parent.parent)
    callsign = "N0CALL"
    private_key_path = None  # Set to key file path if authentication enabled
    enable_auth = False  # Set to True if you have private key file
    enable_mac = True   # MAC can work with fallback libraries

    # Generate MAC key (32 bytes for ChaCha20-Poly1305)
    # In production, this would be shared via key exchange
    mac_key = os.urandom(32)

    print("=" * 60)
    print("gr-sleipnir Superframe Transmission Example")
    print("=" * 60)
    print(f"Project root: {project_root}")
    print(f"Callsign: {callsign}")
    print(f"Authentication: {'Enabled' if enable_auth else 'Disabled'}")
    print(f"MAC: {'Enabled' if enable_mac else 'Disabled'}")
    print()

    # Initialize controller
    try:
        controller = SuperframeController(
            project_root=project_root,
            callsign=callsign,
            private_key_path=private_key_path,
            enable_auth=enable_auth,
            enable_mac=enable_mac
        )
        print("Superframe controller initialized")
    except Exception as e:
        print(f"Error initializing controller: {e}")
        return 1

    # Generate Opus frames
    # In production, these would come from audio encoding
    print("Generating Opus frames...")
    opus_frames = generate_dummy_opus_frames(24)
    print(f"Generated {len(opus_frames)} Opus frames ({len(opus_frames[0])} bytes each)")

    # Transmit superframe
    print()
    print("Transmitting superframe...")
    try:
        success = controller.transmit_superframe(opus_frames, mac_key=mac_key)

        if success:
            print("Superframe transmitted successfully!")
            print(f"Output files in: {controller.temp_dir}")
        else:
            print("Superframe transmission failed")
            return 1
    except Exception as e:
        print(f"Error transmitting superframe: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Cleanup
        print()
        print("Cleaning up...")
        controller.cleanup()

    print()
    print("=" * 60)
    print("Example completed")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Create tx_auth_frame.grc flowgraph")
    print("2. Modify tx_4fsk_opus.grc to create tx_4fsk_opus_voice.grc")
    print("3. Integrate with actual Opus audio encoding")
    print("4. Set up private key file for authentication (optional)")
    print("5. Implement key exchange for MAC keys")

    return 0


if __name__ == "__main__":
    sys.exit(main())

