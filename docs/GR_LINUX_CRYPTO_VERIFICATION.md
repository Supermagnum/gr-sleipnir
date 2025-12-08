# gr-linux-crypto Verification Guide

This guide helps verify that gr-linux-crypto is correctly installed and can be used by gr-sleipnir.

## Verification Steps

### 1. Check Installation

Verify that gr-linux-crypto is installed:

```bash
# Check if module files exist
ls -la /usr/local/lib/python3.*/dist-packages/ | grep linux_crypto
ls -la /usr/lib/python3.*/dist-packages/ | grep linux_crypto

# Check GNU Radio can find it
gnuradio-config-info --enabled-components | grep -i linux
```

### 2. Test Python Import

Test if gr-linux-crypto can be imported:

```python
# Try different import methods
try:
    import linux_crypto
    print("SUCCESS: linux_crypto")
except ImportError:
    print("FAILED: linux_crypto")

try:
    from gnuradio import linux_crypto
    print("SUCCESS: gnuradio.linux_crypto")
except ImportError:
    print("FAILED: gnuradio.linux_crypto")
```

### 3. Check Available Blocks

Once imported, check what blocks are available:

```python
import linux_crypto  # or from gnuradio import linux_crypto

# List all attributes
print("Available attributes:")
for attr in dir(linux_crypto):
    if not attr.startswith('_'):
        print(f"  - {attr}")

# Look for make functions
make_funcs = [attr for attr in dir(linux_crypto) if attr.startswith('make_')]
print(f"\nMake functions: {make_funcs}")
```

### 4. Test Block Creation

Try creating a block:

```python
import linux_crypto

# Try common function names
try:
    block = linux_crypto.make_ecdsa_sign("/path/to/key.pem", "brainpoolP256r1")
    print("SUCCESS: Created ecdsa_sign block")
except AttributeError:
    print("make_ecdsa_sign not found")

try:
    block = linux_crypto.ecdsa_sign_make("/path/to/key.pem")
    print("SUCCESS: Created ecdsa_sign block (alternative name)")
except AttributeError:
    print("ecdsa_sign_make not found")
```

### 5. Verify in gr-sleipnir

Run the gr-sleipnir detection:

```python
cd /home/haaken/github-projects/gr-sleipnir
python3 -c "
import sys
sys.path.insert(0, '.')
from python.crypto_integration import LINUX_CRYPTO_AVAILABLE, LINUX_CRYPTO_MODULE
print(f'gr-linux-crypto available: {LINUX_CRYPTO_AVAILABLE}')
if LINUX_CRYPTO_MODULE:
    print(f'Module: {LINUX_CRYPTO_MODULE}')
    print(f'Location: {getattr(LINUX_CRYPTO_MODULE, \"__file__\", \"unknown\")}')
"
```

## Common Issues

### Issue: Module Not Found

**Symptoms**: `ImportError: No module named 'linux_crypto'`

**Solutions**:
1. Verify installation:
   ```bash
   cd gr-linux-crypto/build
   sudo make install
   sudo ldconfig
   ```

2. Check Python path:
   ```python
   import sys
   print(sys.path)
   ```

3. Verify installation location:
   ```bash
   find /usr -name "*linux_crypto*" 2>/dev/null
   find /usr/local -name "*linux_crypto*" 2>/dev/null
   ```

### Issue: Wrong Import Name

**Symptoms**: Import works but blocks not found

**Solutions**:
1. Check actual module name:
   ```bash
   python3 -c "import pkgutil; [print(m.name) for _, m, _ in pkgutil.iter_modules() if 'linux' in m.name.lower()]"
   ```

2. Try alternative imports (see verification step 2)

### Issue: Blocks Not Available

**Symptoms**: Module imports but no make functions found

**Solutions**:
1. Check if blocks are registered:
   ```python
   import linux_crypto
   print([x for x in dir(linux_crypto) if 'ecdsa' in x.lower()])
   ```

2. Verify block names match gr-linux-crypto documentation

3. Check GNU Radio version compatibility

## Integration Status

gr-sleipnir will automatically detect gr-linux-crypto if it's available. The integration code:

1. **Tries multiple import methods** to find gr-linux-crypto
2. **Logs success/failure** when importing
3. **Falls back to Python implementation** if not available
4. **Uses gr-linux-crypto blocks** when detected

## Expected Output

When gr-linux-crypto is correctly installed, you should see:

```
SUCCESS: gr-linux-crypto found as 'linux_crypto'
  Found make functions: ['make_ecdsa_sign', 'make_ecdsa_verify', ...]
```

When not available:

```
Warning: gr-linux-crypto not available. Using Python fallback.
  Tried imports: linux_crypto, gnuradio.linux_crypto, gr_linux_crypto
  To use gr-linux-crypto, ensure it's installed and GNU Radio can find it.
```

## Next Steps

Once verified:
1. gr-sleipnir will automatically use gr-linux-crypto blocks when available
2. Performance should improve (hardware acceleration if available)
3. Check logs to confirm gr-linux-crypto is being used

