# gr-opus Test Suite

This directory contains unit tests and integration tests for the gr-opus module.

## Test Files

- `qa_opus_encoder.py` - Unit tests for the Opus encoder block
- `qa_opus_decoder.py` - Unit tests for the Opus decoder block
- `qa_opus_roundtrip.py` - Integration tests for encoder-decoder round-trip

## Running Tests

### Using CMake/CTest

After building the module:

```bash
cd build
ctest
```

Or run individual tests:

```bash
ctest -R qa_opus_encoder
ctest -R qa_opus_decoder
ctest -R qa_opus_roundtrip
```

### Using Python unittest directly

```bash
cd tests
python3 -m unittest qa_opus_encoder
python3 -m unittest qa_opus_decoder
python3 -m unittest qa_opus_roundtrip
```

Or run all tests:

```bash
python3 -m unittest discover -p 'qa_*.py'
```

## Test Coverage

### Encoder Tests (`qa_opus_encoder.py`)

- Initialization with default and custom parameters
- Different application types (voip, audio, lowdelay)
- Different sample rates (8kHz, 12kHz, 16kHz, 24kHz, 48kHz)
- Mono and stereo configurations
- Single and multiple frame encoding
- Partial frame buffering
- Edge cases (silence, clipping, empty input)

### Decoder Tests (`qa_opus_decoder.py`)

- Initialization with default and custom parameters
- Different sample rates
- Mono and stereo configurations
- Fixed and variable packet size modes
- Partial packet buffering
- Multiple packet decoding
- Invalid packet handling
- Output range validation

### Round-trip Tests (`qa_opus_roundtrip.py`)

- Sine wave encoding/decoding
- Multiple frames
- Stereo signals
- Different sample rates
- Different bitrates
- Different application types
- Silence handling
- White noise

## Requirements

Tests require:
- Python 3.6+
- numpy
- opuslib
- GNU Radio 3.8+

## Notes

- Tests use the opuslib library directly to generate test encoded packets
- Some tests may produce warnings or skip tests if dependencies are missing
- Round-trip tests verify that encoding and decoding preserve signal characteristics

