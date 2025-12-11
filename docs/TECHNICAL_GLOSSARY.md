# Technical Glossary

This document explains technical terms and jargon used throughout the gr-sleipnir documentation and codebase.

## Table of Contents

- [Modulation and Signal Processing](#modulation-and-signal-processing)
- [Error Correction and Coding](#error-correction-and-coding)
- [Performance Metrics](#performance-metrics)
- [Channel Models](#channel-models)
- [Cryptography](#cryptography)
- [Audio Codecs](#audio-codecs)
- [Protocol and Framing](#protocol-and-framing)
- [Hardware and Radio Terms](#hardware-and-radio-terms)
- [Testing and Analysis](#testing-and-analysis)

## Modulation and Signal Processing

### 4FSK (4-level Frequency Shift Keying)
A digital modulation scheme where 4 different frequency levels represent 2 bits per symbol. In gr-sleipnir, 4FSK operates at 4,800 symbols/second, providing 9,600 bps gross data rate. Each symbol represents one of 4 frequencies, allowing 2 bits to be transmitted per symbol.

**Usage**: Standard mode for gr-sleipnir, provides good balance between performance and SNR requirements.

### 8FSK (8-level Frequency Shift Keying)
A digital modulation scheme where 8 different frequency levels represent 3 bits per symbol. In gr-sleipnir, 8FSK operates at 4,800 symbols/second, providing 14,400 bps gross data rate. Each symbol represents one of 8 frequencies, allowing 3 bits to be transmitted per symbol.

**Usage**: High-performance mode for gr-sleipnir, provides better audio quality but requires higher SNR.

### Symbol Rate
The number of symbols transmitted per second. In gr-sleipnir, both 4FSK and 8FSK use 4,800 symbols/second. The symbol rate determines the bandwidth requirement and is independent of the number of levels (4 vs 8).

**Units**: Symbols per second (sps) or baud

### Deviation
The frequency offset from the center frequency for each symbol level. In gr-sleipnir, FSK deviation is 2,400 Hz, meaning each symbol level is offset by ±2,400 Hz from the center frequency.

**Units**: Hertz (Hz)

### Bandwidth
The range of frequencies occupied by the signal. For 4FSK: ~9-10 kHz, for 8FSK: ~11-12 kHz. This includes the signal bandwidth plus guard bands.

**Units**: Hertz (Hz) or kilohertz (kHz)

### SNR (Signal-to-Noise Ratio)
The ratio of signal power to noise power, measured in decibels (dB). Higher SNR means better signal quality and lower error rates. gr-sleipnir achieves operational performance (FER < 5%) at -1 dB SNR for 4FSK and 0-1 dB SNR for 8FSK.

**Units**: Decibels (dB)

### Waterfall SNR
The SNR point where performance transitions from unusable to usable. Traditionally defined as FER < 1%, but for hard-decision decoders, "operational SNR" (FER < 5%) is more appropriate.

**Units**: Decibels (dB)

### Operational SNR
The SNR point where FER drops below a practical threshold (typically 5% for voice communication). This is more realistic than traditional "waterfall" (FER < 1%) for hard-decision decoders.

**Units**: Decibels (dB)

## Error Correction and Coding

### LDPC (Low-Density Parity-Check)
A forward error correction (FEC) code that uses a sparse parity-check matrix. LDPC codes are highly efficient and can approach Shannon limit performance. gr-sleipnir uses:
- Rate 3/4 LDPC for 4FSK (3 data bits for every 4 coded bits)
- Rate 2/3 LDPC for 8FSK (2 data bits for every 3 coded bits)

**Usage**: Corrects errors introduced during transmission, allowing recovery of corrupted data.

### Hard-Decision Decoding
A decoding method where the demodulator outputs only hard bits (0 or 1) without confidence information. The decoder then attempts to correct errors using only these hard decisions. Less efficient than soft-decision decoding but simpler to implement.

**Limitation**: Hard-decision decoders have a performance floor (typically 4-6% FER) that cannot be overcome even at very high SNR.

### Soft-Decision Decoding
A decoding method where the demodulator provides confidence information (log-likelihood ratios, or LLRs) for each bit. The decoder uses this confidence information to make better error correction decisions.

**Advantage**: Can achieve much lower FER (potentially < 1%) but requires more complex implementation.

### FEC (Forward Error Correction)
Error correction codes that add redundancy to data, allowing the receiver to detect and correct errors without retransmission. LDPC is a type of FEC code.

### Code Rate
The ratio of data bits to coded bits. A rate 3/4 code means 3 data bits produce 4 coded bits (25% overhead). Lower rates provide more error correction but reduce effective data rate.

**Examples**: Rate 3/4 = 75% efficiency, Rate 2/3 = 67% efficiency

### Parity Check Matrix
A matrix used by LDPC decoders to verify and correct errors. The matrix defines relationships between bits that must be satisfied for valid codewords.

## Performance Metrics

### FER (Frame Error Rate)
The percentage of frames that fail to decode correctly. Calculated as `frame_errors / total_frames`. Lower FER means better performance.

**Units**: Percentage (%) or fraction (0.0 to 1.0)

**Interpretation**:
- FER < 1%: Excellent quality
- FER 1-5%: Good quality
- FER 5-10%: Acceptable quality
- FER > 10%: Poor quality

### FER Floor
The minimum FER achievable even at very high SNR. For hard-decision LDPC decoders, this is typically 4-6% due to fundamental limitations of hard-decision decoding.

**gr-sleipnir**: 6.45% for 4FSK, 6.92% for 8FSK at SNR ≥ 10 dB

### BER (Bit Error Rate)
The percentage of bits that are incorrect after decoding. Generally lower than FER because a single bit error may not cause a frame error.

**Units**: Percentage (%) or fraction (0.0 to 1.0)

### WarpQ Score
A perceptual audio quality metric that compares decoded audio to reference audio. Scores range from 0 (worst) to 5 (best). Higher scores indicate better audio quality.

**gr-sleipnir**: Mean WarpQ of 4.83 indicates excellent audio quality.

**Interpretation**:
- WarpQ > 4.5: Excellent quality
- WarpQ 4.0-4.5: Good quality
- WarpQ 3.0-4.0: Acceptable quality
- WarpQ < 3.0: Poor quality

### Pass Rate
The percentage of tests that meet all validation criteria (FER threshold, WarpQ threshold, etc.). Used to assess overall system performance.

**gr-sleipnir**: 81.4% overall pass rate (Phase 3 complete)

## Channel Models

### AWGN (Additive White Gaussian Noise)
A channel model that adds random Gaussian noise to the signal. This is the standard model for testing communication systems and represents thermal noise in receivers.

**Usage**: Baseline channel model for performance testing.

### Rayleigh Fading
A channel model that simulates multipath propagation in non-line-of-sight (NLOS) mobile scenarios. The signal amplitude follows a Rayleigh distribution due to multiple signal paths combining.

**Usage**: Tests mobile/portable operation where the signal reflects off multiple objects.

**Penalty**: Typically adds 1-2 dB SNR requirement compared to AWGN.

### Rician Fading
A channel model that simulates multipath propagation with a dominant line-of-sight (LOS) path plus additional reflected paths. The signal amplitude follows a Rician distribution.

**Usage**: Tests mobile/portable operation with a clear direct path plus reflections.

**Penalty**: Typically adds 1-2 dB SNR requirement compared to AWGN, but less severe than Rayleigh.

### Frequency Offset
A channel impairment where the receiver's local oscillator frequency differs from the transmitter's frequency. Common causes include:
- Oscillator drift (temperature, aging)
- Doppler shift (mobile operation)
- Crystal oscillator inaccuracy

**gr-sleipnir tolerance**:
- ±100 Hz: Excellent (FER ~5%, recommended)
- ±500 Hz: Good (FER ~6%, acceptable)
- ±1000 Hz: Marginal (FER ~11%, may cause issues)

### Clean Channel
An ideal channel model with no impairments - perfect synchronization, no noise, no fading. Used as a baseline for comparison.

## Cryptography

### ECDSA (Elliptic Curve Digital Signature Algorithm)
A digital signature algorithm based on elliptic curve cryptography. Used in gr-sleipnir for authentication (signing and verification).

**Usage**: Verifies that messages come from the claimed sender and have not been modified.

**Note**: Signing and verification are NOT encryption - they do not hide message content.

### ChaCha20-Poly1305
A symmetric encryption algorithm combining ChaCha20 stream cipher with Poly1305 message authentication code (MAC). Used in gr-sleipnir for authenticated encryption.

**Usage**: Encrypts message content and provides integrity verification.

**Note**: Encryption DOES hide message content and may be restricted in some jurisdictions.

### MAC (Message Authentication Code)
A cryptographic checksum that verifies message integrity and authenticity. Poly1305 is the MAC used with ChaCha20 in gr-sleipnir.

**Usage**: Detects if encrypted data has been modified or corrupted.

### BrainpoolP256r1
A specific elliptic curve defined by the Brainpool standard. Used in gr-sleipnir for ECDSA signatures. Chosen for its battery-friendly characteristics (efficient computation on low-power devices).

### Key Pair
A pair of cryptographic keys: a private key (kept secret) and a public key (shared). Used for:
- ECDSA: Private key signs, public key verifies
- Encryption: Public key encrypts, private key decrypts (if using public-key encryption)

### Signature Verification
The process of checking that a digital signature is valid. Verifies:
1. The signature was created with the claimed sender's private key
2. The message content matches what was signed
3. The message has not been modified

**Note**: This is NOT encryption - it does not hide message content.

## Audio Codecs

### Opus
A modern, open-source audio codec developed by the IETF and Xiph.org. Provides excellent audio quality at low bitrates. Used in gr-sleipnir for voice encoding.

**gr-sleipnir usage**:
- 4FSK: 6,000 bps Opus
- 8FSK: 8,000 bps Opus

**Advantages**: Superior quality compared to Codec2 and AMBE+2 at similar bitrates.

### Codec2
An open-source, low-bitrate speech codec designed for amateur radio. Used in M17 and FreeDV modes.

**Comparison**: Codec2 typically operates at 0.7-3.2 kbps, providing lower quality than Opus at 6-8 kbps.

### AMBE+2
A proprietary speech codec used in DMR, D-STAR, Fusion, and P25 systems. Typically operates at 2.45 kbps.

**Comparison**: AMBE+2 provides lower quality than Opus at 6-8 kbps, but is widely used in commercial systems.

### Bitrate
The number of bits per second used to encode audio. Higher bitrates generally provide better quality but require more bandwidth.

**gr-sleipnir**: 6,000 bps (4FSK) or 8,000 bps (8FSK)

## Protocol and Framing

### Superframe
A collection of frames that form a complete transmission unit. In gr-sleipnir, a superframe contains:
- 1 authentication frame (Frame 0, optional)
- 24 voice frames (Frames 1-24)

**Duration**: ~1 second of audio (24 frames × 40 ms per frame)

### Frame
A single data unit containing encoded audio, metadata, and error correction. In gr-sleipnir:
- Voice frames: 40 bytes of Opus-encoded audio
- Authentication frame: Signature and metadata

**Duration**: ~40 ms per frame

### Sync Frame
A special frame used for receiver synchronization. Contains a known pattern that helps the receiver lock onto the signal.

**Usage**: Enables the receiver to find the start of frames and maintain timing.

### PDU (Packet Data Unit)
A data structure used in GNU Radio for passing messages between blocks. Contains both data and metadata.

**Usage**: Used internally in gr-sleipnir for frame routing and processing.

### Callsign
An amateur radio identifier assigned to licensed operators. In gr-sleipnir, callsigns are embedded in frames for identification and routing.

**Usage**: Identifies the sender and can be used for recipient filtering.

## Hardware and Radio Terms

### NFM (Narrowband Frequency Modulation)
A modulation mode used in amateur radio where the signal bandwidth is limited (typically 12.5 kHz or 25 kHz channel spacing). gr-sleipnir is designed to fit within NFM channel spacing.

### TCXO (Temperature Compensated Crystal Oscillator)
A high-stability oscillator that maintains frequency accuracy across temperature changes. Recommended for gr-sleipnir to meet ±100 Hz frequency stability requirement.

**Alternative**: Standard crystal oscillators may drift ±500 Hz or more, causing performance degradation.

### PTT (Push-to-Talk)
A control mechanism that activates the transmitter when pressed. In gr-sleipnir, PTT can be controlled via GPIO or ZeroMQ messages.

### GPIO (General Purpose Input/Output)
Hardware pins on a computer (e.g., Raspberry Pi) that can be controlled by software. Used in gr-sleipnir for PTT control.

### ZeroMQ
A messaging library that enables inter-process communication. Used in gr-sleipnir for PTT control and status messaging.

## Testing and Analysis

### Phase 1 Testing
Initial validation testing with a small number of critical test cases (12 tests). Used to verify basic functionality.

**Duration**: ~minutes

### Phase 2 Testing
Comprehensive testing across all major configurations (832 tests). Tests all modulation modes, crypto modes, and channel conditions.

**Duration**: ~hours

### Phase 3 Testing
Complete stress testing including edge cases (7,728 tests). Tests all combinations including text messaging, multi-recipient encryption, and boundary conditions.

**Duration**: ~hours to days

### Test Scenario
A single test configuration defined by:
- Modulation mode (4FSK or 8FSK)
- Crypto mode (none, sign, encrypt, both)
- Channel condition (clean, AWGN, Rayleigh, Rician, frequency offset)
- SNR level
- Data mode (voice or voice_text)
- Recipient scenario (single, two, multi)

### Validation Criteria
The pass/fail criteria for tests, including:
- FER thresholds (channel-specific)
- WarpQ thresholds
- Crypto security validation
- Data integrity checks

### Statistical Significance
A measure of confidence that observed differences are real and not due to random variation. Typically assessed using p-values:
- p < 0.05: Statistically significant (95% confidence)
- p ≥ 0.05: Not statistically significant

### Coefficient of Variation (CV)
A measure of variability relative to the mean. Lower CV indicates more stable/consistent results.

**Formula**: CV = (standard deviation / mean) × 100%

## Additional Terms

### GNU Radio
An open-source software framework for building software-defined radio (SDR) applications. gr-sleipnir is built on GNU Radio.

### OOT (Out-of-Tree) Module
A GNU Radio module that is not part of the core GNU Radio distribution. gr-sleipnir and its dependencies (gr-opus, gr-linux-crypto, etc.) are OOT modules.

### Flowgraph
A GNU Radio program that connects signal processing blocks together. Defines how data flows through the system.

### Hierarchical Block
A GNU Radio block that contains other blocks, creating a reusable sub-flowgraph. `sleipnir_tx_hier` and `sleipnir_rx_hier` are hierarchical blocks.

### PMT (Polymorphic Type)
GNU Radio's data type for passing messages and metadata between blocks. Used for control signals, status messages, and non-stream data.

### Sample Rate
The number of samples per second processed by the system. In gr-sleipnir:
- RF sample rate: 48,000 samples/second
- Audio sample rate: 8,000 samples/second

**Units**: Samples per second (sps) or Hertz (Hz)

### I/Q (In-phase/Quadrature)
A representation of complex signals using two components: in-phase (I) and quadrature (Q). Used in digital signal processing for modulation and demodulation.

### APRS (Automatic Packet Reporting System)
A digital communications protocol used in amateur radio for real-time data exchange (position, weather, messages). gr-sleipnir supports APRS packet transmission.

### Multiplexing
Combining multiple data streams into a single transmission. gr-sleipnir multiplexes voice, text messages, and APRS packets in the same superframe.

---

## Quick Reference

| Term | Meaning | Units/Values |
|------|---------|--------------|
| FER | Frame Error Rate | Percentage (0-100%) |
| SNR | Signal-to-Noise Ratio | Decibels (dB) |
| WarpQ | Audio Quality Score | 0-5 scale |
| 4FSK | 4-level Frequency Shift Keying | Modulation mode |
| 8FSK | 8-level Frequency Shift Keying | Modulation mode |
| LDPC | Low-Density Parity-Check | Error correction code |
| Opus | Audio codec | Codec name |
| ECDSA | Elliptic Curve Digital Signature | Cryptographic algorithm |
| ChaCha20-Poly1305 | Encryption algorithm | Cryptographic algorithm |
| AWGN | Additive White Gaussian Noise | Channel model |
| Rayleigh | Multipath fading model | Channel model |
| Rician | LOS + multipath fading model | Channel model |

---

For more detailed information, see the main [README.md](../README.md) and [Test Results](TEST_RESULTS.md) documentation.

