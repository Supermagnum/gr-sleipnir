# Refactor to 8-Carrier QPSK System

## Overview

Refactoring gr-sleipnir from FSK to 8 parallel QPSK carriers:
- 8 QPSK carriers, 900 baud per carrier
- 2 bits per symbol (QPSK)
- ~1,000-1,200 Hz bandwidth per carrier (with pulse shaping)
- Use only installed GNU Radio modules (remove optional dependencies)

## Architecture Changes

### Current System (FSK)
```
Audio → Opus → Superframe → LDPC → Bits → FSK Symbol Mapping → Pulse Shaping → Frequency Modulator → RF
```

### New System (8-Carrier QPSK)
```
Audio → Opus → Superframe → LDPC → Bits → Split into 8 streams → 
  [8x: QPSK Modulator → Pulse Shaping → Frequency Shift] → Sum → RF
```

## Parameters

### Per Carrier
- Symbol rate: 900 baud
- Bits per symbol: 2 (QPSK)
- Bit rate: 1,800 bits/sec per carrier
- Bandwidth: ~1,000-1,200 Hz (with α=0.35 roll-off)

### Total System
- Total carriers: 8
- Total bit rate: 14,400 bits/sec (8 × 1,800)
- Carrier spacing: ~1,300 Hz (to avoid overlap)

### Pulse Shaping
- Filter: Root Raised Cosine (RRC)
- Roll-off factor (α): 0.35
- Samples per symbol: 4-8 (to be determined)
- Bandwidth calculation: BW = symbol_rate × (1 + α)

## Module Dependencies

### Required (Standard GNU Radio)
- `gnuradio.gr` - Core blocks
- `gnuradio.blocks` - Basic blocks
- `gnuradio.filter` - Filters (RRC)
- `gnuradio.digital` - QPSK modulation/demodulation, symbol sync
- `gnuradio.analog` - Frequency shifting, AGC

### Optional (Make Optional)
- `gnuradio.gr_opus` - Opus audio encoding/decoding
- `gnuradio.fec` - LDPC forward error correction
- `gnuradio.pdu` - PDU conversion
- `gnuradio.channels` - Channel models

## Implementation Status

The 8-carrier QPSK system has been fully implemented:

1. Single-carrier QPSK TX/RX chains: Completed
2. QPSK symbol to LLR converter: Completed
3. 8-carrier frequency shifting and combining: Completed
4. TX chain updated: QPSK modulation with 8-carrier multiplexing
5. RX chain updated: Single-carrier QPSK demodulation
6. Function signatures updated: Added num_carriers, carrier_spacing parameters

## Implementation Plan (Remaining)

1. Update configuration files
2. Test and validate

## QPSK Implementation

### TX Chain (Single Carrier)
```
Bits → packed_to_unpacked (2 bits) → chunks_to_symbols_bf (QPSK constellation) → 
RRC Interpolator → Frequency Shift → Complex Output
```

### RX Chain (Single Carrier)
```
Complex Input → Frequency Shift (to baseband) → RRC Matched Filter → 
Costas Loop → Symbol Sync → Constellation Decoder → Bits
```

### Multi-Carrier
- Split bit stream into 8 parallel streams
- Each stream goes through QPSK chain
- Frequency shift each by carrier offset
- Sum all carriers
- On RX: Bandpass filter each carrier, process in parallel

## Constellation

QPSK constellation (2 bits → complex symbol):
- 00 → (1+1j)/√2 = 0.707+0.707j
- 01 → (-1+1j)/√2 = -0.707+0.707j
- 10 → (1-1j)/√2 = 0.707-0.707j
- 11 → (-1-1j)/√2 = -0.707-0.707j

Or normalized:
- 00 → 1+1j
- 01 → -1+1j
- 10 → 1-1j
- 11 → -1-1j

