#!/usr/bin/env python3
"""
Minimal integration test for decoder router -> parser message port connection.
"""

import numpy as np
from gnuradio import gr, blocks
import pmt
import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import our blocks
from python.frame_aware_ldpc_decoder_router import make_frame_aware_ldpc_decoder_router
from python.sleipnir_superframe_parser import make_sleipnir_superframe_parser


class TestMessageSink(gr.basic_block):
    """Simple message sink to verify messages are received."""
    
    def __init__(self):
        gr.basic_block.__init__(
            self,
            name="test_message_sink",
            in_sig=None,
            out_sig=None
        )
        
        self.message_port_register_in(pmt.intern("in"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)
        self.msg_count = 0
    
    def handle_msg(self, msg):
        self.msg_count += 1
        print(f"\n{'='*60}")
        print(f"TestMessageSink: Received message #{self.msg_count}")
        print(f"{'='*60}\n")


def test_decoder_to_parser():
    """Test decoder router -> parser connection."""
    print("\n" + "="*70)
    print("TEST: Decoder Router -> Parser Message Port Connection")
    print("="*70 + "\n")
    
    # Create minimal flowgraph
    tb = gr.top_block()
    
    # Create test data source
    test_data = np.random.randn(10000).astype(np.float32)
    source = blocks.vector_source_f(test_data, repeat=False)
    
    # Create decoder router
    auth_matrix = "../ldpc_matrices/ldpc_auth_1536_512.alist"
    voice_matrix = "../ldpc_matrices/ldpc_voice_576_384.alist"
    
    if not Path(auth_matrix).exists() or not Path(voice_matrix).exists():
        print("ERROR: LDPC matrix files not found")
        print(f"  Looking for: {auth_matrix}")
        print(f"  Looking for: {voice_matrix}")
        print(f"  Base directory: {base_dir}")
        return False
    
    decoder_router = make_frame_aware_ldpc_decoder_router(
        auth_matrix_file=auth_matrix,
        voice_matrix_file=voice_matrix,
        superframe_size=25,
        max_iter=50
    )
    print("Decoder router created")
    
    # Create parser
    parser = make_sleipnir_superframe_parser(
        local_callsign="N0CALL",
        enable_sync_detection=False,
        mac_key=None
    )
    print("Parser created")
    
    # Create test sink to verify parser output
    test_sink = TestMessageSink()
    
    # Connect stream: source -> decoder_router
    tb.connect(source, decoder_router)
    
    # Connect message ports: decoder_router -> parser
    print("Connecting message port: decoder_router['pdus'] -> parser['in']")
    tb.msg_connect((decoder_router, "pdus"), (parser, "in"))
    
    # Connect parser output to test sink
    tb.msg_connect((parser, "out"), (test_sink, "in"))
    
    # Start flowgraph
    print("\nStarting flowgraph...")
    tb.start()
    
    # Let it run
    print("Running for 5 seconds...")
    time.sleep(5)
    
    # Stop
    print("Stopping flowgraph...")
    tb.stop()
    tb.wait()
    
    print(f"\nResults:")
    print(f"  Test sink received: {test_sink.msg_count} messages")
    print(f"  Parser message count: {getattr(parser, '_parser_msg_count', 0)}")
    
    if test_sink.msg_count > 0 or getattr(parser, '_parser_msg_count', 0) > 0:
        print("\n[ok] SUCCESS: Messages are being delivered!")
        return True
    else:
        print("\n[fail] FAIL: No messages received")
        return False


def test_decoder_to_test_sink():
    """Test decoder router -> test sink (bypass parser)."""
    print("\n" + "="*70)
    print("TEST: Decoder Router -> Test Sink (bypass parser)")
    print("="*70 + "\n")
    
    tb = gr.top_block()
    
    # Create test data
    test_data = np.random.randn(10000).astype(np.float32)
    source = blocks.vector_source_f(test_data, repeat=False)
    
    # Create decoder router
    # Find LDPC matrix files
    base_dir = Path(__file__).parent.parent
    auth_matrix = base_dir / "ldpc_matrices" / "ldpc_auth_1536_512.alist"
    voice_matrix = base_dir / "ldpc_matrices" / "ldpc_voice_576_384.alist"
    
    # Try alternative locations
    if not auth_matrix.exists():
        auth_matrix = base_dir / "python" / "ldpc_matrices" / "ldpc_auth_1536_512.alist"
    if not voice_matrix.exists():
        voice_matrix = base_dir / "python" / "ldpc_matrices" / "ldpc_voice_576_384.alist"
    
    auth_matrix = str(auth_matrix)
    voice_matrix = str(voice_matrix)
    
    if not Path(auth_matrix).exists() or not Path(voice_matrix).exists():
        print("ERROR: LDPC matrix files not found")
        print(f"  Looking for: {auth_matrix}")
        print(f"  Looking for: {voice_matrix}")
        return False
    
    decoder_router = make_frame_aware_ldpc_decoder_router(
        auth_matrix_file=auth_matrix,
        voice_matrix_file=voice_matrix,
        superframe_size=25,
        max_iter=50
    )
    
    # Create test sink
    test_sink = TestMessageSink()
    
    # Connect
    tb.connect(source, decoder_router)
    tb.msg_connect((decoder_router, "pdus"), (test_sink, "in"))
    
    # Run
    print("Starting flowgraph...")
    tb.start()
    time.sleep(5)
    tb.stop()
    tb.wait()
    
    print(f"\nResults:")
    print(f"  Test sink received: {test_sink.msg_count} messages")
    
    if test_sink.msg_count > 0:
        print("\n[ok] SUCCESS: Decoder router messages reach test sink!")
        return True
    else:
        print("\n[fail] FAIL: No messages from decoder router")
        return False


if __name__ == "__main__":
    print("\n" + "="*70)
    print("Decoder Router -> Parser Integration Test")
    print("="*70)
    
    # Test 1: Decoder -> Test Sink (bypass parser)
    result1 = test_decoder_to_test_sink()
    
    # Test 2: Decoder -> Parser
    result2 = test_decoder_to_parser()
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Test 1 (Decoder -> Test Sink): {'PASS' if result1 else 'FAIL'}")
    print(f"Test 2 (Decoder -> Parser): {'PASS' if result2 else 'FAIL'}")
    print("="*70)

