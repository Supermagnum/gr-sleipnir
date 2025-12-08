# Sync Frame Implementation

This document describes the implementation of periodic sync frames for receiver acquisition in gr-sleipnir.

## Overview

Periodic sync frames are inserted into the superframe stream to aid receiver acquisition and synchronization. Sync frames are only used when signing is disabled (when signing is enabled, Frame 0 serves as the sync marker).

## Implementation

### TX Side: Sync Frame Generation

**File**: `python/sleipnir_superframe_assembler.py`

**Features**:
- Inserts sync frame every N superframes (configurable, default: 5)
- Sync frame replaces first voice frame in superframe
- Sync frame structure: 64-bit sync pattern + superframe counter + frame counter + padding

**Configuration**:
- `enable_sync_frames`: Enable/disable sync frame generation (default: True)
- `sync_frame_interval`: Insert sync frame every N superframes (default: 5)

**Sync Frame Structure** (48 bytes, same as voice frame):
```
Bytes 0-7:   Sync pattern (64 bits, fixed: 0xDEADBEEFCAFEBABE)
Bytes 8-11:  Superframe counter (32 bits, big-endian)
Bytes 12-15: Frame counter (32 bits, always 0 for sync frame)
Bytes 16-47: Reserved/padding (zeros)
```

**Usage**:
```python
assembler = make_sleipnir_superframe_assembler(
    callsign="N0CALL",
    enable_signing=False,  # Sync frames only when signing disabled
    enable_sync_frames=True,
    sync_frame_interval=5  # Insert every 5 superframes
)
```

### RX Side: Sync Frame Detection

**File**: `python/sleipnir_superframe_parser.py`

**Features**:
- Detects sync frames by pattern matching
- Validates sync frame structure
- Updates sync state and frame counter
- Maintains sync state: "searching", "synced", "lost"

**Sync Detection Process**:
1. **Pattern Matching**: Search for sync pattern (0xDEADBEEFCAFEBABE) in decoded data
2. **Validation**: Verify sync frame structure (pattern + counters)
3. **State Update**: Update sync state and superframe counter
4. **Frame Parsing**: Parse frames starting from sync frame position

**Sync State**:
- **"searching"**: Initial state, looking for sync frame
- **synced"**: Sync acquired, counter validated
- **"lost"**: Counter mismatch detected, sync may be lost

**Configuration**:
- `enable_sync_detection`: Enable/disable sync frame detection (default: True)

**Usage**:
```python
parser = make_sleipnir_superframe_parser(
    local_callsign="N0CALL",
    enable_sync_detection=True
)
```

## Sync Frame Behavior

### When Signing is Enabled

- **Sync frames**: NOT inserted (Frame 0 serves as sync marker)
- **Acquisition**: Uses Frame 0 for synchronization
- **Overhead**: None (Frame 0 already present)

### When Signing is Disabled

- **Sync frames**: Inserted every N superframes (default: 5)
- **Acquisition**: Uses sync frames for fast acquisition
- **Overhead**: ~0.2% (1 sync frame per 125 frames = 1 per 5 seconds)

## Performance Characteristics

### Bandwidth Overhead

- **Sync frame interval**: 5 superframes (default)
- **Overhead**: 1 frame per 125 frames = 0.8% per superframe = ~0.2% overall
- **Bandwidth cost**: Minimal (48 bytes per sync frame)

### Acquisition Time

- **With sync frames**: < 1 second (first sync frame at 5 seconds)
- **Without sync frames**: 1-5 seconds (LDPC decoder sync)

### Sync Maintenance

- **Counter validation**: Validates superframe counter increment
- **Sync loss detection**: Detects counter mismatches
- **Recovery**: Automatically re-acquires on next sync frame

## Integration

### TX Hierarchical Block

Sync frames are automatically inserted by the superframe assembler when:
- Signing is disabled
- `enable_sync_frames=True` (default)

No additional configuration needed in hierarchical blocks.

### RX Hierarchical Block

Sync detection is automatically enabled by the superframe parser when:
- `enable_sync_detection=True` (default)

Sync state is reported in status messages:
```python
status = {
    'sync_state': 'synced',  # or 'searching', 'lost'
    'superframe_counter': 42,
    # ... other status fields
}
```

## Testing

### Test Sync Frame Generation

```python
from python.sleipnir_superframe_assembler import make_sleipnir_superframe_assembler

# Create assembler with sync frames enabled
assembler = make_sleipnir_superframe_assembler(
    callsign="TEST",
    enable_signing=False,
    enable_sync_frames=True,
    sync_frame_interval=5
)

# Generate superframes and verify sync frame insertion
# Sync frame should appear at superframe_counter % 5 == 0
```

### Test Sync Frame Detection

```python
from python.sleipnir_superframe_parser import make_sleipnir_superframe_parser

# Create parser with sync detection enabled
parser = make_sleipnir_superframe_parser(
    local_callsign="TEST",
    enable_sync_detection=True
)

# Process decoded frames and verify sync detection
# Check status messages for sync_state updates
```

## Troubleshooting

### Sync Frames Not Detected

**Symptoms**: `sync_state` remains "searching"

**Possible causes**:
- Sync frames not being generated (check `enable_sync_frames`)
- Sync pattern mismatch (verify sync pattern constant)
- Frame alignment issues (check LDPC decoder output)

**Solutions**:
- Verify TX is generating sync frames
- Check sync pattern matches (0xDEADBEEFCAFEBABE)
- Verify frame boundaries are correct

### Sync State "Lost"

**Symptoms**: `sync_state` changes to "lost"

**Possible causes**:
- Counter mismatch (frames dropped or corrupted)
- Superframe counter overflow
- Multiple transmitters

**Solutions**:
- Check for frame drops in LDPC decoder
- Verify single transmitter
- Allow counter to wrap (modulo 2^32)

### High Overhead

**Symptoms**: Too many sync frames

**Solutions**:
- Increase `sync_frame_interval` (e.g., 10 instead of 5)
- Disable sync frames if not needed (`enable_sync_frames=False`)

## Future Enhancements

Potential improvements:
- **Adaptive sync interval**: Adjust interval based on channel conditions
- **Multiple sync patterns**: Use different patterns for different transmitters
- **Sync frame encryption**: Encrypt sync frame payload (currently plaintext)
- **Sync frame MAC**: Add MAC to sync frame for integrity

## References

- [Sync Frame Analysis](SYNC_FRAME_ANALYSIS.md) - Detailed analysis of sync frame requirements
- [Superframe Implementation](SUPERFRAME_IMPLEMENTATION.md) - Overall superframe structure

