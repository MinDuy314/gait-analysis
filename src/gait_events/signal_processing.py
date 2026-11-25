"""Signal processing utilities for landmark trajectories and kinematics."""

from typing import Optional, Tuple
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks


def butter_lowpass_filter(
    data: np.ndarray,
    cutoff_hz: float = 6.0,
    fs_hz: float = 30.0,
    order: int = 4,
) -> np.ndarray:
    """Zero-phase lowpass Butterworth filter for motion trajectories."""
    arr = np.asarray(data, dtype=np.float64)
    if arr.size <= order * 3 or not np.all(np.isfinite(arr)):
        return arr

    nyq = 0.5 * fs_hz
    normal_cutoff = min(cutoff_hz / nyq, 0.99)
    b, a = butter(order, normal_cutoff, btype="low", analog=False)
    return filtfilt(b, a, arr)


def detect_extrema_events(
    signal: np.ndarray,
    min_distance_frames: int = 10,
    prominence_factor: float = 0.1,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Find local peaks (maxima) and valleys (minima) in a 1D trajectory signal.
    Returns (peak_indices, valley_indices).
    """
    valid_sig = np.asarray(signal, dtype=np.float64)
    if valid_sig.size < min_distance_frames * 2 or not np.all(np.isfinite(valid_sig)):
        return np.array([], dtype=int), np.array([], dtype=int)

    sig_range = float(np.max(valid_sig) - np.min(valid_sig))
    prominence = max(1e-3, sig_range * prominence_factor)

    peaks, _ = find_peaks(valid_sig, distance=min_distance_frames, prominence=prominence)
    valleys, _ = find_peaks(-valid_sig, distance=min_distance_frames, prominence=prominence)
    return peaks, valleys
