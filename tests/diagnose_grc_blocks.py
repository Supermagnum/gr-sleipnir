#!/usr/bin/env python3
"""
Diagnostic script to check why gr-sleipnir blocks don't appear in GRC.

This script checks:
1. Block YAML files are installed
2. Module can be imported
3. GRC can find the blocks
4. Block YAML format is correct
"""

import os
import sys
import yaml
from pathlib import Path

def check_block_files():
    """Check if block YAML files exist in expected locations."""
    print("=" * 60)
    print("Checking Block YAML Files")
    print("=" * 60)
    
    block_paths = [
        os.path.expanduser('~/.gnuradio/grc/blocks'),
        '/usr/share/gnuradio/grc/blocks',
        '/usr/local/share/gnuradio/grc/blocks',
    ]
    
    sleipnir_blocks = []
    for path in block_paths:
        if os.path.exists(path):
            for file in os.listdir(path):
                if 'sleipnir' in file.lower() and file.endswith('.block.yml'):
                    full_path = os.path.join(path, file)
                    sleipnir_blocks.append((path, file, full_path))
                    print(f"  Found: {full_path}")
    
    if not sleipnir_blocks:
        print("  ERROR: No sleipnir block files found!")
        return False
    
    print(f"\n  Found {len(sleipnir_blocks)} sleipnir block file(s)")
    return True

def check_block_yaml_format():
    """Check if block YAML files are valid."""
    print("\n" + "=" * 60)
    print("Checking Block YAML Format")
    print("=" * 60)
    
    block_paths = [
        os.path.expanduser('~/.gnuradio/grc/blocks'),
        '/usr/share/gnuradio/grc/blocks',
        '/usr/local/share/gnuradio/grc/blocks',
    ]
    
    all_valid = True
    for path in block_paths:
        if not os.path.exists(path):
            continue
        
        for file in os.listdir(path):
            if 'sleipnir' in file.lower() and file.endswith('.block.yml'):
                full_path = os.path.join(path, file)
                try:
                    with open(full_path, 'r') as f:
                        block_def = yaml.safe_load(f)
                    
                    # Check required fields
                    required = ['id', 'label', 'category', 'templates', 'file_format']
                    missing = [f for f in required if f not in block_def]
                    
                    if missing:
                        print(f"  ERROR: {file} missing fields: {missing}")
                        all_valid = False
                    else:
                        print(f"  OK: {file}")
                        print(f"    ID: {block_def['id']}")
                        print(f"    Label: {block_def['label']}")
                        print(f"    Category: {block_def['category']}")
                        print(f"    File format: {block_def['file_format']}")
                        
                        # Check templates
                        if 'imports' in block_def['templates']:
                            print(f"    Has imports: Yes")
                        if 'make' in block_def['templates']:
                            print(f"    Has make: Yes")
                
                except Exception as e:
                    print(f"  ERROR: {file} - {e}")
                    all_valid = False
    
    return all_valid

def check_module_import():
    """Check if sleipnir module can be imported."""
    print("\n" + "=" * 60)
    print("Checking Module Import")
    print("=" * 60)
    
    try:
        from gnuradio import sleipnir
        print("  OK: Module imported successfully")
        
        # Check for factory functions
        required_funcs = ['make_sleipnir_tx_hier', 'make_sleipnir_rx_hier']
        for func_name in required_funcs:
            if hasattr(sleipnir, func_name):
                print(f"  OK: {func_name} found")
            else:
                print(f"  ERROR: {func_name} not found")
                return False
        
        return True
    except ImportError as e:
        print(f"  ERROR: Cannot import sleipnir module: {e}")
        return False

def check_grc_block_discovery():
    """Try to use GRC's block discovery mechanism."""
    print("\n" + "=" * 60)
    print("Checking GRC Block Discovery")
    print("=" * 60)
    
    try:
        # Try to import GRC and check block paths
        import gnuradio.grc
        
        # Get block search paths
        try:
            from gnuradio.grc.core.platform import Platform
            platform = Platform()
            print(f"  GRC Platform found")
            print(f"  Block search paths:")
            for path in platform.block_paths:
                exists = os.path.exists(path)
                sleipnir_count = 0
                if exists:
                    sleipnir_count = len([f for f in os.listdir(path) 
                                         if 'sleipnir' in f.lower() and f.endswith('.block.yml')])
                print(f"    {path} (exists: {exists}, sleipnir blocks: {sleipnir_count})")
        except Exception as e:
            print(f"  WARNING: Could not get GRC platform: {e}")
            print(f"  This is normal if GRC is not fully initialized")
        
        return True
    except ImportError as e:
        print(f"  WARNING: Could not import GRC modules: {e}")
        print(f"  This is normal if running outside GRC")
        return True  # Not a critical error

def main():
    """Run all diagnostic checks."""
    print("gr-sleipnir GRC Block Diagnostic")
    print("=" * 60)
    print()
    
    results = {
        'block_files': check_block_files(),
        'yaml_format': check_block_yaml_format(),
        'module_import': check_module_import(),
        'grc_discovery': check_grc_block_discovery(),
    }
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_ok = all(results.values())
    
    for check, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  {check}: {status}")
    
    if all_ok:
        print("\n  All checks passed!")
        print("\n  If blocks still don't appear in GRC:")
        print("    1. Restart GNU Radio Companion")
        print("    2. Clear GRC cache (if it exists)")
        print("    3. Check GRC preferences for block paths")
        print("    4. Try installing blocks to system directory:")
        print("       sudo cp ~/.gnuradio/grc/blocks/sleipnir_*.block.yml /usr/share/gnuradio/grc/blocks/")
    else:
        print("\n  Some checks failed. Please review the errors above.")
    
    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())

