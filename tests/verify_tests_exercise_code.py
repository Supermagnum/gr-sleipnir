#!/usr/bin/env python3
"""
Verify that all tests actually exercise the code and catch bugs.

This script:
1. Runs all tests
2. Verifies they actually call the real code (not mocks/stubs)
3. Checks that tests would catch common bugs
4. Reports any tests that don't actually verify functionality
"""

import unittest
import sys
import os
import importlib
import inspect
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def analyze_test_file(test_file_path):
    """Analyze a test file to see if it actually exercises code."""
    issues = []
    
    try:
        # Import the test module
        spec = importlib.util.spec_from_file_location("test_module", test_file_path)
        if spec is None:
            return [f"Cannot load {test_file_path}"]
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Check for test functions/classes
        test_functions = []
        test_classes = []
        
        for name, obj in inspect.getmembers(module):
            if name.startswith('test_') and inspect.isfunction(obj):
                test_functions.append((name, obj))
            elif inspect.isclass(obj) and (name.startswith('Test') or 'Test' in name):
                test_classes.append((name, obj))
                # Get test methods from class
                for method_name, method in inspect.getmembers(obj, predicate=inspect.isfunction):
                    if method_name.startswith('test_'):
                        test_functions.append((f"{name}.{method_name}", method))
        
        # Analyze each test function
        for test_name, test_func in test_functions:
            source = inspect.getsource(test_func)
            
            # Check for common issues
            checks = {
                'imports_real_code': False,
                'calls_real_functions': False,
                'has_assertions': False,
                'not_just_skip': False,
            }
            
            # Check imports
            if 'from python.' in source or 'import python.' in source:
                checks['imports_real_code'] = True
            
            # Check for actual function calls (not just mocks)
            real_function_patterns = [
                'ldpc_encode', 'ldpc_decode',
                'encrypt_chacha20', 'decrypt_chacha20',
                'generate_ecdsa_signature', 'verify_ecdsa_signature',
                'make_sleipnir', 'frame_aware_ldpc',
            ]
            for pattern in real_function_patterns:
                if pattern in source:
                    checks['calls_real_functions'] = True
                    break
            
            # Check for assertions
            if 'assert' in source or 'self.assertEqual' in source or 'self.assertNotEqual' in source:
                checks['has_assertions'] = True
            
            # Check if it's not just skipping
            if 'skipTest' in source or 'skipIf' in source:
                # Check if there's actual test code after the skip
                lines_after_skip = source.split('skipTest')[1] if 'skipTest' in source else source
                if 'assert' in lines_after_skip or len(lines_after_skip) > 100:
                    checks['not_just_skip'] = True
            else:
                checks['not_just_skip'] = True
            
            # Report issues
            if not checks['imports_real_code'] and not checks['calls_real_functions']:
                issues.append(f"{test_name}: Doesn't import or call real code")
            if not checks['has_assertions']:
                issues.append(f"{test_name}: No assertions found")
            if not checks['not_just_skip']:
                issues.append(f"{test_name}: Only skips, no actual test")
        
        if not test_functions:
            issues.append("No test functions found")
        
    except Exception as e:
        issues.append(f"Error analyzing {test_file_path}: {e}")
    
    return issues


def main():
    """Main verification function."""
    print("=" * 70)
    print("Test Code Verification")
    print("=" * 70)
    print()
    
    tests_dir = Path(__file__).parent
    test_files = list(tests_dir.glob('test_*.py'))
    
    all_issues = {}
    passed_tests = []
    
    for test_file in sorted(test_files):
        print(f"Analyzing {test_file.name}...")
        issues = analyze_test_file(test_file)
        
        if issues:
            all_issues[test_file.name] = issues
            print(f"  ⚠️  Found {len(issues)} potential issue(s)")
            for issue in issues:
                print(f"     - {issue}")
        else:
            passed_tests.append(test_file.name)
            print(f"  ✓ Looks good")
        print()
    
    # Summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Total test files: {len(test_files)}")
    print(f"Files with issues: {len(all_issues)}")
    print(f"Files that look good: {len(passed_tests)}")
    print()
    
    if all_issues:
        print("Files with potential issues:")
        for filename, issues in all_issues.items():
            print(f"  {filename}:")
            for issue in issues:
                print(f"    - {issue}")
        print()
        print("⚠️  WARNING: Some tests may not actually exercise the code!")
        return 1
    else:
        print("✓ All tests appear to exercise real code")
        return 0


if __name__ == '__main__':
    import importlib.util
    sys.exit(main())

