# GR-SLEIPNIR Comprehensive Test Suite Results

## Test Execution Summary

- **Total Tests Run**: 104
- **Test Duration**: ~9 minutes
- **Test Configuration**: `config_comprehensive.yaml`
- **Date**: 2025-12-09

## Test Coverage

### SNR Range
- Range: -5 dB to +19 dB
- Step: 2 dB
- Total SNR points: 13

### Modulation Modes
- 4FSK
- 8FSK

### Channel Conditions
- AWGN (Additive White Gaussian Noise)
- Rayleigh fading

### Frequency Offsets
- 0.0 Hz (no offset)
- 100.0 Hz (small offset)

### Crypto Modes
- None (baseline)

## Generated Reports

1. **FER vs SNR Plot** (`fer_vs_snr.png`)
   - Performance curves showing Frame Error Rate vs Signal-to-Noise Ratio
   - Separate curves for each modulation/channel combination
   - Includes threshold lines (1% and 10% FER)

2. **Summary Report** (`summary_report.txt`)
   - Overall statistics
   - Performance breakdown by modulation, channel type, and crypto mode
   - FER statistics (min, max, mean, median)

3. **Pass/Fail Report** (`pass_fail_report.txt`)
   - Validation results based on FER thresholds
   - Results grouped by SNR level
   - Pass criteria: FER < 1% (Good), FER < 10% (Acceptable)

4. **CSV Summary** (`../results_summary.csv`)
   - Machine-readable summary of all test results
   - Includes test number, SNR, modulation, crypto mode, channel type, frequency offset, FER, frame counts, and timing

5. **Individual Test Results** (`../test_XXXX/result.json`)
   - Detailed results for each test configuration
   - Includes metrics, audio quality analysis, and validation checks

6. **Decoded Audio Files** (`../test_XXXX/output_snr*.wav`)
   - Decoded audio output for subjective quality assessment
   - One file per test configuration

## Known Issues

During test execution, some opus encoder/decoder errors were observed:
- `Unable to cast Python instance of type <class 'NoneType'> to C++ type`
- These errors may affect frame decoding performance

## Metrics Collected

### Frame-Level Metrics
- **Frame Error Rate (FER)**: Percentage of frames that failed to decode
- **Frame Count**: Total number of frames processed
- **Error Count**: Number of frames with errors

### Audio Quality Metrics
- **DC Offset**: Measure of signal bias
- **Clipping**: Percentage of samples that exceed maximum amplitude
- **Dynamic Range**: Ratio of maximum to minimum signal levels
- **Audio SNR**: Signal-to-noise ratio of decoded audio (when WARP-Q available)

### Performance Metrics
- **Processing Rate**: Samples processed per second
- **Elapsed Time**: Total test execution time

## Validation Criteria

- **Good Performance**: FER < 1%
- **Acceptable Performance**: FER < 10%
- **Failed**: FER >= 10%

## Next Steps

1. Investigate opus encoder/decoder errors to improve frame decoding
2. Run tests with crypto modes enabled (sign, encrypt, both)
3. Test additional channel conditions (clean, Rician fading)
4. Test with larger frequency offsets (500 Hz, 1000 Hz)
5. Analyze audio quality metrics when frames are successfully decoded

## Files Structure

```
test_results_comprehensive/
├── all_results.json              # All test results in JSON format
├── results_summary.csv           # CSV summary for analysis
├── test_run.log                  # Test execution log
├── test_XXXX/                    # Individual test directories
│   ├── result.json              # Detailed test results
│   └── output_snr*.wav          # Decoded audio output
└── report/                       # Generated reports
    ├── fer_vs_snr.png           # FER vs SNR performance plot
    ├── summary_report.txt       # Summary statistics
    ├── pass_fail_report.txt     # Pass/fail validation report
    └── README.md                # This file
```

