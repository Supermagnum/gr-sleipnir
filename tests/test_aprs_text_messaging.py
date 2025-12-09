#!/usr/bin/env python3
"""
Comprehensive test suite for APRS and text messaging in gr-sleipnir.

Tests all scenarios:
- Voice + APRS simultaneous transmission
- Voice + text messaging
- APRS-only mode
- Text-only mode
- Mixed mode stress test
- Critical validation (no data leakage)
"""

import sys
import os
import time
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "python"))

try:
    from gnuradio import gr
    from gnuradio import blocks, filter, analog, digital, pdu
    from gnuradio.gr import sizeof_float, sizeof_gr_complex, sizeof_char
    from gnuradio.gr import pmt
    import gnuradio.gr_opus as gr_opus
except ImportError as e:
    print(f"ERROR: GNU Radio not available: {e}")
    sys.exit(1)

try:
    from sleipnir_superframe_assembler import make_sleipnir_superframe_assembler
    from sleipnir_superframe_parser import make_sleipnir_superframe_parser
    from frame_aware_ldpc import make_frame_aware_ldpc_encoder, make_frame_aware_ldpc_decoder
    from voice_frame_builder import VoiceFrameBuilder
except ImportError as e:
    print(f"ERROR: gr-sleipnir modules not available: {e}")
    sys.exit(1)


class TestResults:
    """Container for test results."""
    def __init__(self):
        self.results = {}
        self.passed = 0
        self.failed = 0
    
    def add_result(self, test_name: str, passed: bool, details: Dict = None):
        """Add a test result."""
        self.results[test_name] = {
            'passed': passed,
            'details': details or {}
        }
        if passed:
            self.passed += 1
        else:
            self.failed += 1
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Total: {self.passed + self.failed}")
        print("\nDetailed Results:")
        for test_name, result in self.results.items():
            status = "PASS" if result['passed'] else "FAIL"
            print(f"  {status}: {test_name}")
            if result['details']:
                for key, value in result['details'].items():
                    print(f"    {key}: {value}")


def create_aprs_packet(callsign: str, latitude: float, longitude: float, altitude: int = 0) -> bytes:
    """Create an APRS packet payload."""
    # Simplified APRS format: CALLSIGN,LAT,LON,ALT
    aprs_str = f"{callsign},{latitude:.6f},{longitude:.6f},{altitude}"
    return aprs_str.encode('utf-8')


def create_text_message(text: str) -> bytes:
    """Create a text message payload."""
    return text.encode('utf-8')


def test_voice_aprs_simultaneous(results: TestResults):
    """Test voice + APRS simultaneous transmission."""
    print("\n" + "=" * 60)
    print("Test: Voice + APRS Simultaneous Transmission")
    print("=" * 60)
    
    try:
        # Create assembler
        assembler = make_sleipnir_superframe_assembler(
            callsign="TEST",
            enable_signing=False,
            enable_encryption=False
        )
        
        # Create parser
        parser = make_sleipnir_superframe_parser(
            local_callsign="TEST",
            require_signatures=False
        )
        
        # Create test data
        opus_frames = [b'\x01' * 40] * 24  # 24 voice frames
        aprs_packet = create_aprs_packet("TEST", 59.9139, 10.7522, 100)
        
        # Send APRS packet to assembler
        aprs_pmt = pmt.init_u8vector(len(aprs_packet), list(aprs_packet))
        assembler.handle_aprs_msg(pmt.cons(pmt.make_dict(), aprs_pmt))
        
        # Assemble superframe
        frame_payloads = assembler.assemble_superframe(opus_frames)
        
        # Verify frame count
        if len(frame_payloads) != 24:
            results.add_result("voice_aprs_frame_count", False, {
                'expected': 24,
                'got': len(frame_payloads)
            })
            return
        
        # Parse frames
        aprs_found = False
        voice_found = False
        
        for frame in frame_payloads:
            parsed = parser.frame_builder.parse_frame(frame)
            frame_type = parsed.get('frame_type', 0)
            
            if frame_type == parser.frame_builder.FRAME_TYPE_APRS:
                aprs_found = True
            elif frame_type == parser.frame_builder.FRAME_TYPE_VOICE:
                voice_found = True
        
        # Verify APRS doesn't corrupt voice
        voice_corrupted = False
        for i, frame in enumerate(frame_payloads):
            parsed = parser.frame_builder.parse_frame(frame)
            if parsed.get('frame_type') == parser.frame_builder.FRAME_TYPE_VOICE:
                opus_data = parsed.get('opus_data', b'')
                # Check if voice data is corrupted (all zeros or wrong type)
                if opus_data == b'\x00' * len(opus_data):
                    voice_corrupted = True
                    break
        
        results.add_result("voice_aprs_simultaneous", 
                          aprs_found and voice_found and not voice_corrupted,
                          {
                              'aprs_found': aprs_found,
                              'voice_found': voice_found,
                              'voice_corrupted': voice_corrupted
                          })
        
    except Exception as e:
        results.add_result("voice_aprs_simultaneous", False, {'error': str(e)})


def test_voice_text_simultaneous(results: TestResults):
    """Test voice + text messaging."""
    print("\n" + "=" * 60)
    print("Test: Voice + Text Messaging")
    print("=" * 60)
    
    try:
        assembler = make_sleipnir_superframe_assembler(
            callsign="TEST",
            enable_signing=False,
            enable_encryption=False
        )
        
        parser = make_sleipnir_superframe_parser(
            local_callsign="TEST",
            require_signatures=False
        )
        
        opus_frames = [b'\x02' * 40] * 24
        text_message = create_text_message("Hello from gr-sleipnir!")
        
        # Send text message
        text_pmt = pmt.init_u8vector(len(text_message), list(text_message))
        assembler.handle_text_msg(pmt.cons(pmt.make_dict(), text_pmt))
        
        # Assemble and parse
        frame_payloads = assembler.assemble_superframe(opus_frames)
        
        text_found = False
        voice_found = False
        
        for frame in frame_payloads:
            parsed = parser.frame_builder.parse_frame(frame)
            frame_type = parsed.get('frame_type', 0)
            
            if frame_type == parser.frame_builder.FRAME_TYPE_TEXT:
                text_found = True
            elif frame_type == parser.frame_builder.FRAME_TYPE_VOICE:
                voice_found = True
        
        results.add_result("voice_text_simultaneous",
                          text_found and voice_found,
                          {
                              'text_found': text_found,
                              'voice_found': voice_found
                          })
        
    except Exception as e:
        results.add_result("voice_text_simultaneous", False, {'error': str(e)})


def test_aprs_only_mode(results: TestResults):
    """Test APRS-only mode (no voice)."""
    print("\n" + "=" * 60)
    print("Test: APRS-Only Mode")
    print("=" * 60)
    
    try:
        assembler = make_sleipnir_superframe_assembler(
            callsign="TEST",
            enable_signing=False,
            enable_encryption=False
        )
        
        parser = make_sleipnir_superframe_parser(
            local_callsign="TEST",
            require_signatures=False
        )
        
        # Send multiple APRS packets
        aprs_packets = [
            create_aprs_packet("TEST", 59.9139, 10.7522, 100),
            create_aprs_packet("TEST", 59.9140, 10.7523, 101),
            create_aprs_packet("TEST", 59.9141, 10.7524, 102)
        ]
        
        for aprs_packet in aprs_packets:
            aprs_pmt = pmt.init_u8vector(len(aprs_packet), list(aprs_packet))
            assembler.handle_aprs_msg(pmt.cons(pmt.make_dict(), aprs_pmt))
        
        # Use empty voice frames
        opus_frames = [b'\x00' * 40] * 24
        
        frame_payloads = assembler.assemble_superframe(opus_frames)
        
        aprs_count = 0
        voice_count = 0
        
        for frame in frame_payloads:
            parsed = parser.frame_builder.parse_frame(frame)
            frame_type = parsed.get('frame_type', 0)
            
            if frame_type == parser.frame_builder.FRAME_TYPE_APRS:
                aprs_count += 1
            elif frame_type == parser.frame_builder.FRAME_TYPE_VOICE:
                voice_count += 1
        
        # In APRS-only mode, we expect APRS frames to be inserted
        # Remaining frames will still be voice (empty frames)
        # The key is that APRS frames are present and properly identified
        results.add_result("aprs_only_mode",
                          aprs_count >= 3,
                          {
                              'aprs_count': aprs_count,
                              'voice_count': voice_count,
                              'note': 'APRS frames inserted, remaining frames are voice (expected)'
                          })
        
    except Exception as e:
        results.add_result("aprs_only_mode", False, {'error': str(e)})


def test_text_only_mode(results: TestResults):
    """Test text-only mode (no voice)."""
    print("\n" + "=" * 60)
    print("Test: Text-Only Mode")
    print("=" * 60)
    
    try:
        assembler = make_sleipnir_superframe_assembler(
            callsign="TEST",
            enable_signing=False,
            enable_encryption=False
        )
        
        parser = make_sleipnir_superframe_parser(
            local_callsign="TEST",
            require_signatures=False
        )
        
        # Send text messages
        text_messages = [
            create_text_message("Message 1"),
            create_text_message("Message 2"),
            create_text_message("Message 3")
        ]
        
        for text_msg in text_messages:
            text_pmt = pmt.init_u8vector(len(text_msg), list(text_msg))
            assembler.handle_text_msg(pmt.cons(pmt.make_dict(), text_pmt))
        
        opus_frames = [b'\x00' * 40] * 24
        
        frame_payloads = assembler.assemble_superframe(opus_frames)
        
        text_count = 0
        voice_count = 0
        
        for frame in frame_payloads:
            parsed = parser.frame_builder.parse_frame(frame)
            frame_type = parsed.get('frame_type', 0)
            
            if frame_type == parser.frame_builder.FRAME_TYPE_TEXT:
                text_count += 1
            elif frame_type == parser.frame_builder.FRAME_TYPE_VOICE:
                voice_count += 1
        
        # In text-only mode, we expect text frames to be inserted
        # Remaining frames will still be voice (empty frames)
        # The key is that text frames are present and properly identified
        results.add_result("text_only_mode",
                          text_count >= 3,
                          {
                              'text_count': text_count,
                              'voice_count': voice_count,
                              'note': 'Text frames inserted, remaining frames are voice (expected)'
                          })
        
    except Exception as e:
        results.add_result("text_only_mode", False, {'error': str(e)})


def test_mixed_mode_stress(results: TestResults):
    """Test mixed mode: voice + APRS + text simultaneously."""
    print("\n" + "=" * 60)
    print("Test: Mixed Mode Stress Test")
    print("=" * 60)
    
    try:
        assembler = make_sleipnir_superframe_assembler(
            callsign="TEST",
            enable_signing=False,
            enable_encryption=False
        )
        
        parser = make_sleipnir_superframe_parser(
            local_callsign="TEST",
            require_signatures=False
        )
        
        # Send all types
        # APRS
        aprs_packet = create_aprs_packet("TEST", 59.9139, 10.7522, 100)
        aprs_pmt = pmt.init_u8vector(len(aprs_packet), list(aprs_packet))
        assembler.handle_aprs_msg(pmt.cons(pmt.make_dict(), aprs_pmt))
        
        # Text
        text_message = create_text_message("Mixed mode test")
        text_pmt = pmt.init_u8vector(len(text_message), list(text_message))
        assembler.handle_text_msg(pmt.cons(pmt.make_dict(), text_pmt))
        
        # Voice
        opus_frames = [b'\x03' * 40] * 24
        
        frame_payloads = assembler.assemble_superframe(opus_frames)
        
        aprs_count = 0
        text_count = 0
        voice_count = 0
        
        for frame in frame_payloads:
            parsed = parser.frame_builder.parse_frame(frame)
            frame_type = parsed.get('frame_type', 0)
            
            if frame_type == parser.frame_builder.FRAME_TYPE_APRS:
                aprs_count += 1
            elif frame_type == parser.frame_builder.FRAME_TYPE_TEXT:
                text_count += 1
            elif frame_type == parser.frame_builder.FRAME_TYPE_VOICE:
                voice_count += 1
        
        # Verify no cross-contamination
        contamination = False
        for frame in frame_payloads:
            parsed = parser.frame_builder.parse_frame(frame)
            frame_type = parsed.get('frame_type', 0)
            
            if frame_type == parser.frame_builder.FRAME_TYPE_VOICE:
                opus_data = parsed.get('opus_data', b'')
                # Voice should not contain APRS or text patterns
                if b'TEST,' in opus_data or b'Mixed mode' in opus_data:
                    contamination = True
                    break
        
        results.add_result("mixed_mode_stress",
                          aprs_count > 0 and text_count > 0 and voice_count > 0 and not contamination,
                          {
                              'aprs_count': aprs_count,
                              'text_count': text_count,
                              'voice_count': voice_count,
                              'contamination': contamination
                          })
        
    except Exception as e:
        results.add_result("mixed_mode_stress", False, {'error': str(e)})


def test_data_leakage_validation(results: TestResults):
    """Critical validation: APRS/text must NOT appear in audio output."""
    print("\n" + "=" * 60)
    print("Test: Data Leakage Validation")
    print("=" * 60)
    
    try:
        assembler = make_sleipnir_superframe_assembler(
            callsign="TEST",
            enable_signing=False,
            enable_encryption=False
        )
        
        parser = make_sleipnir_superframe_parser(
            local_callsign="TEST",
            require_signatures=False
        )
        
        # Send APRS and text
        aprs_packet = create_aprs_packet("TEST", 59.9139, 10.7522, 100)
        aprs_pmt = pmt.init_u8vector(len(aprs_packet), list(aprs_packet))
        assembler.handle_aprs_msg(pmt.cons(pmt.make_dict(), aprs_pmt))
        
        text_message = create_text_message("This should not appear in audio")
        text_pmt = pmt.init_u8vector(len(text_message), list(text_message))
        assembler.handle_text_msg(pmt.cons(pmt.make_dict(), text_pmt))
        
        # Use known voice pattern
        opus_frames = [b'\xAA' * 40] * 24
        
        frame_payloads = assembler.assemble_superframe(opus_frames)
        
        # Parse and check audio output
        opus_output = []
        aprs_output = []
        text_output = []
        
        for frame in frame_payloads:
            parsed = parser.frame_builder.parse_frame(frame)
            frame_type = parsed.get('frame_type', 0)
            
            if frame_type == parser.frame_builder.FRAME_TYPE_VOICE:
                opus_data = parsed.get('opus_data', b'')
                opus_output.append(opus_data)
            elif frame_type == parser.frame_builder.FRAME_TYPE_APRS:
                aprs_data = parsed.get('aprs_data', b'')
                aprs_output.append(aprs_data)
            elif frame_type == parser.frame_builder.FRAME_TYPE_TEXT:
                text_data = parsed.get('text_data', b'')
                text_output.append(text_data)
        
        # Check for leakage
        audio_data = b''.join(opus_output)
        aprs_leakage = aprs_packet in audio_data
        text_leakage = text_message in audio_data
        
        # Check that APRS/text are properly separated
        aprs_found = len(aprs_output) > 0
        text_found = len(text_output) > 0
        
        results.add_result("data_leakage_validation",
                          not aprs_leakage and not text_leakage and aprs_found and text_found,
                          {
                              'aprs_in_audio': aprs_leakage,
                              'text_in_audio': text_leakage,
                              'aprs_properly_separated': aprs_found,
                              'text_properly_separated': text_found
                          })
        
    except Exception as e:
        results.add_result("data_leakage_validation", False, {'error': str(e)})


def main():
    """Run all tests."""
    print("=" * 60)
    print("APRS and Text Messaging Test Suite")
    print("=" * 60)
    
    results = TestResults()
    
    # Run all tests
    test_voice_aprs_simultaneous(results)
    test_voice_text_simultaneous(results)
    test_aprs_only_mode(results)
    test_text_only_mode(results)
    test_mixed_mode_stress(results)
    test_data_leakage_validation(results)
    
    # Print summary
    results.print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if results.failed == 0 else 1)


if __name__ == "__main__":
    main()

