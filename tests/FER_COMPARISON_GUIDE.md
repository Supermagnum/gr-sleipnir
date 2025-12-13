# FER Comparison Samples Guide

## Overview

This guide explains how to generate and use comparison audio samples showing gr-sleipnir performance at different Frame Error Rate (FER) levels, compared to M17 Codec2.

## Quick Start

```bash
cd /home/haaken/github-projects/gr-sleipnir
python3 tests/generate_fer_comparison_samples.py
```

This will generate:
- Clean channel sample (~5% FER floor)
- 5% FER sample
- 10% FER sample
- Comparison summary JSON

## Generated Samples

### 1. Clean Channel (0% FER Target)

**Target**: 0% FER  
**Actual**: ~5% FER (hard-decision decoder floor)  
**SNR**: ~15-20 dB  
**Purpose**: Shows best-case performance with current decoder

**Characteristics**:
- Minimal frame errors (only decoder floor)
- Excellent audio quality (WarpQ ~4.8-5.0)
- Represents performance at very high SNR

### 2. 5% FER (Current Floor)

**Target**: 5% FER  
**Actual**: ~5% FER  
**SNR**: ~10-15 dB  
**Purpose**: Shows typical high-SNR performance

**Characteristics**:
- Represents the FER floor of hard-decision decoder
- Excellent audio quality maintained
- Operational threshold for voice communication

### 3. 10% FER (Degraded Conditions)

**Target**: 10% FER  
**Actual**: ~10% FER  
**SNR**: ~0-3 dB  
**Purpose**: Shows performance under challenging conditions

**Characteristics**:
- Higher frame error rate
- Still acceptable audio quality (WarpQ ~4.0-4.5)
- Represents weak signal conditions

## M17 Codec2 Comparison

### SNR Adjustment

M17 has a waterfall SNR of approximately +5 dB compared to gr-sleipnir. For fair comparison:

- **gr-sleipnir at 15 dB** → Compare with **M17 at 20 dB**
- **gr-sleipnir at 10 dB** → Compare with **M17 at 15 dB**
- **gr-sleipnir at 2 dB** → Compare with **M17 at 7 dB**

### Generating M17 Samples

If m17-tools is installed, the script will attempt to generate M17 samples automatically. Otherwise:

1. **Install m17-tools**:
   ```bash
   git clone https://github.com/m17-project/m17-tools.git
   cd m17-tools
   mkdir build && cd build
   cmake ..
   make
   sudo make install
   ```

2. **Encode with Codec2**:
   ```bash
   # M17 uses Codec2 at 3.2 kbps
   c2enc 3200 input.wav output.c2
   ```

3. **Transmit through channel** (use GNU Radio or similar):
   - Apply AWGN channel at target SNR
   - Use similar channel conditions as gr-sleipnir tests

4. **Decode**:
   ```bash
   c2dec output.c2 output.wav
   ```

### Comparison Points

| Metric | gr-sleipnir (8FSK) | M17 | Advantage |
|--------|-------------------|-----|-----------|
| Waterfall SNR | 0-1 dB | +5 dB | ~6 dB better |
| Operational SNR | 0-1 dB | +5-6 dB | ~5-6 dB better |
| FER Floor | ~5-7% | <1% (soft-decision) | M17 better |
| Audio Codec | Opus 6-8 kbps | Codec2 3.2 kbps | gr-sleipnir better |
| Audio Quality | Excellent | Good | gr-sleipnir better |

**Key Trade-offs**:
- gr-sleipnir: Better SNR performance, superior audio quality, but higher FER floor
- M17: Lower FER floor (soft-decision), but requires higher SNR and lower audio quality

## Using the Samples

### Listening Comparison

1. **Play samples side-by-side**:
   ```bash
   # gr-sleipnir samples
   aplay fer_comparison_samples/clean_channel/output_snr*.wav
   aplay fer_comparison_samples/fer_5pct/output_snr*.wav
   aplay fer_comparison_samples/fer_10pct/output_snr*.wav
   
   # M17 samples (if generated)
   aplay fer_comparison_samples/m17_comparison/m17_codec2_snr*.wav
   ```

2. **Compare audio quality**:
   - Listen for artifacts, distortion, intelligibility
   - Note differences in voice quality (Opus vs Codec2)
   - Assess impact of frame errors on audio

### Analysis

The summary JSON file contains detailed metrics:

```json
{
  "samples": {
    "clean": {
      "wav": "path/to/wav",
      "target_fer": 0.0,
      "actual_fer": 0.052,
      "snr_db": 20.0,
      "warpq_score": 4.87
    }
  }
}
```

Use these metrics to:
- Verify FER targets were met
- Compare audio quality scores
- Analyze SNR requirements

## Performance Context

### FER Floor Explanation

The ~5-7% FER floor is a fundamental limitation of hard-decision LDPC decoding:
- Hard-decision: Bits are 0 or 1 (no confidence information)
- Soft-decision: Bits have confidence values (better error correction)
- M17 uses soft-decision, achieving <1% FER floor
- gr-sleipnir uses hard-decision for simplicity and performance

**Impact**: Even at very high SNR, some frames will fail to decode. However:
- Audio quality remains excellent (WarpQ ~4.8-5.0)
- System remains operational
- Frame errors are typically brief and don't significantly impact intelligibility

### Operational Thresholds

- **FER < 5%**: Excellent quality, fully operational
- **FER 5-10%**: Good quality, operational with minor artifacts
- **FER 10-20%**: Acceptable quality, degraded but usable
- **FER > 20%**: Poor quality, may be unusable

## Customization

### Adjusting FER Targets

Edit the script to change target FER values:

```python
# In main() function
target_fer_clean = 0.0    # Change to desired value
target_fer_5pct = 0.05    # Change to desired value
target_fer_10pct = 0.10   # Change to desired value
```

### Different Channel Conditions

Modify channel type:

```python
generate_sample(
    input_wav,
    snr_db,
    modulation,
    output_dir,
    channel_type='rayleigh',  # or 'rician', 'clean'
    ...
)
```

### Different Modulation

Use 4FSK instead of 8FSK:

```bash
python3 tests/generate_fer_comparison_samples.py --modulation 4FSK
```

## Troubleshooting

### Script Fails to Find SNR Values

The script uses test results to find appropriate SNR values. If results aren't found:
1. Ensure `test-results-files/phase3.json` exists
2. Or run comprehensive tests: `python3 tests/test_comprehensive.py --config tests/config_comprehensive.yaml`

### M17 Samples Not Generated

If m17-tools is not installed:
1. Install m17-tools (see above)
2. Or generate samples manually using the instructions above

### Audio Quality Issues

If WarpQ scores are missing:
- Install warpq: `pip install warpq`
- Or check basic metrics in summary JSON

## References

- [FER Tracking Documentation](../docs/FER_TRACKING.md)
- [Test Results Documentation](../docs/TEST_RESULTS.md)
- [M17 Project](https://github.com/m17-project/m17-tools)
- [Codec2 Documentation](https://www.rowetel.com/?page_id=452)

