"""Gait cycle analysis: stance/swing phases, double support and gait sub-phases (Feature 02).

All outputs are ESTIMATES from monocular 2D video. They are not validated against
force plates or instrumented walkways and must be labelled as such.

Method summary
--------------
Event detection (side / sagittal view only)
    Coordinate-based method of Zeni et al. (2008), "Two simple methods for
    determining gait events during treadmill and overground walking using
    kinematic data", Gait & Posture 27(4):710-714:

    * Initial contact (IC) = local maximum of the heel's anterior position
      relative to the pelvis (hip midpoint).
    * Toe-off (TO) = local minimum of the toe's anterior position relative to
      the pelvis.

    The heel / toe fall back to the ankle when the pose model does not track
    them (YOLO COCO-17 has no heel or toe). Fallbacks lower event confidence.
    Visual foot height is NOT used to decide ground contact.

    The anterior direction is the sign of the pelvis' net horizontal
    displacement; for stationary walking (treadmill) the facing direction
    (nose vs. ear midpoint) is used. Front and rear views cannot resolve the
    anterior-posterior axis in 2D, so phase analysis is not performed for them.

Cycle definition
    A gait cycle is one IC to the next IC of the same foot. A cycle is
    complete only if exactly one same-side TO lies between the two ICs.

    stance = TO - IC          swing = IC_next - TO
    stance % = stance / cycle duration * 100 (swing % likewise)

Double support (per cycle of the reference limb)
    initial double support  = IC -> contralateral TO
    terminal double support = contralateral IC -> TO
    Only computed when both contralateral events lie inside the cycle in the
    order IC < oppTO < oppIC < TO, and all four events meet the confidence
    threshold.

Sub-phases (Perry & Burnfield, "Gait Analysis: Normal and Pathological
Function", 2nd ed., 2010) - boundary events:
    loading response   IC            -> contralateral TO
    midstance          contralat. TO -> heel off
    terminal stance    heel off      -> contralateral IC
    pre-swing          contralat. IC -> TO
    initial swing      TO            -> feet adjacent (swing ankle passes stance ankle)
    midswing           feet adjacent -> tibia vertical (swing ankle passes swing knee)
    terminal swing     tibia vertical-> next IC
    Heel off needs a tracked heel distinct from the ankle; without it
    midstance / terminal stance are reported as unavailable, not guessed.

Data quality
    Event confidence = landmark confidence at the event frame
                       x signal-prominence factor x landmark-fallback factor.
    Events below MIN_EVENT_CONFIDENCE are flagged low confidence; cycles that
    contain them are excluded from aggregates. Cycles with implausible duration
    or stance percentage, missing/duplicate TO, or landmark gaps are marked
    incomplete and excluded.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from pydantic import BaseModel, Field
from scipy.signal import find_peaks

from src.gait_events.signal_processing import butter_lowpass_filter
from src.pose_estimation.landmark_schema import FramePose

METHOD_VERSION = "gait_cycle_v1"
METHOD_DESCRIPTION = "Zeni et al. 2008 coordinate-based events from 2D sagittal-view pose (estimated)"

MIN_EVENT_CONFIDENCE = 0.5
MIN_LANDMARK_CONFIDENCE = 0.3
MAX_GAP_S = 0.2  # landmark gaps up to this length are interpolated
CYCLE_DURATION_RANGE_S = (0.6, 2.5)  # plausibility bounds, not normative values
STANCE_PCT_RANGE = (40.0, 80.0)  # plausibility bounds, not normative values
MIN_CYCLES_SUPPORTED = 3
FALLBACK_FACTOR = 0.85
SUPPORTED_VIEWS = ("side", "unknown")
SIDES = ("left", "right")

STANCE_SUBPHASES = ("loading_response", "midstance", "terminal_stance", "pre_swing")
SWING_SUBPHASES = ("initial_swing", "mid_swing", "terminal_swing")
SUBPHASES = ("initial_contact",) + STANCE_SUBPHASES + SWING_SUBPHASES


# --------------------------------------------------------------------------- #
# Schemas                                                                     #
# --------------------------------------------------------------------------- #

class CycleEvent(BaseModel):
    event_type: str  # initial_contact | toe_off
    side: str
    frame_index: int
    timestamp_s: float
    confidence: float
    low_confidence: bool
    landmark: str  # landmark actually used (e.g. "left_heel" or "left_ankle (heel proxy)")


class SubPhase(BaseModel):
    name: str
    start_pct: Optional[float] = None
    end_pct: Optional[float] = None
    duration_s: Optional[float] = None
    available: bool = False
    reason: Optional[str] = None


class GaitCycleRecord(BaseModel):
    cycle_id: str
    side: str
    status: str  # valid | low_confidence | incomplete | implausible
    included_in_aggregate: bool
    reasons: List[str] = Field(default_factory=list)
    start_s: float
    end_s: Optional[float] = None
    duration_s: Optional[float] = None
    toe_off_s: Optional[float] = None
    stance_s: Optional[float] = None
    swing_s: Optional[float] = None
    stance_pct: Optional[float] = None
    swing_pct: Optional[float] = None
    initial_double_support_s: Optional[float] = None
    terminal_double_support_s: Optional[float] = None
    double_support_s: Optional[float] = None
    double_support_pct: Optional[float] = None
    min_event_confidence: Optional[float] = None
    subphases: List[SubPhase] = Field(default_factory=list)


class MetricSummary(BaseModel):
    name: str
    unit: str
    side: Optional[str] = None  # left | right | None (bilateral)
    value: Optional[float] = None
    sd: Optional[float] = None
    n_cycles: int = 0
    status: str = "unavailable"  # estimated | low_confidence | unavailable
    measurement_type: str = "estimated"  # never "validated" for 2D video
    note: Optional[str] = None


class GaitCycleAnalysis(BaseModel):
    method_version: str = METHOD_VERSION
    method: str = METHOD_DESCRIPTION
    status: str  # analysed | insufficient_data | not_supported_view
    camera_view: str
    walking_direction: Optional[str] = None  # left_to_right | right_to_left
    direction_source: Optional[str] = None
    fps: Optional[float] = None
    duration_s: Optional[float] = None
    landmarks_used: Dict[str, str] = Field(default_factory=dict)
    events: List[CycleEvent] = Field(default_factory=list)
    cycles: List[GaitCycleRecord] = Field(default_factory=list)
    phase_metrics: List[MetricSummary] = Field(default_factory=list)
    cadence: Optional[MetricSummary] = None
    subphase_summary: Dict[str, List[SubPhase]] = Field(default_factory=dict)
    counts: Dict[str, int] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    thresholds: Dict[str, float] = Field(default_factory=lambda: {
        "min_event_confidence": MIN_EVENT_CONFIDENCE,
        "min_cycle_duration_s": CYCLE_DURATION_RANGE_S[0],
        "max_cycle_duration_s": CYCLE_DURATION_RANGE_S[1],
        "min_stance_pct": STANCE_PCT_RANGE[0],
        "max_stance_pct": STANCE_PCT_RANGE[1],
        "min_cycles_supported": MIN_CYCLES_SUPPORTED,
    })


# --------------------------------------------------------------------------- #
# Signal helpers                                                              #
# --------------------------------------------------------------------------- #

def _series(poses: Sequence[FramePose], name: str, axis: str = "x") -> Tuple[np.ndarray, np.ndarray]:
    vals, confs = [], []
    for p in poses:
        lm = p.landmarks.get(name)
        if lm is not None and lm.is_visible and lm.confidence >= MIN_LANDMARK_CONFIDENCE:
            vals.append(lm.x_px if axis == "x" else lm.y_px)
            confs.append(lm.confidence)
        else:
            vals.append(np.nan)
            confs.append(0.0)
    return np.asarray(vals, dtype=float), np.asarray(confs, dtype=float)


def _fill_short_gaps(arr: np.ndarray, max_gap: int) -> Tuple[np.ndarray, np.ndarray]:
    """Linearly interpolate gaps of at most ``max_gap`` samples. Returns (filled, valid_mask)."""
    out = arr.copy()
    valid = np.isfinite(arr)
    if valid.sum() < 2:
        return out, valid
    idx = np.arange(arr.size)
    i = 0
    while i < arr.size:
        if not valid[i]:
            j = i
            while j < arr.size and not valid[j]:
                j += 1
            if i > 0 and j < arr.size and (j - i) <= max_gap:
                out[i:j] = np.interp(idx[i:j], [i - 1, j], [arr[i - 1], arr[j]])
            i = j
        else:
            i += 1
    return out, np.isfinite(out)


def _is_proxy(poses: Sequence[FramePose], name: str, base: str) -> bool:
    """True when ``name`` is missing or merely a copy of ``base`` (e.g. YOLO heel = ankle)."""
    seen = same = 0
    for p in poses:
        a, b = p.landmarks.get(name), p.landmarks.get(base)
        if a is None or b is None:
            continue
        seen += 1
        if abs(a.x_px - b.x_px) < 1e-6 and abs(a.y_px - b.y_px) < 1e-6:
            same += 1
    return seen == 0 or same / seen > 0.95


def _smooth(sig: np.ndarray, valid: np.ndarray, fs: float) -> np.ndarray:
    """Low-pass filter contiguous valid runs (6 Hz, zero-phase)."""
    out = np.full_like(sig, np.nan)
    i = 0
    while i < sig.size:
        if valid[i]:
            j = i
            while j < sig.size and valid[j]:
                j += 1
            out[i:j] = butter_lowpass_filter(sig[i:j], cutoff_hz=6.0, fs_hz=fs)
            i = j
        else:
            i += 1
    return out


def _find_extrema(sig: np.ndarray, valid: np.ndarray, fs: float, maxima: bool) -> List[Tuple[int, float]]:
    """Find maxima/minima within valid runs. Returns (index, prominence_quality 0..1)."""
    results: List[Tuple[int, float]] = []
    s = sig if maxima else -sig
    i = 0
    while i < s.size:
        if valid[i]:
            j = i
            while j < s.size and valid[j]:
                j += 1
            seg = s[i:j]
            if seg.size >= int(fs * 0.5):
                rng = float(np.nanmax(seg) - np.nanmin(seg))
                if rng > 1e-6:
                    peaks, props = find_peaks(seg, distance=max(3, int(fs * 0.5)), prominence=0.15 * rng)
                    for k, prom in zip(peaks, props["prominences"]):
                        # Ignore extrema touching the run boundary (cannot confirm a true extremum).
                        if k == 0 or k == seg.size - 1:
                            continue
                        results.append((i + int(k), float(min(1.0, prom / (0.3 * rng)))))
            i = j
        else:
            i += 1
    return results


# --------------------------------------------------------------------------- #
# Direction & events                                                          #
# --------------------------------------------------------------------------- #

def _walking_direction(poses: Sequence[FramePose], pelvis: np.ndarray, pelvis_valid: np.ndarray,
                       leg_len: float) -> Tuple[Optional[int], Optional[str], List[str]]:
    warnings: List[str] = []
    xs = pelvis[pelvis_valid]
    if xs.size >= 2:
        disp = float(xs[-1] - xs[0])
        if abs(disp) > 0.5 * leg_len:
            d = 1 if disp > 0 else -1
            vel = np.diff(xs)
            moving = vel[np.abs(vel) > 1e-3]
            if moving.size and np.mean(np.sign(moving) == d) < 0.7:
                warnings.append("Walking direction changes during the clip; events near turns may be unreliable.")
            return d, "pelvis_displacement", warnings
    # Stationary walking (e.g. treadmill): use facing direction from nose vs. ear midpoint.
    offs = []
    for p in poses:
        lm = p.landmarks
        nose = lm.get("nose")
        ears = [lm.get("left_ear"), lm.get("right_ear")]
        ears = [e for e in ears if e is not None and e.is_visible and e.confidence >= MIN_LANDMARK_CONFIDENCE]
        if nose is not None and nose.is_visible and ears:
            offs.append(nose.x_px - float(np.mean([e.x_px for e in ears])))
    if len(offs) >= 10 and abs(float(np.median(offs))) > 2.0:
        warnings.append("Little forward progression; walking direction inferred from head orientation.")
        return (1 if np.median(offs) > 0 else -1), "facing_direction", warnings
    return None, None, warnings


def detect_cycle_events(
    poses: Sequence[FramePose],
    fps: float,
    direction: int,
    pelvis: np.ndarray,
    landmarks_used: Dict[str, str],
) -> Tuple[List[CycleEvent], Dict[str, np.ndarray]]:
    """Detect IC and TO per side. Returns events and per-side validity masks."""
    max_gap = max(1, int(round(MAX_GAP_S * fps)))
    timestamps = [p.timestamp_s for p in poses]
    frames = [p.frame_index for p in poses]
    events: List[CycleEvent] = []
    valid_masks: Dict[str, np.ndarray] = {}

    for side in SIDES:
        ankle = f"{side}_ankle"
        heel_proxy = _is_proxy(poses, f"{side}_heel", ankle)
        toe_proxy = _is_proxy(poses, f"{side}_foot_index", ankle)
        heel_name = ankle if heel_proxy else f"{side}_heel"
        toe_name = ankle if toe_proxy else f"{side}_foot_index"
        landmarks_used[f"{side}_initial_contact"] = f"{ankle} (heel proxy)" if heel_proxy else heel_name
        landmarks_used[f"{side}_toe_off"] = f"{ankle} (toe proxy)" if toe_proxy else toe_name

        side_valid = np.ones(len(poses), dtype=bool)
        for kind, name, proxy in (("initial_contact", heel_name, heel_proxy), ("toe_off", toe_name, toe_proxy)):
            raw, conf = _series(poses, name)
            filled, valid = _fill_short_gaps(raw, max_gap)
            valid = valid & np.isfinite(pelvis)
            side_valid &= valid
            rel = (filled - pelvis) * direction  # anterior position relative to pelvis
            smooth = _smooth(np.where(valid, rel, 0.0), valid, fps)
            extrema = _find_extrema(smooth, valid, fps, maxima=(kind == "initial_contact"))
            for idx, quality in extrema:
                lm_conf = float(conf[idx]) if conf[idx] > 0 else float(np.nanmean(conf[max(0, idx - 2): idx + 3]) or 0.0)
                c = lm_conf * (0.5 + 0.5 * quality) * (FALLBACK_FACTOR if proxy else 1.0)
                c = round(float(min(1.0, max(0.0, c))), 3)
                events.append(CycleEvent(
                    event_type=kind,
                    side=side,
                    frame_index=frames[idx],
                    timestamp_s=round(float(timestamps[idx]), 4),
                    confidence=c,
                    low_confidence=c < MIN_EVENT_CONFIDENCE,
                    landmark=landmarks_used[f"{side}_{kind}"],
                ))
        valid_masks[side] = side_valid

    events.sort(key=lambda e: (e.timestamp_s, e.side))
    return events, valid_masks


# --------------------------------------------------------------------------- #
# Cycles                                                                      #
# --------------------------------------------------------------------------- #

def _pct(part: float, whole: float) -> float:
    return round(100.0 * part / whole, 2)


def _gap_between(t0: float, t1: float, timestamps: np.ndarray, valid: np.ndarray) -> bool:
    sel = (timestamps >= t0) & (timestamps <= t1)
    return bool(sel.any() and not valid[sel].all())


def _first_crossing(t: np.ndarray, sig: np.ndarray, t0: float, t1: float) -> Optional[float]:
    """First time in (t0, t1) where ``sig`` changes from <= 0 to > 0 (linear interpolation)."""
    sel = np.where((t > t0) & (t < t1) & np.isfinite(sig))[0]
    for a, b in zip(sel[:-1], sel[1:]):
        if b != a + 1:
            continue
        if sig[a] <= 0 < sig[b]:
            frac = -sig[a] / (sig[b] - sig[a])
            return float(t[a] + frac * (t[b] - t[a]))
    return None


def build_cycles(
    events: Sequence[CycleEvent],
    timestamps: np.ndarray,
    valid_masks: Dict[str, np.ndarray],
    kin: Optional[Dict[str, Dict[str, np.ndarray]]] = None,
) -> List[GaitCycleRecord]:
    """Assemble per-side cycles (IC -> next IC) with phase timing, double support and sub-phases.

    ``kin`` (optional) holds per-side anterior positions used for swing sub-phases and heel-off:
    ``{"left": {"ankle": arr, "knee": arr, "heel_y": arr | None, "leg_len": float}, ...}``.
    """
    cycles: List[GaitCycleRecord] = []
    for side in SIDES:
        opp = "right" if side == "left" else "left"
        ics = [e for e in events if e.side == side and e.event_type == "initial_contact"]
        tos = [e for e in events if e.side == side and e.event_type == "toe_off"]
        opp_ics = [e for e in events if e.side == opp and e.event_type == "initial_contact"]
        opp_tos = [e for e in events if e.side == opp and e.event_type == "toe_off"]
        valid = valid_masks.get(side, np.ones_like(timestamps, dtype=bool))

        # Leading partial cycle (video starts mid-cycle): recorded as incomplete.
        if ics and timestamps.size and ics[0].timestamp_s - timestamps[0] > 0.1:
            cycles.append(GaitCycleRecord(
                cycle_id=f"{side}_partial_start", side=side, status="incomplete", included_in_aggregate=False,
                reasons=["Recording starts mid-cycle (no initial contact before this segment)."],
                start_s=round(float(timestamps[0]), 4), end_s=ics[0].timestamp_s,
            ))

        for n, (ic, ic_next) in enumerate(zip(ics[:-1], ics[1:]), start=1):
            t0, t1 = ic.timestamp_s, ic_next.timestamp_s
            dur = t1 - t0
            rec = GaitCycleRecord(
                cycle_id=f"{side}_cycle_{n}", side=side, status="valid", included_in_aggregate=False,
                start_s=t0, end_s=t1, duration_s=round(dur, 4),
            )
            reasons: List[str] = []
            inside = [e for e in tos if t0 < e.timestamp_s < t1]
            if _gap_between(t0, t1, timestamps, valid):
                reasons.append("Landmark tracking gap inside the cycle.")
            if len(inside) == 0:
                reasons.append("No toe-off detected between consecutive initial contacts.")
            elif len(inside) > 1:
                reasons.append("More than one toe-off detected in the cycle.")
            if reasons:
                rec.status, rec.reasons = "incomplete", reasons
                cycles.append(rec)
                continue

            to = inside[0]
            stance, swing = to.timestamp_s - t0, t1 - to.timestamp_s
            rec.toe_off_s = to.timestamp_s
            rec.stance_s, rec.swing_s = round(stance, 4), round(swing, 4)
            rec.stance_pct, rec.swing_pct = _pct(stance, dur), _pct(swing, dur)
            used = [ic, ic_next, to]

            # Double support: IC < oppTO < oppIC < TO, all within the cycle.
            o_to = [e for e in opp_tos if t0 < e.timestamp_s < to.timestamp_s]
            o_ic = [e for e in opp_ics if t0 < e.timestamp_s < to.timestamp_s]
            ds_ok = len(o_to) == 1 and len(o_ic) == 1 and o_to[0].timestamp_s < o_ic[0].timestamp_s
            ds_conf_ok = ds_ok and min(o_to[0].confidence, o_ic[0].confidence) >= MIN_EVENT_CONFIDENCE
            if ds_conf_ok:
                ids = o_to[0].timestamp_s - t0
                tds = to.timestamp_s - o_ic[0].timestamp_s
                rec.initial_double_support_s = round(ids, 4)
                rec.terminal_double_support_s = round(tds, 4)
                rec.double_support_s = round(ids + tds, 4)
                rec.double_support_pct = _pct(ids + tds, dur)

            rec.min_event_confidence = round(min(e.confidence for e in used), 3)
            if not (CYCLE_DURATION_RANGE_S[0] <= dur <= CYCLE_DURATION_RANGE_S[1]):
                rec.status = "implausible"
                rec.reasons.append(f"Cycle duration {dur:.2f} s outside plausible range "
                                   f"{CYCLE_DURATION_RANGE_S[0]}-{CYCLE_DURATION_RANGE_S[1]} s.")
            elif not (STANCE_PCT_RANGE[0] <= rec.stance_pct <= STANCE_PCT_RANGE[1]):
                rec.status = "implausible"
                rec.reasons.append(f"Stance {rec.stance_pct:.0f}% outside plausible range "
                                   f"{STANCE_PCT_RANGE[0]:.0f}-{STANCE_PCT_RANGE[1]:.0f}%.")
            elif rec.min_event_confidence < MIN_EVENT_CONFIDENCE:
                rec.status = "low_confidence"
                rec.reasons.append(f"At least one event below confidence {MIN_EVENT_CONFIDENCE}.")
            if not ds_conf_ok:
                rec.reasons.append("Double support not estimated: contralateral events missing, "
                                   "out of order or low confidence.")
            rec.included_in_aggregate = rec.status == "valid"

            rec.subphases = _subphases(
                rec, ds_conf_ok and o_to[0].timestamp_s, ds_conf_ok and o_ic[0].timestamp_s,
                timestamps, (kin or {}).get(side), (kin or {}).get(opp),
            ) if rec.status == "valid" else []
            cycles.append(rec)

        # Trailing partial cycle (video ends mid-cycle).
        if ics and timestamps.size and timestamps[-1] - ics[-1].timestamp_s > 0.1:
            cycles.append(GaitCycleRecord(
                cycle_id=f"{side}_partial_end", side=side, status="incomplete", included_in_aggregate=False,
                reasons=["Recording ends before the next initial contact."],
                start_s=ics[-1].timestamp_s, end_s=round(float(timestamps[-1]), 4),
            ))

    cycles.sort(key=lambda c: (c.start_s, c.side))
    return cycles


def _subphases(rec: GaitCycleRecord, opp_to, opp_ic, t: np.ndarray, kin, opp_kin) -> List[SubPhase]:
    """Eight sub-phases for one valid cycle. Unavailable boundaries are never guessed."""
    t0, t1, to = rec.start_s, rec.end_s, rec.toe_off_s
    dur = rec.duration_s

    def phase(name, a, b, reason=None):
        if a is None or b is None or a is False or b is False or b < a:
            return SubPhase(name=name, available=False, reason=reason or "Boundary event unavailable.")
        return SubPhase(name=name, start_pct=_pct(a - t0, dur), end_pct=_pct(b - t0, dur),
                        duration_s=round(b - a, 4), available=True)

    no_ds = "Contralateral events unavailable or low confidence."
    heel_off = feet_adj = tibia_vert = None
    heel_reason = "Heel landmark not tracked separately from the ankle; heel rise cannot be detected."
    swing_reason = "Knee/ankle trajectories unavailable for this cycle."
    if kin and opp_kin:
        # Feet adjacent: swing ankle passes the stance (contralateral) ankle.
        feet_adj = _first_crossing(t, kin["ankle"] - opp_kin["ankle"], to, t1)
        # Tibia vertical: swing ankle passes its own knee.
        if feet_adj is not None:
            tibia_vert = _first_crossing(t, kin["ankle"] - kin["knee"], feet_adj, t1)
        if kin.get("heel_y") is not None and opp_to:
            heel_y = kin["heel_y"]
            stance_sel = (t >= t0) & (t <= opp_to) & np.isfinite(heel_y)
            if stance_sel.any():
                ground = float(np.nanmax(heel_y[stance_sel]))  # image y grows downward
                thr = 0.03 * kin["leg_len"]
                win = np.where((t > opp_to) & (t < to) & np.isfinite(heel_y))[0]
                rise = [i for i in win if ground - heel_y[i] > thr]
                heel_off = float(t[rise[0]]) if rise else None
                heel_reason = None if heel_off is not None else "No heel rise detected before toe-off."

    return [
        SubPhase(name="initial_contact", start_pct=0.0, end_pct=0.0, duration_s=0.0, available=True),
        phase("loading_response", t0, opp_to, no_ds),
        phase("midstance", opp_to, heel_off, heel_reason if opp_to else no_ds),
        phase("terminal_stance", heel_off, opp_ic, heel_reason if opp_ic else no_ds),
        phase("pre_swing", opp_ic, to, no_ds),
        phase("initial_swing", to, feet_adj, swing_reason if not kin else "Feet-adjacent instant not found."),
        phase("mid_swing", feet_adj, tibia_vert, swing_reason if not kin else "Tibia-vertical instant not found."),
        phase("terminal_swing", tibia_vert, t1, swing_reason if not kin else "Tibia-vertical instant not found."),
    ]


# --------------------------------------------------------------------------- #
# Aggregation                                                                 #
# --------------------------------------------------------------------------- #

def _summary(name: str, unit: str, values: List[float], side: Optional[str], note: Optional[str] = None) -> MetricSummary:
    n = len(values)
    if n == 0:
        return MetricSummary(name=name, unit=unit, side=side, status="unavailable",
                             note=note or "No valid cycles available.")
    return MetricSummary(
        name=name, unit=unit, side=side, n_cycles=n,
        value=round(float(np.mean(values)), 3),
        sd=round(float(np.std(values, ddof=1)), 3) if n > 1 else None,
        status="estimated" if n >= MIN_CYCLES_SUPPORTED else "low_confidence",
        note=note if n >= MIN_CYCLES_SUPPORTED else f"Based on only {n} valid cycle(s); interpret with caution.",
    )


def symmetry_index(left: Optional[float], right: Optional[float]) -> Optional[float]:
    """Robinson et al. (1987) symmetry index: |L - R| / (0.5 (L + R)) x 100. 0 = perfect symmetry."""
    if left is None or right is None or (left + right) == 0:
        return None
    return round(abs(left - right) / (0.5 * (left + right)) * 100.0, 2)


def aggregate(cycles: Sequence[GaitCycleRecord], events: Sequence[CycleEvent]) -> Tuple[List[MetricSummary], Optional[MetricSummary], Dict[str, List[SubPhase]]]:
    valid = [c for c in cycles if c.included_in_aggregate]
    metrics: List[MetricSummary] = []
    per_side: Dict[str, Dict[str, MetricSummary]] = {}
    for side in SIDES:
        sc = [c for c in valid if c.side == side]
        per_side[side] = {
            "stance_time": _summary("stance_time", "s", [c.stance_s for c in sc], side),
            "swing_time": _summary("swing_time", "s", [c.swing_s for c in sc], side),
            "stance_pct": _summary("stance_pct", "% cycle", [c.stance_pct for c in sc], side),
            "swing_pct": _summary("swing_pct", "% cycle", [c.swing_pct for c in sc], side),
        }
        metrics.extend(per_side[side].values())

    metrics.append(_summary("gait_cycle_duration", "s", [c.duration_s for c in valid], None))
    ds = [c for c in valid if c.double_support_s is not None]
    ds_note = None if ds else "Not estimated: contralateral events insufficient or low confidence."
    metrics.append(_summary("double_support_time", "s", [c.double_support_s for c in ds], None, ds_note))
    metrics.append(_summary("double_support_pct", "% cycle", [c.double_support_pct for c in ds], None, ds_note))

    for key, unit in (("stance_time", "%"), ("swing_time", "%"), ("stance_pct", "%")):
        l, r = per_side["left"][key], per_side["right"][key]
        si = symmetry_index(l.value, r.value)
        status = "unavailable" if si is None else (
            "estimated" if min(l.n_cycles, r.n_cycles) >= MIN_CYCLES_SUPPORTED else "low_confidence")
        metrics.append(MetricSummary(
            name=f"{key}_asymmetry", unit=f"{unit} (symmetry index)", value=si,
            n_cycles=min(l.n_cycles, r.n_cycles), status=status,
            note="Symmetry index |L-R| / mean(L,R) x 100; 0 = symmetric." if si is not None
            else "Requires valid cycles on both sides.",
        ))

    # Cadence is reported separately from phase metrics: steps/min from consecutive
    # initial contacts of alternating feet, using only confident events.
    ics = sorted([e for e in events if e.event_type == "initial_contact" and not e.low_confidence],
                 key=lambda e: e.timestamp_s)
    steps = [b.timestamp_s - a.timestamp_s for a, b in zip(ics[:-1], ics[1:])
             if a.side != b.side and 0.25 <= b.timestamp_s - a.timestamp_s <= 1.25]
    cadence = _summary("cadence", "steps/min", [60.0 / s for s in steps], None,
                       "Step-based: 60 / time between alternating initial contacts.")
    if steps:
        cadence.n_cycles = len(steps)
        cadence.note = f"Step-based from {len(steps)} steps: 60 / time between alternating initial contacts."

    sub_summary: Dict[str, List[SubPhase]] = {}
    for side in SIDES:
        sc = [c for c in valid if c.side == side]
        rows: List[SubPhase] = []
        for name in SUBPHASES:
            got = [p for c in sc for p in c.subphases if p.name == name and p.available]
            if got:
                rows.append(SubPhase(
                    name=name, available=True,
                    start_pct=round(float(np.mean([p.start_pct for p in got])), 2),
                    end_pct=round(float(np.mean([p.end_pct for p in got])), 2),
                    duration_s=round(float(np.mean([p.duration_s for p in got])), 4),
                    reason=f"Mean of {len(got)} cycle(s).",
                ))
            else:
                reasons = [p.reason for c in sc for p in c.subphases if p.name == name and p.reason]
                rows.append(SubPhase(name=name, available=False,
                                     reason=reasons[0] if reasons else "No valid cycles."))
        sub_summary[side] = rows
    return metrics, cadence, sub_summary


# --------------------------------------------------------------------------- #
# Entry point                                                                 #
# --------------------------------------------------------------------------- #

def analyze_gait_cycles(poses: Sequence[FramePose], camera_view: str = "side", fps: Optional[float] = None) -> GaitCycleAnalysis:
    """Run gait-cycle analysis on a pose sequence. Never raises for poor data; reports status instead."""
    view = camera_view or "unknown"
    if view not in SUPPORTED_VIEWS:
        return GaitCycleAnalysis(
            status="not_supported_view", camera_view=view,
            warnings=[f"Stance/swing phases require a side (sagittal) view; the {view} view cannot resolve "
                      "forward-backward foot motion in 2D. Record a side view for gait-cycle analysis."],
        )
    if len(poses) < 2:
        return GaitCycleAnalysis(status="insufficient_data", camera_view=view, warnings=["Too few frames."])

    t = np.asarray([p.timestamp_s for p in poses], dtype=float)
    dt = np.diff(t)
    est_fps = float(1.0 / np.median(dt)) if dt.size and np.median(dt) > 0 else (fps or 30.0)
    fs = fps or est_fps
    result = GaitCycleAnalysis(status="analysed", camera_view=view, fps=round(fs, 2),
                               duration_s=round(float(t[-1] - t[0]), 3))
    if t[-1] - t[0] < 1.5:
        result.status = "insufficient_data"
        result.warnings.append("Recording shorter than 1.5 s; at least one full gait cycle per side is needed.")
        return result

    max_gap = max(1, int(round(MAX_GAP_S * fs)))
    lh, _ = _series(poses, "left_hip")
    rh, _ = _series(poses, "right_hip")
    pelvis_raw = np.where(np.isfinite(lh) & np.isfinite(rh), (lh + rh) / 2.0, np.where(np.isfinite(lh), lh, rh))
    pelvis, pelvis_valid = _fill_short_gaps(pelvis_raw, max_gap)

    leg = []
    for p in poses:
        for s in SIDES:
            h, a = p.landmarks.get(f"{s}_hip"), p.landmarks.get(f"{s}_ankle")
            if h and a and h.is_visible and a.is_visible:
                leg.append(float(np.hypot(h.x_px - a.x_px, h.y_px - a.y_px)))
    leg_len = float(np.median(leg)) if leg else 0.0
    if pelvis_valid.sum() < 0.6 * len(poses) or leg_len <= 0:
        result.status = "insufficient_data"
        result.warnings.append("Hip/ankle landmarks not tracked reliably enough for gait-cycle analysis.")
        return result

    direction, source, dir_warnings = _walking_direction(poses, pelvis, pelvis_valid, leg_len)
    result.warnings.extend(dir_warnings)
    if direction is None:
        result.status = "insufficient_data"
        result.warnings.append("Walking direction could not be determined (no forward progression or head orientation).")
        return result
    result.walking_direction = "left_to_right" if direction > 0 else "right_to_left"
    result.direction_source = source

    events, valid_masks = detect_cycle_events(poses, fs, direction, np.where(pelvis_valid, pelvis, np.nan),
                                              result.landmarks_used)

    kin: Dict[str, Dict[str, np.ndarray]] = {}
    for s in SIDES:
        ank, _ = _series(poses, f"{s}_ankle")
        kne, _ = _series(poses, f"{s}_knee")
        ank, _ = _fill_short_gaps(ank, max_gap)
        kne, _ = _fill_short_gaps(kne, max_gap)
        heel_y = None
        if not _is_proxy(poses, f"{s}_heel", f"{s}_ankle"):
            hy, _ = _series(poses, f"{s}_heel", axis="y")
            heel_y, _ = _fill_short_gaps(hy, max_gap)
        kin[s] = {"ankle": (ank - pelvis) * direction, "knee": (kne - pelvis) * direction,
                  "heel_y": heel_y, "leg_len": leg_len}

    cycles = build_cycles(events, t, valid_masks, kin)
    metrics, cadence, sub_summary = aggregate(cycles, events)

    result.events = events
    result.cycles = cycles
    result.phase_metrics = metrics
    result.cadence = cadence
    result.subphase_summary = sub_summary
    result.counts = {
        "events": len(events),
        "low_confidence_events": sum(e.low_confidence for e in events),
        "cycles_total": len([c for c in cycles if not c.cycle_id.endswith(("partial_start", "partial_end"))]),
        "cycles_valid": sum(c.included_in_aggregate for c in cycles),
        "cycles_low_confidence": sum(c.status == "low_confidence" for c in cycles),
        "cycles_incomplete": sum(c.status == "incomplete" for c in cycles),
        "cycles_implausible": sum(c.status == "implausible" for c in cycles),
    }
    if any("proxy" in v for v in result.landmarks_used.values()):
        result.warnings.append("Heel/toe not tracked by the pose model; ankle used as proxy. "
                               "Event timing is less precise and confidence is reduced.")
    if result.counts["cycles_valid"] == 0:
        result.status = "insufficient_data"
        result.warnings.append("No valid gait cycles; aggregate phase metrics are unavailable.")
    return result
