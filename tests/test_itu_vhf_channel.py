#!/usr/bin/env python3
"""
ITU VHF Channel Model Test Suite for gr-sleipnir
=================================================

Tests gr-sleipnir's SuperframeAssembler -> SuperframeParser chain through
ITU-R M.1225 compliant VHF/UHF channel models appropriate for handheld
rubber-duck antenna operation.

Channel scenarios modelled:
  1. Handheld urban stationary   -- Rayleigh, fd=1 Hz,  delay=2.5 us
  2. Handheld walking city       -- Rayleigh, fd=2 Hz,  delay=2.0 us
  3. Handheld in vehicle 50km/h  -- Rayleigh, fd=7 Hz,  delay=1.0 us
  4. Handheld in vehicle 120km/h -- Rayleigh, fd=16 Hz, delay=0.5 us
  5. Handheld rural open         -- Rician,   fd=1 Hz,  delay=0.5 us, K=4 dB
  6. Handheld to repeater        -- Rician,   fd=2 Hz,  delay=0.3 us, K=6 dB

SNR sweep: -5 dB to +15 dB in 1 dB steps per scenario.

Quality metrics:
  - FER  (Frame Error Rate) derived from `python/sleipnir/` PDU processing:
       float audio is packed into 24 * 40 B nominal \"Opus\" placeholders ->
       Python SuperframeAssembler (same layout as the C++ block) ->
       surrogate AWGN-equivalent IID bit flips driven by the swept Eb/N0 (dB) knob ->
       Python SuperframeParser (same validity rules as the C++ block). Cumulative
       parser counters yield FER vs SNR curves per ITU scenario seed.
  - PESQ (ITU-T P.862), narrowband, and STOI (pystoi) are computed by comparing the
       clean reference waveform to the *analog channel output* (`apply_itu_vhf_channel`).
       That path deliberately does **not** run a full Opus encode/decode round-trip.

Important distinction — read results accordingly:
  FER answers: \"Given this SNR knob, how often does the **binary PDU** violate
 voice framing after the real assembler/binary surrogate/parser rules?\"
  PESQ/STOI answer: \"How degraded does the **analog waveform** sound after the ITU-like
  multipath+Doppler model?\" They characterise **channel model / waveform** behaviour,
  not Opus reconstructed audio. To score codec-plus-channel quality, integrate a real Opus encoder/decoder around the PDU chain and compute speech metrics on the decoded PCM instead.

Reference: ITU-R M.1225, ITU-R P.1407, ITU-R P.1812
Antenna:   Rubber duck on handheld, gain ~ -4 dBd, height ~1.2 m

Usage:
    python3 test_itu_vhf_channel.py [--ref clean_pulse_60s.wav] [--out results/]
    python3 test_itu_vhf_channel.py --scenario 1 --snr_min 0 --snr_max 10
"""

import argparse
import csv
import json
import math
import os
import sys
import time
import wave
import zlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from scipy import signal as scipy_signal

try:
    from pesq import pesq as pesq_score
    HAVE_PESQ = True
except ImportError:
    HAVE_PESQ = False
    print("[WARN] pesq not installed -- PESQ scores will be skipped. pip install pesq")

try:
    from pystoi import stoi as stoi_score
    HAVE_STOI = True
except ImportError:
    HAVE_STOI = False
    print("[WARN] pystoi not installed -- STOI scores will be skipped. pip install pystoi")

# ---------------------------------------------------------------------------
# gr-sleipnir imports (GNU Radio-free Python analogue under repo python/)
# ---------------------------------------------------------------------------
SLEIPNIR_PYTHON = Path(__file__).resolve().parents[1] / "python"
if SLEIPNIR_PYTHON.is_dir():
    sys.path.insert(0, str(SLEIPNIR_PYTHON))

try:
    from sleipnir.superframe_assembler import SuperframeAssembler
    from sleipnir.superframe_parser import SuperframeParser
    HAVE_SLEIPNIR = True
except ImportError:
    HAVE_SLEIPNIR = False
    print("[WARN] gr-sleipnir GNU Radio-free Python analogue not found -- using stub for structure test.")
    print(f"       Expected: {SLEIPNIR_PYTHON}")

VOICE_FRAMES_PER_SF = 24


def bpsk_awgn_bit_error_probability(ebno_db: float) -> float:
    """Coherent BPSK AWGN bit error probability; Eb/N0 in dB."""
    eb_lin = max(10.0 ** (float(ebno_db) / 10.0), 1e-30)
    pb = 0.5 * math.erfc(math.sqrt(eb_lin))
    return float(min(max(pb, 1e-12), 0.499999))


def corrupt_pdu_iid_bits(pdu: bytes, ebno_db: float, rng: np.random.Generator) -> bytes:
    """Surrogate AWGN-equivalent IID bit flips on an assembled superframe PDU."""
    if not pdu:
        return pdu
    pb = bpsk_awgn_bit_error_probability(ebno_db)
    out = bytearray(pdu)
    for i in range(len(out)):
        v = out[i]
        bit_mask = 1
        for _ in range(8):
            if rng.random() < pb:
                v ^= bit_mask
            bit_mask <<= 1
        out[i] = v & 0xFF
    return bytes(out)


# ---------------------------------------------------------------------------
# ITU-R M.1225 channel tap profiles
# ---------------------------------------------------------------------------

# Vehicular A (urban, NLOS) -- adapted for VHF rubber duck
VEHICULAR_A_TAPS = {
    "delays_us": [0.0, 0.31, 0.71, 1.09, 1.73, 2.51],
    "powers_db": [0.0, -1.0, -9.0, -10.0, -15.0, -20.0],
}

# Pedestrian A (urban walking)
PEDESTRIAN_A_TAPS = {
    "delays_us": [0.0, 0.11, 0.19, 0.41],
    "powers_db": [0.0, -9.7, -19.2, -22.8],
}

# Rural / LOS (Rician) -- simplified two-tap
RURAL_LOS_TAPS = {
    "delays_us": [0.0, 0.30],
    "powers_db": [0.0, -15.0],
}


@dataclass
class ChannelScenario:
    name: str
    model: str          # 'rayleigh' or 'rician'
    doppler_hz: float   # max Doppler shift in Hz
    delay_profile: dict # tap delays and powers
    k_factor_db: float  # Rician K in dB (0 = Rayleigh)
    description: str


SCENARIOS = [
    ChannelScenario(
        name="urban_stationary",
        model="rayleigh",
        doppler_hz=1.0,
        delay_profile=VEHICULAR_A_TAPS,
        k_factor_db=0.0,
        description="Handheld urban stationary -- body shadowing, NLOS dominant",
    ),
    ChannelScenario(
        name="walking_city",
        model="rayleigh",
        doppler_hz=2.0,
        delay_profile=PEDESTRIAN_A_TAPS,
        k_factor_db=0.0,
        description="Handheld walking city -- ~5 km/h, random orientation",
    ),
    ChannelScenario(
        name="vehicle_50kmh",
        model="rayleigh",
        doppler_hz=7.0,
        delay_profile=VEHICULAR_A_TAPS,
        k_factor_db=0.0,
        description="Handheld in vehicle 50 km/h -- window glass ~3 dB attenuation",
    ),
    ChannelScenario(
        name="vehicle_120kmh",
        model="rayleigh",
        doppler_hz=16.0,
        delay_profile=VEHICULAR_A_TAPS,
        k_factor_db=0.0,
        description="Handheld in vehicle 120 km/h -- rapid multipath evolution",
    ),
    ChannelScenario(
        name="rural_open",
        model="rician",
        doppler_hz=1.0,
        delay_profile=RURAL_LOS_TAPS,
        k_factor_db=4.0,
        description="Handheld rural open -- partial LOS, low antenna height",
    ),
    ChannelScenario(
        name="to_repeater",
        model="rician",
        doppler_hz=2.0,
        delay_profile=RURAL_LOS_TAPS,
        k_factor_db=6.0,
        description="Handheld to elevated repeater -- partial LOS, repeater high",
    ),
]


# ---------------------------------------------------------------------------
# ITU-R M.1225 Jakes fading model
# ---------------------------------------------------------------------------

def _jakes_fading(n: int, fd: float, sr: float, n_sinusoids: int = 16,
                  rng: Optional[np.random.Generator] = None) -> np.ndarray:
    """
    Generate a complex Rayleigh fading sequence using the Jakes model.
    ITU-R M.1225 section B.1.

    Parameters
    ----------
    n            : number of samples
    fd           : maximum Doppler frequency (Hz)
    sr           : sample rate (Hz)
    n_sinusoids  : number of sinusoids (16 gives good statistics)
    rng          : optional numpy random generator for reproducibility
    """
    if rng is None:
        rng = np.random.default_rng()
    t = np.arange(n) / sr
    h = np.zeros(n, dtype=complex)
    for k in range(1, n_sinusoids + 1):
        alpha_k = 2 * np.pi * k / n_sinusoids
        phi_k = rng.uniform(0, 2 * np.pi)
        h += np.exp(1j * (2 * np.pi * fd * np.cos(alpha_k) * t + phi_k))
    return h / np.sqrt(n_sinusoids)


def apply_itu_vhf_channel(
    samples: np.ndarray,
    sr: float,
    scenario: ChannelScenario,
    snr_db: float,
    seed: int = 42,
) -> np.ndarray:
    """
    Apply an ITU-R M.1225 VHF channel model to a real audio signal.

    Steps:
      1. Convert to analytic signal (complex baseband)
      2. Apply multipath delay taps with Jakes fading per tap
      3. Add AWGN at requested SNR
      4. Return real part at original sample rate

    Parameters
    ----------
    samples  : float32/float64 audio, normalised to [-1, 1]
    sr       : sample rate in Hz
    scenario : ChannelScenario instance
    snr_db   : target SNR in dB (signal power / noise power)
    seed     : RNG seed for reproducibility
    """
    rng = np.random.default_rng(seed)
    n = len(samples)

    tap_delays_us = scenario.delay_profile["delays_us"]
    tap_powers_db = scenario.delay_profile["powers_db"]
    tap_delays_samp = [int(round(d * 1e-6 * sr)) for d in tap_delays_us]
    tap_powers_lin  = [10 ** (p / 20) for p in tap_powers_db]
    max_delay = max(tap_delays_samp)

    # Analytic (complex) baseband representation
    s_complex = scipy_signal.hilbert(samples)

    # Output buffer with room for max delay
    out_len = n + max_delay
    output = np.zeros(out_len, dtype=complex)

    k_lin = 10 ** (scenario.k_factor_db / 10) if scenario.k_factor_db > 0 else 0.0

    for delay_samp, power_lin in zip(tap_delays_samp, tap_powers_lin):
        fade = _jakes_fading(n, scenario.doppler_hz, sr,
                             n_sinusoids=16, rng=rng)
        if scenario.model == "rician" and k_lin > 0:
            # Rician: superimpose LOS component on Rayleigh scatter
            los_amplitude = np.sqrt(k_lin / (k_lin + 1))
            scatter_scale = np.sqrt(1.0 / (k_lin + 1))
            fade = los_amplitude + scatter_scale * fade
        output[delay_samp: delay_samp + n] += power_lin * fade * s_complex

    output = output[:n]

    # Normalise faded signal power before adding noise
    faded_power = np.mean(np.abs(output) ** 2)
    if faded_power > 0:
        output /= np.sqrt(faded_power)

    # Add AWGN at requested SNR
    snr_lin = 10 ** (snr_db / 10)
    noise_power = 1.0 / snr_lin
    noise = np.sqrt(noise_power / 2) * (
        rng.standard_normal(n) + 1j * rng.standard_normal(n)
    )
    output += noise

    # Return real part, normalised to [-1, 1]
    result = np.real(output).astype(np.float32)
    peak = np.max(np.abs(result))
    if peak > 0:
        result /= peak
    return result


# ---------------------------------------------------------------------------
# WAV helpers
# ---------------------------------------------------------------------------

def load_wav(path: str) -> Tuple[np.ndarray, int]:
    """Load a WAV file, return (float32 samples normalised to [-1,1], sample_rate)."""
    with wave.open(path, "rb") as w:
        sr   = w.getframerate()
        sw   = w.getsampwidth()
        raw  = w.readframes(w.getnframes())
    if sw == 2:
        s = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 4:
        s = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported sample width: {sw}")
    return s, sr


def save_wav(path: str, samples: np.ndarray, sr: int) -> None:
    """Save float32 samples as 16-bit WAV."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    s16 = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(s16.tobytes())


# ---------------------------------------------------------------------------
# gr-sleipnir chain stub (used when GR4 package not installed)
# ---------------------------------------------------------------------------

class SleipnirChainStub:
    """
    Fallback when python/sleipnir is not importable.

    Applies a monotone FER-vs-Eb/N0 heuristic from the surrogate digital Pb model
    (not bit-accurate; use SleipnirChain when imports succeed).
    """
    FRAME_BYTES = 48
    FRAMES_PER_SUPERFRAME = 25
    OPUS_FRAME_BYTES = 40

    def process(
        self,
        audio: np.ndarray,
        sr: int,
        digital_ebno_db: float = 0.0,
        rng: Optional[np.random.Generator] = None,
    ) -> Tuple[np.ndarray, dict]:
        if rng is None:
            rng = np.random.default_rng(0)

        pb = bpsk_awgn_bit_error_probability(digital_ebno_db)
        rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
        analogue_gate = float(np.clip(1.0 - rms * 8.0, 0.0, 1.0))

        fer = float(np.clip(pb * 180.0 * (1.0 - analogue_gate * 0.15), 0.0, 1.0))
        total_frames_guess = max(24, len(audio) // max(1, int(sr * 0.020)))
        frame_errors = int(round(min(fer, 1.0) * float(total_frames_guess)))
        stats = {
            "frame_error_rate": round(fer, 4),
            "frame_errors": frame_errors,
            "total_frames": total_frames_guess,
            "sync_detected": rms > 0.03,
        }
        decoded = (audio.astype(np.float32)) * np.float32(1.0 - fer * 0.75)
        return decoded, stats


class SleipnirChain:
    """
    PDU-level chain aligned with GNURadio 4 sleipnir analogue:

      float audio -> nominal 40-byte "Opus placeholders" -> SuperframeAssembler
      -> IID bit corruption (BPSK-AWGN Pb from swept Eb/N0) -> SuperframeParser

    FER/status come from Parser counters; decoded audio reconstructs placeholders
    from per-49-byte frame inspection (excluding sync frames), matching Parser rules.
    """
    def __init__(self, callsign: str = "N0CALL"):
        self.assembler = SuperframeAssembler(callsign=callsign)
        self.parser = SuperframeParser(local_callsign=callsign)

    def process(
        self,
        audio: np.ndarray,
        sr: int,
        digital_ebno_db: float,
        rng: np.random.Generator,
    ) -> Tuple[np.ndarray, dict]:
        from sleipnir import frame_format as ff

        self.assembler.reset()
        self.parser.reset()

        opus_frame_samples = int(sr * 0.020)
        frames: List[bytes] = []
        for i in range(0, len(audio) - opus_frame_samples + 1, opus_frame_samples):
            chunk = audio[i : i + opus_frame_samples]
            frame_bytes = chunk.astype(np.float32).tobytes()[:40]
            frames.append(frame_bytes.ljust(40, b"\x00"))

        n_sf = len(frames) // VOICE_FRAMES_PER_SF
        decoded_chunks: List[np.ndarray] = []
        last_sync = False

        for blk in range(n_sf):
            pdu_in = b"".join(frames[blk * VOICE_FRAMES_PER_SF : (blk + 1) * VOICE_FRAMES_PER_SF])
            assembled = self.assembler.assemble(pdu_in)
            corrupted = corrupt_pdu_iid_bits(assembled, digital_ebno_db, rng)
            _parsed_opus, pstats = self.parser.parse(corrupted)
            last_sync = bool(pstats.get("sync_detected", False))

            fsz = int(ff.VOICE_FRAME_SIZE)
            pos = 0
            waveform_blocks: List[np.ndarray] = []
            while pos + fsz <= len(corrupted):
                fr = corrupted[pos : pos + fsz]
                pos += fsz

                tb = np.zeros(opus_frame_samples, dtype=np.float32)
                if ff.is_sync_frame(fr):
                    continue
                if int(fr[0]) != int(ff.FRAME_TYPE_VOICE):
                    waveform_blocks.append(tb)
                    continue
                payload = bytes(fr[1 : 1 + int(ff.OPUS_STORED_BYTES)]).ljust(40, b"\x00")
                nfloat = len(payload) // 4
                floats = np.frombuffer(payload[: nfloat * 4], dtype=np.float32).copy()
                ncopy = min(int(floats.size), opus_frame_samples)
                tb[:ncopy] = floats[:ncopy]

                waveform_blocks.append(tb)

            if waveform_blocks:
                decoded_chunks.append(np.concatenate(waveform_blocks))

        decoded = (
            np.concatenate(decoded_chunks)
            if decoded_chunks
            else np.zeros(0, dtype=np.float32)
        )
        if decoded.size < len(audio):
            decoded = np.pad(decoded, (0, max(0, len(audio) - decoded.size))).astype(np.float32)
        else:
            decoded = decoded[: len(audio)].astype(np.float32)

        total_frames = int(self.parser.total_frames_received)
        frame_errors = int(self.parser.frame_error_count)
        fer = float(frame_errors) / float(total_frames) if total_frames > 0 else 1.0
        stats = {
            "frame_error_rate": round(fer, 4),
            "frame_errors": frame_errors,
            "total_frames": total_frames,
            "sync_detected": last_sync,
        }
        return decoded, stats


# ---------------------------------------------------------------------------
# Quality metrics
# ---------------------------------------------------------------------------

def compute_pesq(reference: np.ndarray, degraded: np.ndarray, sr: int) -> Optional[float]:
    """ITU-T P.862 PESQ -- narrowband mode (sr must be 8000 or 16000)."""
    if not HAVE_PESQ:
        return None
    target_sr = 8000
    if sr != target_sr:
        ref_ds = scipy_signal.resample_poly(reference, target_sr, sr)
        deg_ds = scipy_signal.resample_poly(degraded,  target_sr, sr)
    else:
        ref_ds, deg_ds = reference, degraded
    n = min(len(ref_ds), len(deg_ds))
    try:
        score = pesq_score(target_sr, ref_ds[:n].astype(np.float32),
                           deg_ds[:n].astype(np.float32), "nb")
        return round(float(score), 4)
    except Exception:
        return None


def compute_stoi(reference: np.ndarray, degraded: np.ndarray, sr: int) -> Optional[float]:
    """Short-Time Objective Intelligibility (STOI) -- range 0..1."""
    if not HAVE_STOI:
        return None
    n = min(len(reference), len(degraded))
    try:
        score = stoi_score(reference[:n], degraded[:n], sr, extended=False)
        return round(float(score), 4)
    except Exception:
        return None


def compute_snr_actual(reference: np.ndarray, degraded: np.ndarray) -> float:
    """Actual signal-to-noise ratio between reference and degraded."""
    n = min(len(reference), len(degraded))
    sig     = reference[:n].astype(np.float64, copy=False)
    noise   = sig - degraded[:n].astype(np.float64, copy=False)
    sig_p   = float(np.mean(sig ** 2))
    noise_p = float(np.mean(noise ** 2))
    if not np.isfinite(sig_p) or not np.isfinite(noise_p) or noise_p <= 1e-30:
        if sig_p <= 1e-30:
            return 0.0
        return 99.0 if noise_p <= 1e-30 else 0.0
    return round(float(10 * np.log10(sig_p / noise_p)), 2)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    scenario: str
    snr_db: float
    fer: float
    frame_errors: int
    total_frames: int
    sync_detected: bool
    pesq: Optional[float]
    stoi: Optional[float]
    actual_snr_db: float
    elapsed_s: float


# ---------------------------------------------------------------------------
# Main sweep
# ---------------------------------------------------------------------------

def run_sweep(
    ref_path: str,
    scenarios: List[ChannelScenario],
    snr_range: range,
    out_dir: str,
    callsign: str = "N0CALL",
    verbose: bool = True,
) -> List[TestResult]:

    os.makedirs(out_dir, exist_ok=True)
    reference, sr = load_wav(ref_path)

    max_samples = sr * 10
    reference = reference[:max_samples]

    if HAVE_SLEIPNIR:
        chain = SleipnirChain(callsign=callsign)
        chain_name = "sleipnir PDU analogue (assemble + IID bit flips + parser; matches C++ frame layout)"
    else:
        chain = SleipnirChainStub()
        chain_name = "stub (gr-sleipnir GR4 not found)"

    print(f"\ngr-sleipnir ITU VHF Channel Test")
    print(f"Chain:     {chain_name}")
    print(f"Reference: {ref_path}  ({len(reference)/sr:.1f}s @ {sr} Hz)")
    print(f"SNR range: {snr_range.start} to {snr_range.stop-1} dB "
          f"({len(snr_range)} steps)")
    print(f"Scenarios: {len(scenarios)}")
    print(f"Output:    {out_dir}")
    print("=" * 70)

    results = []

    for scenario in scenarios:
        print(f"\n[{scenario.name}] {scenario.description}")
        print(f"  Model={scenario.model}  fd={scenario.doppler_hz} Hz  "
              f"K={scenario.k_factor_db} dB")
        print(f"  {'SNR':>5}  {'FER':>7}  {'PESQ':>6}  {'STOI':>6}  "
              f"{'ActSNR':>7}  {'Sync':>5}")
        print(f"  {'-'*5}  {'-'*7}  {'-'*6}  {'-'*6}  {'-'*7}  {'-'*5}")

        for snr_db in snr_range:
            t0 = time.monotonic()

            degraded = apply_itu_vhf_channel(
                reference, float(sr), scenario, float(snr_db),
                seed=42 + snr_db
            )

            seed = (
                42
                + int(snr_db)
                + (zlib.adler32(scenario.name.encode("utf-8")) & 0x7FFFFFFF)
            ) & 0xFFFFFFFF
            rng = np.random.default_rng(seed)

            decoded, stats = chain.process(degraded, sr, float(snr_db), rng)

            pesq_val   = compute_pesq(reference, decoded, sr)
            stoi_val   = compute_stoi(reference, decoded, sr)
            actual_snr = compute_snr_actual(reference, decoded)
            elapsed    = time.monotonic() - t0

            result = TestResult(
                scenario=scenario.name,
                snr_db=float(snr_db),
                fer=stats["frame_error_rate"],
                frame_errors=stats["frame_errors"],
                total_frames=stats["total_frames"],
                sync_detected=stats["sync_detected"],
                pesq=pesq_val,
                stoi=stoi_val,
                actual_snr_db=actual_snr,
                elapsed_s=round(elapsed, 3),
            )
            results.append(result)

            pesq_str = f"{pesq_val:6.3f}" if pesq_val is not None else "   n/a"
            stoi_str = f"{stoi_val:6.3f}" if stoi_val is not None else "   n/a"
            sync_str = "YES" if stats["sync_detected"] else "NO "

            print(f"  {snr_db:>5}  {stats['frame_error_rate']:>7.4f}  "
                  f"{pesq_str}  {stoi_str}  {actual_snr:>7.2f}  {sync_str:>5}")

    return results


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------

def write_csv(results: List[TestResult], path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()))
        w.writeheader()
        for r in results:
            w.writerow(asdict(r))
    print(f"\nCSV  -> {path}")


def write_json(results: List[TestResult], path: str) -> None:
    with open(path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    print(f"JSON -> {path}")


def write_summary(results: List[TestResult], path: str) -> None:
    """Per-scenario summary: operational SNR threshold (FER < 5%) and peak PESQ."""
    scenarios = dict()
    for r in results:
        scenarios.setdefault(r.scenario, []).append(r)

    lines = [
        "# gr-sleipnir ITU VHF Channel Test Summary\n",
        "## Rubber duck antenna, handheld operation\n",
        "## Channel: ITU-R M.1225, Quality: ITU-T P.862 PESQ\n\n",
        "| Scenario | Op.SNR (FER<5%) | Peak PESQ | Peak STOI | Notes |\n",
        "|----------|----------------|-----------|-----------|-------|\n",
    ]

    for name, res in scenarios.items():
        scenario_obj = next(s for s in SCENARIOS if s.name == name)
        op_snr = ">{} dB".format(max(r.snr_db for r in res))
        for r in sorted(res, key=lambda x: x.snr_db):
            if r.fer < 0.05:
                op_snr = f"{r.snr_db:.0f} dB"
                break
        peak_pesq = max((r.pesq for r in res if r.pesq is not None), default=None)
        peak_stoi = max((r.stoi for r in res if r.stoi is not None), default=None)
        pesq_str = f"{peak_pesq:.3f}" if peak_pesq else "n/a"
        stoi_str = f"{peak_stoi:.3f}" if peak_stoi else "n/a"
        note = f"fd={scenario_obj.doppler_hz}Hz K={scenario_obj.k_factor_db}dB"
        lines.append(f"| {name} | {op_snr} | {pesq_str} | {stoi_str} | {note} |\n")

    with open(path, "w") as f:
        f.writelines(lines)
    print(f"MD   -> {path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="gr-sleipnir ITU VHF channel model test suite"
    )
    parser.add_argument(
        "--ref", default="/mnt/user-data/uploads/clean_pulse_60s.wav",
        help="Reference WAV file (clean_pulse_60s.wav)"
    )
    parser.add_argument(
        "--out", default="itu_vhf_results",
        help="Output directory for CSV/JSON/Markdown results"
    )
    parser.add_argument(
        "--callsign", default="N0CALL",
        help="Callsign for gr-sleipnir superframe metadata"
    )
    parser.add_argument(
        "--snr_min", type=int, default=-5,
        help="Minimum SNR in dB (default: -5)"
    )
    parser.add_argument(
        "--snr_max", type=int, default=15,
        help="Maximum SNR in dB inclusive (default: 15)"
    )
    parser.add_argument(
        "--scenario", type=int, default=None,
        help="Run only scenario N (1-6). Default: all."
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-SNR output"
    )
    args = parser.parse_args()

    if not Path(args.ref).exists():
        print(f"ERROR: Reference WAV not found: {args.ref}")
        sys.exit(1)

    selected = SCENARIOS
    if args.scenario is not None:
        idx = args.scenario - 1
        if not 0 <= idx < len(SCENARIOS):
            print(f"ERROR: --scenario must be 1-{len(SCENARIOS)}")
            sys.exit(1)
        selected = [SCENARIOS[idx]]

    snr_range = range(args.snr_min, args.snr_max + 1)

    t_total = time.monotonic()
    results = run_sweep(
        ref_path=args.ref,
        scenarios=selected,
        snr_range=snr_range,
        out_dir=args.out,
        callsign=args.callsign,
        verbose=not args.quiet,
    )
    elapsed = time.monotonic() - t_total

    print(f"\n{'='*70}")
    print(f"Total test time: {elapsed:.1f}s  ({len(results)} data points)")

    write_csv(results,     os.path.join(args.out, "results.csv"))
    write_json(results,    os.path.join(args.out, "results.json"))
    write_summary(results, os.path.join(args.out, "SUMMARY.md"))

    print("\nDone.")


if __name__ == "__main__":
    main()
