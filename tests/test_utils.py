#!/usr/bin/env python3
"""
Utility functions for gr-sleipnir test suite.

Provides helper functions for WAV file operations, key generation,
metrics computation, and file management.
"""

import wave
import numpy as np
import os
import json
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import subprocess
import hashlib


def detect_wav_properties(wav_file: str) -> Dict[str, Any]:
    """
    Detect WAV file properties using Python wave library.
    
    Args:
        wav_file: Path to WAV file
        
    Returns:
        Dictionary with properties: sample_rate, channels, sample_width, duration
    """
    try:
        with wave.open(wav_file, 'rb') as wf:
            props = {
                'sample_rate': wf.getframerate(),
                'channels': wf.getnchannels(),
                'sample_width': wf.getsampwidth(),
                'frames': wf.getnframes(),
                'duration': wf.getnframes() / wf.getframerate()
            }
        return props
    except Exception as e:
        logging.error(f"Error detecting WAV properties: {e}")
        return {}


def read_wav_file(wav_file: str) -> Tuple[np.ndarray, int]:
    """
    Read WAV file and return audio data and sample rate.
    
    Args:
        wav_file: Path to WAV file
        
    Returns:
        Tuple of (audio_data, sample_rate)
    """
    try:
        with wave.open(wav_file, 'rb') as wf:
            sample_rate = wf.getframerate()
            n_channels = wf.getnchannels()
            n_frames = wf.getnframes()
            sample_width = wf.getsampwidth()
            
            # Read audio data
            audio_bytes = wf.readframes(n_frames)
            
            # Convert to numpy array
            if sample_width == 1:
                dtype = np.uint8
            elif sample_width == 2:
                dtype = np.int16
            elif sample_width == 4:
                dtype = np.int32
            else:
                raise ValueError(f"Unsupported sample width: {sample_width}")
            
            audio_data = np.frombuffer(audio_bytes, dtype=dtype)
            
            # Convert to float32 in range [-1.0, 1.0]
            if dtype == np.uint8:
                audio_data = (audio_data.astype(np.float32) - 128.0) / 128.0
            elif dtype == np.int16:
                audio_data = audio_data.astype(np.float32) / 32768.0
            elif dtype == np.int32:
                audio_data = audio_data.astype(np.float32) / 2147483648.0
            
            # Handle multi-channel
            if n_channels > 1:
                audio_data = audio_data.reshape(-1, n_channels)
                # Convert to mono by averaging channels
                audio_data = np.mean(audio_data, axis=1)
            
            return audio_data, sample_rate
    except Exception as e:
        logging.error(f"Error reading WAV file {wav_file}: {e}")
        raise


def write_wav_file(wav_file: str, audio_data: np.ndarray, sample_rate: int):
    """
    Write audio data to WAV file.
    
    Args:
        wav_file: Output WAV file path
        audio_data: Audio samples (float32, range [-1.0, 1.0])
        sample_rate: Sample rate in Hz
    """
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(wav_file) if os.path.dirname(wav_file) else '.', exist_ok=True)
        
        # Convert float32 to int16
        audio_int16 = (audio_data * 32767.0).astype(np.int16)
        
        # Write WAV file
        with wave.open(wav_file, 'wb') as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int16.tobytes())
    except Exception as e:
        logging.error(f"Error writing WAV file {wav_file}: {e}")
        raise


def compute_warpq(reference_wav: str, degraded_wav: str) -> Optional[float]:
    """
    Compute WarpQ score for audio quality assessment.
    
    Args:
        reference_wav: Reference WAV file path
        degraded_wav: Degraded WAV file path
        
    Returns:
        WarpQ score (higher is better) or None if computation fails
    """
    # Try to use warp-q command-line tool if available
    try:
        result = subprocess.run(
            ['warp-q', reference_wav, degraded_wav],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Parse output (format may vary)
            try:
                score = float(result.stdout.strip().split()[-1])
                return score
            except:
                pass
    except FileNotFoundError:
        # warp-q tool not found - will use fallback
        pass
    except Exception as e:
        logging.warning(f"warp-q tool error: {e}, using fallback PSNR computation")
    
    # Fallback: compute basic SNR/PSNR
    try:
        ref_audio, ref_sr = read_wav_file(reference_wav)
        deg_audio, deg_sr = read_wav_file(degraded_wav)
        
        # Resample if needed to match reference sample rate
        if ref_sr != deg_sr:
            logging.info(f"Resampling degraded audio from {deg_sr} Hz to {ref_sr} Hz")
            try:
                # Try using scipy.signal.resample if available
                from scipy import signal
                # Calculate number of samples needed
                num_samples = int(len(deg_audio) * ref_sr / deg_sr)
                deg_audio = signal.resample(deg_audio, num_samples)
            except ImportError:
                # Fallback: simple linear interpolation
                logging.warning("scipy not available, using simple resampling")
                # Create time arrays
                ref_time = np.arange(len(ref_audio)) / ref_sr
                deg_time = np.arange(len(deg_audio)) / deg_sr
                
                # Interpolate degraded audio to reference time points
                # Limit to the overlapping time range
                max_time = min(ref_time[-1], deg_time[-1])
                ref_time_limited = ref_time[ref_time <= max_time]
                deg_audio = np.interp(ref_time_limited, deg_time, deg_audio)
                ref_audio = ref_audio[:len(deg_audio)]
        
        # Align lengths
        min_len = min(len(ref_audio), len(deg_audio))
        if min_len == 0:
            logging.warning("Empty audio files")
            return None
        
        ref_audio = ref_audio[:min_len]
        deg_audio = deg_audio[:min_len]
        
        # Compute MSE
        mse = np.mean((ref_audio - deg_audio) ** 2)
        
        if mse == 0:
            return 5.0  # Perfect match
        
        # Compute PSNR (Power Signal-to-Noise Ratio)
        max_val = 1.0
        psnr_db = 20 * np.log10(max_val / np.sqrt(mse))
        
        # Convert PSNR to approximate WarpQ scale (rough mapping)
        # WarpQ typically ranges from 0-5, with 3+ being good quality
        # PSNR 20 dB -> WarpQ ~1.0, PSNR 40 dB -> WarpQ ~3.0, PSNR 60 dB -> WarpQ ~5.0
        warpq_approx = min(5.0, max(0.0, (psnr_db - 10) / 10))
        
        return warpq_approx
    except Exception as e:
        logging.error(f"Error computing WarpQ fallback: {e}")
        import traceback
        logging.debug(traceback.format_exc())
        return None


def generate_test_keys(key_dir: str, callsigns: list = None):
    """
    Generate test keys for crypto testing.
    
    Args:
        key_dir: Directory to store keys
        callsigns: List of callsigns to generate keys for
    """
    if callsigns is None:
        callsigns = ["TEST1", "TEST2", "N0CALL"]
    
    os.makedirs(key_dir, exist_ok=True)
    
    # Generate MAC keys (ChaCha20-Poly1305 uses 32-byte keys)
    for callsign in callsigns:
        # Generate deterministic test key from callsign
        key_bytes = hashlib.sha256(callsign.encode()).digest()
        key_file = os.path.join(key_dir, f"{callsign}_mac.key")
        with open(key_file, 'wb') as f:
            f.write(key_bytes)
        logging.info(f"Generated MAC key for {callsign}: {key_file}")
    
    # Note: ECDSA key generation requires cryptography library
    # For now, we'll use pre-generated keys or skip if not available
    logging.info(f"Test keys generated in {key_dir}")


def setup_logging(log_file: str = None, level: str = "INFO", console: bool = True):
    """
    Setup logging configuration.
    
    Args:
        log_file: Log file path (optional)
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        console: Enable console output
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    handlers = []
    
    if console:
        handlers.append(logging.StreamHandler())
    
    if log_file:
        os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else '.', exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


def save_results(results: Dict[str, Any], output_file: str):
    """
    Save test results to JSON file.
    
    Args:
        results: Results dictionary
        output_file: Output JSON file path
    """
    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)


def load_results(input_file: str) -> Dict[str, Any]:
    """
    Load test results from JSON file.
    
    Args:
        input_file: Input JSON file path
        
    Returns:
        Results dictionary
    """
    with open(input_file, 'r') as f:
        return json.load(f)


def ensure_directory(path: str):
    """
    Ensure directory exists, create if needed.
    
    Args:
        path: Directory path
    """
    os.makedirs(path, exist_ok=True)


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "1h 23m 45s")
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    
    return " ".join(parts)

