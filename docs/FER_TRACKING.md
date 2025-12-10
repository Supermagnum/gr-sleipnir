# Frame Error Rate (FER) Tracking

## Overview

The gr-sleipnir test suite includes comprehensive Frame Error Rate (FER) tracking to accurately measure protocol performance under various channel conditions. This document describes how FER is calculated and tracked.

## FER Calculation

Frame Error Rate is calculated as:

```
FER = frame_error_count / total_frames_received
```

Where:
- **frame_error_count**: Cumulative count of frames that were received but failed to decode
- **total_frames_received**: Cumulative count of all frames received from the channel (successful + failed)

## Error Counting Logic

The `sleipnir_superframe_parser` block tracks frame errors using the following logic:

### 1. Per-Superframe Error Counting

For each superframe processed, errors are counted as:
- **frames_failed_to_parse**: Frames that failed to parse (exceptions, invalid structure)
- **frames_failed_mac**: Frames with corrupted MACs (all-zero or all-0xFF patterns)
- **frames_with_no_output**: Frames that parsed but produced no output (no Opus/APRS/text data)

### 2. Cumulative Error Calculation

The cumulative error count is calculated as:

```
calculated_errors = total_frames_received - cumulative_opus_frames_decoded
```

This direct calculation ensures accuracy, especially for voice-only tests where:
- Only Opus frames are counted as successful
- APRS/text frames are treated as corrupted voice frames (misclassified due to frame_type byte corruption)

### 3. Error Sources

Frames are counted as errors if they:
1. Fail to parse (raise exceptions during parsing)
2. Have corrupted MACs (suspicious patterns detected)
3. Parse successfully but produce no output (no valid Opus/APRS/text data)
4. Are misclassified as APRS/text in voice-only tests (frame_type byte corruption)

## Implementation Details

### Superframe Parser

The `sleipnir_superframe_parser` block:
- Tracks `self.frame_error_count` (cumulative errors)
- Tracks `self.total_frames_received` (cumulative total)
- Tracks `self._cumulative_opus_frames` (cumulative successful Opus frames)
- Emits status messages with these metrics after each superframe

### Metrics Collector

The `MetricsCollectorBlock` (GNU Radio block):
- Receives status messages from the superframe parser
- Extracts `frame_error_count` and `total_frames_received`
- Uses `max()` to keep the latest cumulative values

The `MetricsCollector` (post-processing):
- Computes FER using: `frame_error_count / total_frames_received`
- Falls back to `frame_error_count / (frame_count + frame_error_count)` if `total_frames_received` is not available

## Validation

FER values are validated against SNR-based thresholds:

- **SNR ≥ 15 dB**: FER < 0.1% (0.001)
- **SNR ≥ 10 dB**: FER < 1% (0.01)
- **SNR < 10 dB**: FER < 10% (0.10)

Tests that exceed these thresholds fail validation.

## Known Issues and Fixes

### Issue: FER Always 0.0

**Problem**: `frame_error_count` was always 0, even when frames were failing to decode.

**Root Cause**: Corrupted frames were being misclassified as APRS/text frames (due to frame_type byte corruption), so they were counted as successful instead of errors.

**Fix**: Changed error calculation to only count Opus frames as successful for voice-only tests. The calculation is now:
```
errors = total_frames_received - opus_frames_decoded
```

This ensures that corrupted frames (misclassified as APRS/text) are correctly counted as errors.

### Verification

The fix was verified with a single test at SNR -5.0 dB:
- `frame_count`: 589 (successfully decoded Opus frames)
- `frame_error_count`: 395 (frames that failed)
- `total_frames_received`: 984 (all frames received)
- `fer`: 0.4014 (40.14% frame error rate) ✓

## Usage in Test Suite

The test suite automatically collects FER metrics for each test scenario:

```python
metrics = {
    'frame_count': 589,
    'frame_error_count': 395,
    'total_frames_received': 984,
    'fer': 0.4014
}
```

These metrics are included in test results and used for validation and performance analysis.

## References

- `python/sleipnir_superframe_parser.py`: Superframe parser with error tracking
- `tests/metrics_collector.py`: Metrics collection and FER calculation
- `tests/test_comprehensive.py`: Test suite that validates FER thresholds

