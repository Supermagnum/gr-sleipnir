# FER Comparison Sample Generation

This tool generates audio comparison samples at specific Frame Error Rate (FER) levels to demonstrate gr-sleipnir performance compared to M17 Codec2.

## Overview

The script generates three sets of audio samples:

1. **Clean Channel (0% FER target)**: Actually produces ~5% FER (the hard-decision decoder floor)
2. **5% FER**: Current performance floor at high SNR
3. **10% FER**: Degraded conditions at lower SNR

Each sample is compared with M17 Codec2 at similar SNR conditions.

## Usage

### Basic Usage

```bash
cd /home/haaken/github-projects/gr-sleipnir
python3 tests/generate_fer_comparison_samples.py
```

### Options

```bash
python3 tests/generate_fer_comparison_samples.py \
    --input wav/cq_pcm.wav \
    --output fer_comparison_samples \
    --modulation 8FSK \
    --duration 5.0
```

**Arguments:**
- `--input`: Input WAV file (default: `wav/cq_pcm.wav`)
- `--output`: Output directory (default: `fer_comparison_samples`)
- `--modulation`: Modulation mode - `4FSK` or `8FSK` (default: `8FSK`)
- `--duration`: Sample duration in seconds (default: `5.0`)

## Output

The script generates:

1. **Audio Samples**: WAV files for each FER level
   - `clean_channel/output_snr*.wav` - Clean channel sample
   - `fer_5pct/output_snr*.wav` - 5% FER sample
   - `fer_10pct/output_snr*.wav` - 10% FER sample

2. **Summary File**: `comparison_summary.json` with metadata:
   - Target and actual FER values
   - SNR values used
   - WarpQ audio quality scores
   - File paths

3. **M17 Comparison**: If m17-tools is installed, generates M17 Codec2 samples at similar SNR

## M17 Comparison

The script attempts to generate M17 Codec2 comparison samples. If `m17-tools` is not installed, it will provide instructions for manual generation.

### Installing M17 Tools

```bash
# Clone and build m17-tools
git clone https://github.com/m17-project/m17-tools.git
cd m17-tools
mkdir build && cd build
cmake ..
make
sudo make install
```

### Manual M17 Sample Generation

If m17-tools is not available, you can generate M17 samples manually:

1. Encode audio with Codec2 at 3.2 kbps (M17 standard)
2. Transmit through channel at similar SNR as gr-sleipnir samples
3. Decode and save output

Note: M17 waterfall SNR is approximately +5 dB higher than gr-sleipnir, so adjust SNR accordingly for fair comparison.

## Understanding the Results

### FER Levels

- **0% FER (Clean Channel)**: Not achievable due to hard-decision decoder floor (~5-6%). Sample uses very high SNR (15-20 dB) to approach the floor.
- **5% FER**: Current performance floor at high SNR (10-15 dB). This represents the best achievable performance with the current hard-decision LDPC decoder.
- **10% FER**: Degraded conditions at lower SNR (0-3 dB). Represents performance under challenging channel conditions.

### SNR Values

The script automatically finds appropriate SNR values from test results (if available) or uses estimates based on known performance:

- **Clean channel**: ~15-20 dB SNR (produces ~5% FER floor)
- **5% FER**: ~10-15 dB SNR (produces ~5% FER)
- **10% FER**: ~0-3 dB SNR (produces ~10% FER)

### Audio Quality

WarpQ scores are included in the summary:
- **4.0-5.0**: Excellent quality (minimal artifacts)
- **3.0-3.9**: Good quality (acceptable, minor artifacts)
- **< 3.0**: Fair to poor quality (noticeable degradation)

## Performance Notes

### gr-sleipnir vs M17

Based on test results:
- **gr-sleipnir (8FSK)**: Operational SNR 0-1 dB, FER floor ~5-7%
- **M17**: Waterfall SNR ~+5 dB, uses Codec2 3.2 kbps
- **Advantage**: gr-sleipnir achieves ~6 dB better SNR performance
- **Audio Quality**: gr-sleipnir uses Opus 6-8 kbps vs M17's Codec2 3.2 kbps, providing superior audio quality

### FER Floor Limitation

The hard-decision LDPC decoder introduces a fundamental FER floor of ~5-7% even at very high SNR. This prevents achieving <1% FER that would be possible with soft-decision decoding. However, the system remains operational and provides excellent audio quality even with this floor.

## Example Output

```
======================================================================
COMPARISON SAMPLES GENERATED
======================================================================
Output directory: fer_comparison_samples
Summary file: fer_comparison_samples/comparison_summary.json

Generated samples:
  clean:
    WAV: fer_comparison_samples/clean_channel/output_snr20.0.wav
    Target FER: 0.0%
    Actual FER: 5.2%
    SNR: 20.0 dB
    WarpQ: 4.87
  fer_5pct:
    WAV: fer_comparison_samples/fer_5pct/output_snr10.0.wav
    Target FER: 5.0%
    Actual FER: 5.1%
    SNR: 10.0 dB
    WarpQ: 4.85
  fer_10pct:
    WAV: fer_comparison_samples/fer_10pct/output_snr2.0.wav
    Target FER: 10.0%
    Actual FER: 9.8%
    SNR: 2.0 dB
    WarpQ: 4.52
```

## Troubleshooting

### Test Results Not Found

If the script cannot find test results, it will use estimated SNR values. To use actual test data:
1. Ensure `test-results-files/phase3.json` exists
2. Run the comprehensive test suite if needed: `python3 tests/test_comprehensive.py`

### M17 Tools Not Available

The script will continue without M17 samples. Follow the installation instructions above or generate M17 samples manually.

### Audio Quality Issues

If WarpQ scores are not available:
- Install warpq: `pip install warpq`
- Or use basic audio metrics from the summary JSON

## References

- [FER Tracking Documentation](../docs/FER_TRACKING.md)
- [Test Results Documentation](../docs/TEST_RESULTS.md)
- [M17 Project](https://github.com/m17-project/m17-tools)

