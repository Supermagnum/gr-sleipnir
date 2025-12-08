#!/usr/bin/env python3
"""
Run All Tests

Runs all test suites for gr-sleipnir.
"""

import sys
import subprocess
from pathlib import Path

# Test modules
TESTS = [
    ("Voice + Text Multiplexing", "test_voice_text_multiplex.py"),
    ("Encryption Switching", "test_encryption_switching.py"),
    ("Signature Verification", "test_signature_verification.py"),
    ("Multi-Recipient", "test_multi_recipient.py"),
    ("APRS Injection", "test_aprs_injection.py"),
    ("Backward Compatibility", "test_backward_compatibility.py"),
    ("Recipient Checking", "test_recipient_checking.py"),
    ("Latency Measurement", "test_latency_measurement.py"),
]


def run_test(test_name, test_file):
    """Run a single test."""
    print(f"\n{'='*60}")
    print(f"Running: {test_name}")
    print(f"{'='*60}")
    
    test_path = Path(__file__).parent / test_file
    
    if not test_path.exists():
        print(f"FAIL: Test file not found: {test_file}")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, str(test_path)],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"FAIL: Test timed out: {test_name}")
        return False
    except Exception as e:
        print(f"FAIL: Test failed with error: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("gr-sleipnir Test Suite")
    print("=" * 60)
    
    results = []
    
    for test_name, test_file in TESTS:
        success = run_test(test_name, test_file)
        results.append((test_name, success))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"{status}: {test_name}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {len(results)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

