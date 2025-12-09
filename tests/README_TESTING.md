# gr-sleipnir Comprehensive Test Suite

This test suite provides automated testing of all gr-sleipnir blocks and parameters across varying channel conditions.

## Overview

The test suite exercises:
- All modulation modes (4FSK, 8FSK)
- All FEC rates
- All cryptographic modes (none, signing, encryption, both)
- Various channel conditions (clean, AWGN, fading, frequency offset)
- SNR range from -5 dB to 20 dB

## Files

- `test_sleipnir.py` - Main test script
- `test_crypto_key_sources.py` - Cryptographic key sources and security validation tests
- `config.yaml` - Test configuration
- `analyze_results.py` - Results analysis and plotting
- `README_TESTING.md` - This file

## Requirements

### Python Packages
- numpy
- matplotlib
- pyyaml
- GNU Radio 3.10+ with Python API
- gr-sleipnir (installed)
- gr-opus (for Opus encoding/decoding)

### Input Files
- WAV file for testing (default: `../wav/cq_pcm.wav`)
- Optional: Private key file for encryption testing
- Optional: MAC key for encryption testing

## Quick Start

### 1. Basic Test Run

Run a single test with default configuration:

```bash
cd tests
python test_sleipnir.py --single --wav ../wav/cq_pcm.wav
```

### 2. Full Test Suite

Run the complete test suite (may take several hours):

```bash
python test_sleipnir.py --wav ../wav/cq_pcm.wav --output test_results
```

### 3. Analyze Results

After running tests, analyze and plot results:

```bash
python analyze_results.py --results test_results --output analysis_output
```

## Configuration

Edit `config.yaml` to customize test parameters:

```yaml
# SNR sweep range
snr_range:
  start: -5
  end: 20
  step: 1

# Modulation modes to test
modulations:
  - "4FSK"
  - "8FSK"

# Crypto modes to test
crypto_modes:
  - "none"
  - "sign"
  - "encrypt"
  - "both"

# Channel conditions
channel_types:
  - "clean"
  - "AWGN"
  - "rayleigh"
  - "rician"
```

### Quick Test Configuration

For faster testing, use the `quick_test` section in `config.yaml`:

```yaml
quick_test:
  snr_range:
    start: 0
    end: 15
    step: 5
  modulations:
    - "4FSK"
  crypto_modes:
    - "none"
  channel_types:
    - "AWGN"
```

## Test Flow

The test flowgraph follows this structure:

```
WAV File Source
    ↓
[Resample if needed]
    ↓
gr-opus Encoder (9600 bps)
    ↓
sleipnir_framer
    ↓
sleipnir_encoder
    ↓
Channel Model (variable SNR/impairments)
    ↓
sleipnir_decoder
    ↓
sleipnir_deframer
    ↓
gr-opus Decoder
    ↓
WAV File Sink
```

## Metrics Collected

### Performance Metrics
- **Frame Error Rate (FER)** - Percentage of frames with errors
- **Bit Error Rate (BER)** - If measurable
- **Successful decode count** - Number of successfully decoded frames
- **Processing time/latency** - Time to process test duration

### Cryptographic Metrics
- **Signature verification success rate** - When signing enabled
- **Decryption success rate** - When encryption enabled
- **Crypto rejection rate** - Invalid signatures/keys rejected correctly

### Audio Quality Metrics
- **DC offset** - Check for DC bias in output
- **Dynamic range** - Preserved audio dynamic range
- **Clipping artifacts** - Detection of clipping
- **Sample rate match** - Input/output sample rate consistency
- **Audio SNR** - Signal-to-noise ratio of decoded audio
- **WARP-Q score** - Speech quality metric (if warpq available)

## Cryptographic Key Sources Testing

The `test_crypto_key_sources.py` test suite provides comprehensive testing of:

### Kernel Keyring Integration
- Load test keys via `kernel_keyring_source` block
- Generate signed/encrypted frames
- Verify decoder can authenticate/decrypt
- Full automation possible

### Nitrokey Integration (Conditional)
- Detect if Nitrokey present (`nitrokey --list`)
- If present, run hardware crypto tests
- If absent, skip with clear log message
- Prevents test failures in CI without hardware

### MAC Key Testing
- Test with various pre-shared keys via message ports
- Verify wrong MAC key causes decrypt failure
- Test key rotation (update MAC key mid-stream)
- Test MAC key forwarding from `key_source` to `ctrl` port
- Test invalid key handling (wrong length, malformed)
- Test message port saturation (rapid updates)
- Test ctrl multiplexing (multiple message types)

### Security Validation
- Unsigned frame rejected when signing enabled
- Wrong signature detected and rejected
- Encrypted frame without correct MAC key produces silence/error
- No plaintext leakage checks

Run the cryptographic key sources tests:
```bash
python tests/test_crypto_key_sources.py
```

## Validation Checks

The test suite includes comprehensive validation:

### Data Leakage Prevention
- Verify audio output contains only decoded voice, no framing data
- Check for metadata bleeding into audio stream
- Validate silence during frame sync loss (not random noise/data)

### Boundary Condition Tests
- Empty frames
- Maximum-length frames
- Truncated/corrupted frames
- Out-of-sequence frames
- Invalid crypto signatures (should reject cleanly, not crash)

### State Machine Validation
- Proper initialization from cold start
- Recovery after sync loss
- Handling of incomplete superframes
- Graceful degradation when FEC can't correct errors

### Crypto Sanity Checks
- Unsigned frames rejected when signature verification enabled
- Encrypted frames produce silence/error (not garbled audio) without proper keys
- No plaintext leakage when encryption enabled

### Audio Quality Guards
- Output sample rate matches input
- No DC offset in decoded audio
- Dynamic range preserved
- No clipping artifacts

## Output Files

### Test Results
- `all_results.json` - Complete test results in JSON format
- `results_summary.csv` - Summary in CSV format
- `test_XXXX/result.json` - Individual test results
- `test_XXXX/output_snrXX.X.wav` - Decoded audio for each test

### Analysis Output
- `fer_vs_snr_*.png` - FER vs SNR plots
- `comparison_*.png` - Comparison plots
- `summary.md` - Summary statistics table
- `test_report.md` - Comprehensive test report

## Performance Curves

The analysis script generates performance curves showing:
- FER vs SNR for different modulation modes
- FER vs SNR for different crypto modes
- FER vs SNR for different channel conditions
- Comparison plots at fixed SNR values

## Pass/Fail Criteria

Tests are evaluated against thresholds defined in `config.yaml`:

```yaml
validation:
  fer_threshold_good: 0.01      # FER < 1% is good
  fer_threshold_acceptable: 0.10 # FER < 10% is acceptable
  dc_offset_max: 0.01           # Maximum DC offset
  clipping_max_fraction: 0.001  # Maximum clipping (1% of samples)
  dynamic_range_min: 0.5        # Minimum dynamic range
  snr_audio_min_db: 20.0        # Minimum audio SNR (dB)
```

## Example Usage

### Run Quick Test
```bash
# Edit config.yaml to use quick_test parameters
python test_sleipnir.py --wav ../wav/cq_pcm.wav --output quick_test_results
```

### Run Single Test with Specific Parameters
```bash
# Edit config.yaml with desired parameters
python test_sleipnir.py --single --wav ../wav/cq_pcm.wav
```

### Analyze and Plot Results
```bash
python analyze_results.py --results test_results --output analysis
```

### View Results
```bash
# View summary
cat analysis/summary.md

# View full report
cat analysis/test_report.md

# View plots
ls analysis/*.png
```

## Troubleshooting

### Test Fails to Start
- Check that GNU Radio is properly installed
- Verify gr-sleipnir is installed and accessible
- Check that gr-opus is available
- Verify WAV file exists and is readable

### No Frames Decoded
- Check SNR is high enough (start with 10 dB)
- Verify channel model is working correctly
- Check that modulation parameters match between TX and RX

### Audio Quality Issues
- Check input WAV file quality
- Verify sample rate conversion is working
- Check for clipping in input audio
- Verify Opus encoder/decoder settings

### Crypto Tests Fail
- Verify private key file exists and is valid
- Check MAC key format (32 bytes)
- Ensure crypto libraries are available
- Check that key paths are correct

## Performance Expectations

Based on typical digital voice systems:

- **SNR > 10 dB**: Should achieve FER < 1%
- **SNR 5-10 dB**: Should achieve FER < 10%
- **SNR < 5 dB**: FER may be high, but system should not crash
- **Processing rate**: Should be > 1000 samples/second
- **Audio quality**: SNR > 20 dB for decoded audio

## Extending the Test Suite

### Adding New Test Cases

1. Edit `config.yaml` to add new parameter combinations
2. Modify `TestFlowgraph` class to handle new parameters
3. Update `MetricsCollector` to collect new metrics
4. Add validation checks in `analyze_audio_quality()`

### Adding New Channel Models

1. Extend `ChannelModel` class in `test_sleipnir.py`
2. Add new channel type to `config.yaml`
3. Update test flowgraph generation

### Adding New Metrics

1. Add metric collection in `MetricsCollector`
2. Update `analyze_audio_quality()` for audio metrics
3. Add plotting functions in `analyze_results.py`

## Contributing

When adding new tests or features:
- Follow existing code style
- Add documentation
- Update this README
- Include example configurations
- Test with both quick and full test suites

## License

Same as gr-sleipnir project.

