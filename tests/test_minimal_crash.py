#!/usr/bin/env python3
"""
Minimal test case to reproduce the phase 1 crash.
"""

import sys
import os
import time
import traceback
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(Path(__file__).parent))

from flowgraph_builder import build_test_flowgraph, ChannelModel
from gnuradio import gr, blocks
import pmt

def test_minimal_flowgraph():
    """Test minimal flowgraph setup and execution."""
    print("=" * 70)
    print("MINIMAL CRASH REPRODUCTION TEST")
    print("=" * 70)
    print()
    
    try:
        # Step 1: Create channel dict (as flowgraph_builder expects)
        print("Step 1: Creating channel dict...")
        channel = {"type": "clean"}
        print("  ✓ Channel dict created")
        
        # Step 2: Create flowgraph
        print("\nStep 2: Creating flowgraph...")
        tb = build_test_flowgraph(
            input_wav="wav/cq_pcm.wav",
            output_wav="/tmp/test_minimal_output.wav",
            modulation=4,
            crypto_mode="none",
            channel=channel,
            snr_db=20.0,
            audio_samp_rate=48000.0,
            rf_samp_rate=48000.0,
            symbol_rate=4800.0,
            fsk_deviation=2400.0,
            auth_matrix_file="ldpc_matrices/ldpc_auth_1536_512.alist",
            voice_matrix_file="ldpc_matrices/ldpc_voice_576_384.alist",
            test_duration=1.0,
            data_mode="voice",
            recipients=["TEST1"]
        )
        print("  ✓ Flowgraph created")
        print(f"  Flowgraph type: {type(tb)}")
        
        # Step 3: Check for recipient message
        print("\nStep 3: Checking recipient message setup...")
        if hasattr(tb, '_recipient_msg'):
            print("  ✓ Recipient message exists")
            if hasattr(tb, '_tx_block'):
                print(f"  ✓ TX block exists: {type(tb._tx_block)}")
            else:
                print("  ✗ TX block not found")
        else:
            print("  - No recipient message (this is OK)")
        
        # Step 4: Start flowgraph
        print("\nStep 4: Starting flowgraph...")
        tb.start()
        print("  ✓ Flowgraph started")
        
        # Step 5: Try to send recipient message (this is where warning occurs)
        print("\nStep 5: Attempting to send recipient message...")
        if hasattr(tb, '_recipient_msg') and hasattr(tb, '_tx_block'):
            try:
                time.sleep(0.1)  # Small delay
                tx_block = tb._tx_block
                
                # Check if message port exists
                if hasattr(tx_block, 'message_port_pub'):
                    print(f"  ✓ TX block has message_port_pub method")
                    try:
                        tx_block.message_port_pub(pmt.intern("ctrl"), tb._recipient_msg)
                        print("  ✓ Recipient message sent successfully")
                    except Exception as e:
                        print(f"  ✗ Error sending message: {e}")
                        print(f"    Error type: {type(e)}")
                        traceback.print_exc()
                else:
                    print("  ✗ TX block does not have message_port_pub method")
            except Exception as e:
                print(f"  ✗ Exception accessing TX block: {e}")
                print(f"    Error type: {type(e)}")
                traceback.print_exc()
        
        # Step 6: Run flowgraph
        print("\nStep 6: Running flowgraph for 1 second...")
        time.sleep(1.0)
        print("  ✓ Flowgraph ran successfully")
        
        # Step 7: Stop flowgraph
        print("\nStep 7: Stopping flowgraph...")
        tb.stop()
        print("  ✓ Flowgraph stopped")
        
        # Step 8: Wait for cleanup
        print("\nStep 8: Waiting for cleanup...")
        tb.wait()
        print("  ✓ Cleanup complete")
        
        # Step 9: Manual cleanup (like test_comprehensive.py does)
        print("\nStep 9: Manual cleanup...")
        try:
            # Lock/unlock
            tb.lock()
            tb.unlock()
            
            # Disconnect
            try:
                tb.disconnect_all()
            except:
                pass
            
            # Clear references
            if hasattr(tb, '_metrics_block'):
                try:
                    del tb._metrics_block
                except:
                    pass
            if hasattr(tb, '_tx_block'):
                try:
                    del tb._tx_block
                except:
                    pass
            if hasattr(tb, '_rx_block'):
                try:
                    del tb._rx_block
                except:
                    pass
            
            # Clear all _ prefixed attributes
            if hasattr(tb, '__dict__'):
                for key in list(tb.__dict__.keys()):
                    if key.startswith('_'):
                        try:
                            delattr(tb, key)
                        except:
                            pass
            
            # Delete top block
            del tb
            
            # Force garbage collection
            import gc
            gc.collect()
            gc.collect()
            gc.collect()
            
            # Small delay
            time.sleep(0.3)
            
            print("  ✓ Manual cleanup complete")
        except Exception as e:
            print(f"  ✗ Error during cleanup: {e}")
            print(f"    Error type: {type(e)}")
            traceback.print_exc()
        
        print("\n" + "=" * 70)
        print("✓✓✓ MINIMAL TEST PASSED ✓✓✓")
        print("=" * 70)
        return True
        
    except Exception as e:
        print(f"\n✗✗✗ CRASH REPRODUCED ✗✗✗")
        print(f"Error: {e}")
        print(f"Error type: {type(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_minimal_flowgraph()
    sys.exit(0 if success else 1)

