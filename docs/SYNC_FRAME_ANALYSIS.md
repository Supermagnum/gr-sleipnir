# Sync Frame Analysis

This document analyzes whether periodic sync frames are needed for receiver acquisition in gr-sleipnir.

## Current Superframe Structure

The gr-sleipnir superframe consists of:
- **25 frames per superframe** (1 second total)
- **Frame 0**: Optional authentication frame with ECDSA signature (32 bytes payload, 768 bits coded)
- **Frames 1-24**: Voice frames with Opus audio + MAC (48 bytes payload, 576 bits coded)
- **Frame duration**: 40ms per frame

## Receiver Acquisition Requirements

### Frame Synchronization

The receiver needs to:
1. **Detect frame boundaries**: Know where each 40ms frame starts
2. **Identify frame type**: Distinguish Frame 0 (auth) from Frames 1-24 (voice)
3. **Maintain synchronization**: Track frame counter and superframe boundaries

### Current Synchronization Mechanisms

#### 1. Frame 0 as Sync Marker

**When signing is enabled**, Frame 0 serves as a natural sync marker:
- **Unique structure**: Different LDPC matrix (rate 1/3 vs rate 2/3)
- **Fixed position**: Always first frame in superframe
- **Predictable pattern**: Repeats every 1 second (25 frames)

**Advantages**:
- No overhead when signing is enabled
- Natural sync point
- Provides authentication in addition to sync

**Disadvantages**:
- Only available when signing is enabled
- If Frame 0 is corrupted, sync may be lost
- No sync marker when signing is disabled

#### 2. LDPC Decoder Sync

The LDPC decoder can provide frame synchronization:
- **Frame 0**: 768 bits coded (96 bytes) → 256 bits info (32 bytes)
- **Frames 1-24**: 576 bits coded (72 bytes) → 384 bits info (48 bytes)

**Advantages**:
- Works regardless of signing status
- Built into error correction
- Can detect frame boundaries through decoding success

**Disadvantages**:
- Requires successful LDPC decoding to detect sync
- May be slow in poor SNR conditions
- Frame type detection requires decoding both matrices

#### 3. Symbol-Level Sync

The 4FSK/8FSK demodulator provides symbol-level synchronization:
- Symbol timing recovery
- Frequency offset correction
- Bit-level synchronization

**Advantages**:
- Fast acquisition
- Works at low level
- Independent of frame structure

**Disadvantages**:
- Does not provide frame boundary information
- Requires additional logic to detect frame boundaries

## Analysis: Are Periodic Sync Frames Needed?

### Scenario 1: Signing Enabled

**Current approach**: Frame 0 serves as sync marker

**Assessment**: **Sync frames NOT needed**

**Reasoning**:
- Frame 0 provides natural sync point every 1 second
- Unique structure (different LDPC matrix) aids detection
- 1-second sync interval is sufficient for most scenarios
- No additional overhead required

**Recommendation**: Use Frame 0 as sync marker, no additional sync frames needed

### Scenario 2: Signing Disabled

**Current approach**: Rely on LDPC decoder sync

**Assessment**: **Sync frames MAY be needed**

**Reasoning**:
- No natural sync marker when signing is disabled
- LDPC decoder sync may be slow in poor SNR
- Frame boundary detection requires decoding attempts

**Options**:

#### Option A: Periodic Sync Frames (Recommended)

Insert sync frames periodically (e.g., every N superframes):
- **Frequency**: Every 5-10 superframes (5-10 seconds)
- **Structure**: Fixed sync pattern (e.g., 64-bit sync word)
- **Overhead**: ~0.1-0.2% (1 frame per 125-250 frames)

**Advantages**:
- Fast acquisition
- Works in poor SNR
- Predictable sync points
- Low overhead

**Disadvantages**:
- Small bandwidth overhead
- Requires sync frame detection logic

#### Option B: Enhanced LDPC Sync

Improve LDPC decoder sync detection:
- Use frame-aware LDPC decoder
- Detect frame type through decoding success
- Use frame counter for validation

**Advantages**:
- No bandwidth overhead
- Uses existing error correction

**Disadvantages**:
- Slower acquisition
- May fail in very poor SNR
- More complex implementation

#### Option C: Hybrid Approach

Combine both methods:
- Use sync frames for initial acquisition
- Use LDPC sync for maintenance

**Advantages**:
- Fast initial acquisition
- Robust maintenance
- Best of both worlds

**Disadvantages**:
- More complex implementation
- Some bandwidth overhead

### Recommendation

**For signing-enabled operation**: No sync frames needed, Frame 0 serves as sync marker.

**For signing-disabled operation**: Implement periodic sync frames every 5-10 superframes.

## Proposed Sync Frame Design

### Sync Frame Structure

If periodic sync frames are implemented:

```
Sync Frame Payload (48 bytes, same as voice frame):
- Bytes 0-7:   Sync pattern (64 bits, fixed value)
- Bytes 8-11:  Superframe counter (32 bits)
- Bytes 12-15: Frame counter (32 bits, always 0 for sync frame)
- Bytes 16-47: Reserved/padding
```

**Sync Pattern**: Fixed 64-bit value (e.g., `0xDEADBEEFCAFEBABE`)

**Encoding**: Use voice frame LDPC matrix (rate 2/3) for consistency

### Sync Frame Detection

Receiver detects sync frames by:
1. **Pattern matching**: Look for sync pattern in decoded frames
2. **Counter validation**: Verify superframe counter is incrementing
3. **Position validation**: Sync frames occur at predictable intervals

### Implementation Considerations

#### TX Side

- Insert sync frame every N superframes (configurable, default: 5)
- Replace one voice frame with sync frame
- Maintain superframe counter

#### RX Side

- Scan for sync pattern in decoded frames
- Validate sync frame (pattern + counter)
- Use sync frame to reset frame counter
- Maintain sync state (in-sync vs. searching)

### Performance Impact

**Bandwidth overhead**: ~0.2% (1 sync frame per 500 frames = 1 per 20 seconds)

**Acquisition time**: 
- **With sync frames**: < 1 second (first sync frame)
- **Without sync frames**: 1-5 seconds (LDPC decoder sync)

**Maintenance**: Sync frames help maintain synchronization during fades

## Conclusion

1. **Signing enabled**: Frame 0 provides sufficient sync, no additional sync frames needed
2. **Signing disabled**: Periodic sync frames recommended (every 5-10 superframes)
3. **Hybrid approach**: Use sync frames for initial acquisition, Frame 0 for maintenance when signing enabled

## Implementation Status

**Current**: 
- Frame 0 used as sync marker when signing enabled ✓
- Periodic sync frames implemented for signing-disabled mode ✓

**Implementation**: See [Sync Frame Implementation](SYNC_FRAME_IMPLEMENTATION.md) for details

**Status**: Complete - Sync frames are automatically inserted when signing is disabled

