# gr-sleipnir Performance Report - Complete Analysis

Generated: 2025-12-11 14:21:23

## Executive Summary

- **4FSK FER Floor**: 6.04%
- **8FSK FER Floor**: 4.01%
- **8FSK Advantage**: 2.02 percentage points lower FER
- **Recommendation**: 8FSK has better error correction performance

## 4FSK Complete Analysis (3,864 tests)

### FER Floor
- Mean: 6.04%
- Median: 4.40%
- Std Dev: 3.36%
- Range: 4.00% - 19.33%
- Sample Size: 1848 tests

### Channel Performance

**clean**:
- FER Floor: 4.55%
- Operational SNR: 0.0 dB

**awgn**:
- FER Floor: 4.68%
- Operational SNR: -2.0 dB

**rayleigh**:
- FER Floor: 4.78%
- Operational SNR: 3.0 dB

**rician**:
- FER Floor: 4.66%
- Operational SNR: 3.0 dB

**freq_offset_100hz**:
- FER Floor: 5.15%
- Operational SNR: -2.0 dB

**freq_offset_500hz**:
- FER Floor: 5.32%
- Operational SNR: -2.0 dB

**freq_offset_1khz**:
- FER Floor: 13.12%

### Crypto Overhead

**sign**:
- FER Increase: 0.90 percentage points (17.1%)

**encrypt**:
- FER Increase: 1.01 percentage points (19.2%)

**both**:
- FER Increase: 1.09 percentage points (20.6%)

### Frequency Offset Tolerance

**freq_offset_100hz**: FER Floor 5.15%
**freq_offset_500hz**: FER Floor 5.32%
**freq_offset_1khz**: FER Floor 13.12%

### Fading Penalties

- Rayleigh vs AWGN: 0.10 percentage points FER increase
- Rician vs AWGN: -0.02 percentage points FER increase

## 8FSK Baseline Analysis (crypto='none', 966 tests)

### FER Floor: 4.01%

## 4FSK vs 8FSK Comparison

### FER Floor Difference
- 4FSK: 5.28%
- 8FSK: 4.01%
- Difference: -1.27 percentage points
- Percent Change: -24.1%

## Mode Selection Recommendations

### Primary Recommendation: **8FSK**

8FSK demonstrates superior performance:
- Lower FER floor (4.01% vs 6.04%)
- Better error correction capability
- Higher audio bitrate (8 kbps vs 6 kbps)
- Better frequency tolerance at ±500 Hz

### Use Cases

**Use 8FSK when:**
- Fixed station operation
- Good SNR available (≥0 dB)
- Frequency stability ±500 Hz or better
- Maximum audio quality desired

**Use 4FSK when:**
- Portable/QRP operation
- Weak signal conditions
- Frequency stability concerns (±100 Hz recommended)
- Maximum range desired