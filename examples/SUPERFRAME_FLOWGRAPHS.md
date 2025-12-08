# Superframe Flowgraph Modifications

This document describes the flowgraph modifications needed for superframe transmission.

## Overview

The superframe system uses separate flowgraphs for:
1. **Authentication Frame (Frame 0)**: 256 bits -> 768 bits coded (rate 1/3)
2. **Voice Frames (Frames 1-24)**: 384 bits -> 576 bits coded (rate 2/3)

## Voice Frame Flowgraph: tx_4fsk_opus_voice.grc

### Modifications from tx_4fsk_opus.grc

1. **Replace WAV source with file source**:
   - Remove: `blocks_wavfile_source_0`
   - Remove: `low_pass_filter_0`
   - Remove: `gr_opus_opus_encoder_0`
   - Add: `blocks_file_source_0` (reads 48-byte payload file, type: byte)

2. **Update LDPC matrix**:
   - Change `ldpc_matrix_file` to: `"../ldpc_matrices/ldpc_voice_576_384.alist"`
   - Update `ldpc_encoder_def` file path accordingly
   - Note: Rate is 2/3 (384 bits info -> 576 bits coded)

3. **Payload size**:
   - Input: 48 bytes (384 bits) payload file
   - After LDPC: 72 bytes (576 bits coded)
   - After 4FSK: 288 symbols (576 bits / 2 bits per symbol)

### Flowgraph Structure

```
File Source (48 bytes) 
  -> LDPC Encoder (384->576 bits, rate 2/3)
  -> Packed to Unpacked (2 bits per chunk)
  -> Chunks to Symbols (4FSK mapping)
  -> Root Raised Cosine Filter
  -> Frequency Modulator
  -> File Sink (IQ output)
```

## Authentication Frame Flowgraph: tx_auth_frame.grc

### New Flowgraph

1. **File source**:
   - Reads 32-byte payload file (256 bits signature)
   - Type: byte

2. **LDPC matrix**:
   - Use: `"../ldpc_matrices/ldpc_auth_768_256.alist"`
   - Rate: 1/3 (256 bits info -> 768 bits coded)

3. **Payload size**:
   - Input: 32 bytes (256 bits) payload file
   - After LDPC: 96 bytes (768 bits coded)
   - After 4FSK: 384 symbols (768 bits / 2 bits per symbol)

### Flowgraph Structure

```
File Source (32 bytes)
  -> LDPC Encoder (256->768 bits, rate 1/3)
  -> Packed to Unpacked (2 bits per chunk)
  -> Chunks to Symbols (4FSK mapping)
  -> Root Raised Cosine Filter
  -> Frequency Modulator
  -> File Sink (IQ output)
```

## Common Parameters

Both flowgraphs share:
- **RF Sample Rate**: 48000 Hz
- **Symbol Rate**: 4800 symbols/second
- **FSK Deviation**: 2400 Hz
- **4FSK Symbol Mapping**: [-3, -1, 1, 3]
- **Root Raised Cosine**: alpha=0.35, 110 taps

## Usage from Python

The superframe controller writes payload files and executes flowgraphs:

```python
# Voice frame
payload_file = "frame_1_payload.bin"  # 48 bytes
subprocess.run(["grcc", "-o", "output_dir", "tx_4fsk_opus_voice.grc"])
# Modify generated script to use payload_file
subprocess.run(["python3", "tx_4fsk_opus_voice.py"])

# Auth frame
payload_file = "frame_0_payload.bin"  # 32 bytes
subprocess.run(["grcc", "-o", "output_dir", "tx_auth_frame.grc"])
# Modify generated script to use payload_file
subprocess.run(["python3", "tx_auth_frame.py"])
```

## Implementation Notes

1. **File Source Configuration**:
   - Set `repeat: False` to read exactly one frame
   - Use `type: byte` for binary payload files

2. **LDPC Encoder**:
   - Use `fec_extended_encoder` block
   - Configure with appropriate matrix file
   - No puncturing needed (use `puncpat: "11"`)

3. **Timing**:
   - Voice frame: 576 bits / 4800 bps = 120 ms (but we transmit in 40ms chunks)
   - Auth frame: 768 bits / 4800 bps = 160 ms
   - Note: Actual transmission time depends on symbol rate and filtering

4. **Output Concatenation**:
   - The superframe controller concatenates frame outputs
   - Each frame produces a separate IQ file
   - Final superframe is assembled from 25 frame files


