# gr-sleipnir Comprehensive Test Suite

## Overview

The comprehensive test suite exercises all gr-sleipnir blocks and parameters across varying channel conditions, modulation modes, crypto configurations, and data modes.

## Quick Start

### Run Phase 1 Tests (Baseline)

```bash
cd /home/haaken/github-projects/gr-sleipnir
python3 tests/test_comprehensive.py --config tests/config_comprehensive.yaml --phase 1
```

### Run All Tests

```bash
python3 tests/test_comprehensive.py --config tests/config_comprehensive.yaml
```

### Dry Run (Validate Configuration)

```bash
python3 tests/test_comprehensive.py --config tests/config_comprehensive.yaml --dry-run
```

## Configuration

Edit `tests/config_comprehensive.yaml` to customize test parameters:

- **Modulation modes**: 4FSK, 8FSK
- **Crypto modes**: none, sign, encrypt, both
- **Channel conditions**: clean, AWGN, fading, frequency offset
- **SNR range**: Start, stop, and step values
- **Test duration**: Duration per test scenario

## Test Phases

### Phase 1: Critical Path
- Baseline tests (clean channel, no crypto)
- AWGN sweep with coarser SNR steps
- Quick validation of core functionality

### Phase 2: Full Coverage
- All modulation modes (4FSK, 8FSK)
- All crypto combinations
- Full SNR sweep
- Fading channels

### Phase 3: Edge Cases
- Frequency offset scenarios
- Key rotation tests
- Sync loss/recovery
- Boundary conditions

## Output Files

### Results Directory Structure

```
test_results_comprehensive/
├── results.json              # Full test results
├── summary.json              # Summary statistics
├── summary_table.md          # Summary table
├── report.md                 # Comprehensive report
├── audio/                    # Decoded audio files
│   └── output_*_snr*.wav
└── plots/                    # Performance curves
    ├── fer_vs_snr.png
    ├── warpq_vs_snr.png
    └── ber_vs_snr.png
```

## Metrics Collected

### Protocol Metrics
- **Frame Error Rate (FER)**: Percentage of frames that failed to decode
  - Calculation: `FER = frame_error_count / total_frames_received`
  - `frame_error_count`: Cumulative count of frames that were received but failed to decode
    - Includes frames that failed to parse
    - Includes frames with corrupted MACs
    - Includes corrupted frames misclassified as APRS/text (for voice-only tests)
  - `total_frames_received`: Cumulative count of all frames received from the channel
  - For voice-only tests, only Opus frames are counted as successful; APRS/text frames are treated as corrupted voice frames
  - **Note**: FER tracking was fixed to correctly identify corrupted frames that were previously misclassified
- **Frame Count**: Total number of Opus frames successfully decoded
- **Frame Error Count**: Cumulative count of frames that failed to decode
- **Total Frames Received**: Cumulative count of all frames received (for accurate FER calculation)
- Bit Error Rate (BER)
- Superframe decode success rate
- LDPC decoder iterations/convergence

### Audio Quality
- WarpQ scores
- SNR/PSNR
- Subjective quality assessment

### Crypto Validation
- Signature verification success rate
- Decryption success rate
- MAC verification success rate

### Sync Performance
- Sync acquisition time
- Sync state transitions
- Sync loss recovery time

## Analyzing Results

### Generate Performance Curves

```bash
python3 tests/analyze_results.py \
    --input test_results_comprehensive/results.json \
    --plots-dir test_results_comprehensive/plots
```

### Generate Summary Table

```bash
python3 tests/analyze_results.py \
    --input test_results_comprehensive/results.json \
    --summary-table test_results_comprehensive/summary_table.md
```

### Generate Report

```bash
python3 tests/analyze_results.py \
    --input test_results_comprehensive/results.json \
    --output test_results_comprehensive/report.md
```

## Pass Criteria

Tests are evaluated against pass criteria defined in `config_comprehensive.yaml`:

- **FER < 1%** at SNR > 10 dB (4FSK)
- **FER < 1%** at SNR > 13 dB (8FSK)
- **WarpQ > 2.5** at operational SNR
- **WarpQ > 3.0** at SNR > 10 dB
- **100% crypto verification** when properly keyed
- **Sync acquisition < 1 second**
- **Sync recovery < 2 seconds**

## Troubleshooting

### Missing Input File

Ensure `wav/cq_pcm.wav` exists or update `input_file` in config.

### Missing Matrix Files

Ensure LDPC matrix files exist:
- `ldpc_matrices/ldpc_auth_768_256.alist`
- `ldpc_matrices/ldpc_rate34.alist` (for 4FSK)
- `ldpc_matrices/ldpc_rate23.alist` (for 8FSK)

### Test Timeout

Increase `test_duration` in config or check for flowgraph deadlocks.

### Memory Issues

Reduce `max_tests` parameter or run tests in smaller batches.

## Expected Runtime

- **Phase 1**: ~5-10 minutes
- **Phase 2**: ~1-2 hours
- **Phase 3**: ~30-60 minutes
- **Full Suite**: ~2-4 hours

## Advanced Usage

### Run Specific Test Subset

```bash
python3 tests/test_comprehensive.py \
    --config tests/config_comprehensive.yaml \
    --phase 1 \
    --max-tests 10
```

### Custom Configuration

Create a custom config file:

```yaml
test_parameters:
  input_file: "path/to/your/audio.wav"
  modulation_modes: [4]
  snr_range: [0, 15, 5]
  # ... other parameters
```

Then run:

```bash
python3 tests/test_comprehensive.py --config your_config.yaml
```

## Integration with CI/CD

The test suite can be integrated into CI/CD pipelines:

```bash
# Run Phase 1 tests
python3 tests/test_comprehensive.py --phase 1

# Check pass rate
python3 -c "
import json
with open('test_results_comprehensive/summary.json') as f:
    summary = json.load(f)
    exit(0 if summary['pass_rate'] > 0.9 else 1)
"
```

## Documentation

- **Configuration Schema**: See `config_comprehensive.yaml` comments
- **Metrics Definitions**: See `metrics_collector.py`
- **Flowgraph Builder**: See `flowgraph_builder.py`
- **Results Format**: See `results.json` structure
