"""Reference tests for Feature 02: gait-cycle analysis.

Synthetic walkers are generated with KNOWN event times so detected events, phase
durations, percentages, double support and sub-phase boundaries can be checked
against exact reference values (tolerance: frame quantisation at 30 fps).
"""
import math
import uuid

import numpy as np
import pytest

from src.gait_events.gait_cycle_analysis import (
    MIN_EVENT_CONFIDENCE,
    CycleEvent,
    analyze_gait_cycles,
    build_cycles,
    symmetry_index,
)
from src.pose_estimation.landmark_schema import FramePose, Landmark

FPS = 30.0
T = 1.1  # stride (gait cycle) duration, s
A = 120.0  # anterior-posterior foot excursion amplitude, px
B = 40.0  # knee-ankle offset amplitude, px
GROUND_Y = 600.0
HIP_Y = 200.0
FRAME_TOL_S = 1.5 / FPS


def _lm(name, x, y, conf):
    return Landmark(name=name, x_px=float(x), y_px=float(y), x_norm=float(x) / 1280, y_norm=float(y) / 720,
                    confidence=conf, is_visible=True)


def make_walker(
    duration=6.0,
    stance_frac=(0.6, 0.6),
    direction=1,
    speed=150.0,
    conf=0.9,
    heel_tracked=True,
    toe_tracked=True,
    heel_off_frac=0.30,
    tibia_vertical_frac=0.87,
    gap=None,  # (side, t_start, t_end) -> landmarks of that leg missing
    first_ic=(0.2, 0.2 + T / 2),
    planted_ankle=False,
):
    """Synthetic side-view walker. IC at heel max anterior, TO at toe max posterior (relative to pelvis)."""
    poses = []
    n = int(duration * FPS)
    for i in range(n):
        t = i / FPS
        pelvis_x = 300 + direction * speed * t
        lms = {
            "left_hip": _lm("left_hip", pelvis_x - 5, HIP_Y, conf),
            "right_hip": _lm("right_hip", pelvis_x + 5, HIP_Y, conf),
            "nose": _lm("nose", pelvis_x + direction * 25, 80, conf),
            "left_ear": _lm("left_ear", pelvis_x, 75, conf),
            "right_ear": _lm("right_ear", pelvis_x, 75, conf),
        }
        for side, s_frac, t_ic in (("left", stance_frac[0], first_ic[0]), ("right", stance_frac[1], first_ic[1])):
            if gap and gap[0] == side and gap[1] <= t <= gap[2]:
                continue
            phi = 2 * math.pi * (t - t_ic) / T
            f = ((t - t_ic) / T) % 1.0
            heel_rel = A * math.cos(phi)
            toe_rel = -A * math.cos(phi - 2 * math.pi * s_frac)
            ankle_rel = heel_rel
            if planted_ankle:
                # Realistic ankle: planted during stance (moves back linearly relative to the
                # advancing pelvis from +A at IC to -A at TO), then swings forward to +A.
                if f < s_frac:
                    ankle_rel = A - 2 * A * f / s_frac
                else:
                    ankle_rel = -A * math.cos(math.pi * (f - s_frac) / (1 - s_frac))
            knee_rel = ankle_rel - B * math.sin(2 * math.pi * (t - t_ic - tibia_vertical_frac * T) / T)
            # Heel height: on the ground until heel off, lifted through swing, back down before IC.
            if f < heel_off_frac:
                lift = 0.0
            elif f < s_frac:
                lift = (f - heel_off_frac) / (s_frac - heel_off_frac)
            elif f < 0.97:
                lift = 1.0 - (f - s_frac) / (0.97 - s_frac)
            else:
                lift = 0.0
            heel_y = GROUND_Y - 200.0 * lift
            ax = pelvis_x + direction * ankle_rel
            lms[f"{side}_knee"] = _lm(f"{side}_knee", pelvis_x + direction * knee_rel, 400, conf)
            lms[f"{side}_ankle"] = _lm(f"{side}_ankle", ax, heel_y - 30, conf)
            if heel_tracked:
                lms[f"{side}_heel"] = _lm(f"{side}_heel", pelvis_x + direction * heel_rel, heel_y, conf)
            else:  # YOLO-style: heel is a copy of the ankle
                lms[f"{side}_heel"] = _lm(f"{side}_heel", ax, heel_y - 30, conf * 0.9)
            if toe_tracked:
                lms[f"{side}_foot_index"] = _lm(f"{side}_foot_index", pelvis_x + direction * toe_rel, GROUND_Y, conf)
        poses.append(FramePose(frame_index=i, timestamp_s=t, model_name="synthetic", model_version="test",
                               device="cpu", image_width=1280, image_height=720, landmarks=lms))
    return poses


def _metric(res, name, side=None):
    return next(m for m in res.phase_metrics if m.name == name and m.side == side)


def _sub(res, side, name):
    return next(p for p in res.subphase_summary[side] if p.name == name)


# --------------------------------------------------------------------------- #
# Reference walker: symmetric, stance 60 %                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def reference():
    return analyze_gait_cycles(make_walker(), camera_view="side", fps=FPS)


def test_reference_events_have_timestamps_and_match_ground_truth(reference):
    assert reference.status == "analysed"
    assert reference.walking_direction == "left_to_right"
    ics = [e for e in reference.events if e.side == "left" and e.event_type == "initial_contact"]
    tos = [e for e in reference.events if e.side == "left" and e.event_type == "toe_off"]
    assert len(ics) >= 4 and len(tos) >= 4
    for e in reference.events:
        assert e.timestamp_s is not None and e.frame_index >= 0
        assert 0.0 <= e.confidence <= 1.0
    # True left IC times: 0.2 + k*T ; true TO: IC + 0.6*T
    for e in ics:
        k = round((e.timestamp_s - 0.2) / T)
        assert abs(e.timestamp_s - (0.2 + k * T)) <= FRAME_TOL_S
    for e in tos:
        k = round((e.timestamp_s - 0.2 - 0.6 * T) / T)
        assert abs(e.timestamp_s - (0.2 + 0.6 * T + k * T)) <= FRAME_TOL_S


def test_reference_stance_swing_both_legs(reference):
    for side in ("left", "right"):
        st, sw = _metric(reference, "stance_time", side), _metric(reference, "swing_time", side)
        sp, wp = _metric(reference, "stance_pct", side), _metric(reference, "swing_pct", side)
        assert st.status == "estimated" and st.n_cycles >= 3
        assert st.value == pytest.approx(0.6 * T, abs=FRAME_TOL_S)
        assert sw.value == pytest.approx(0.4 * T, abs=FRAME_TOL_S)
        assert sp.value == pytest.approx(60.0, abs=3.0)
        assert wp.value == pytest.approx(40.0, abs=3.0)
        assert sp.value + wp.value == pytest.approx(100.0, abs=0.01)
        assert st.measurement_type == "estimated"
    assert _metric(reference, "gait_cycle_duration").value == pytest.approx(T, abs=0.02)


def test_reference_double_support_and_cadence(reference):
    # Right IC at +T/2, right TO at +0.1T => each double support 10 %, total 20 %.
    ds = _metric(reference, "double_support_pct")
    assert ds.value == pytest.approx(20.0, abs=4.0)
    assert _metric(reference, "double_support_time").value == pytest.approx(0.2 * T, abs=2 * FRAME_TOL_S)
    assert reference.cadence.value == pytest.approx(120.0 / T, abs=3.0)
    assert reference.cadence.name == "cadence"
    assert all(m.name != "cadence" for m in reference.phase_metrics)  # cadence kept separate


def test_reference_symmetry(reference):
    assert _metric(reference, "stance_pct_asymmetry").value == pytest.approx(0.0, abs=5.0)


def test_reference_eight_subphases(reference):
    expected = {  # (start %, end %) from the synthetic construction
        "loading_response": (0, 10), "midstance": (10, 31), "terminal_stance": (31, 50),
        "pre_swing": (50, 60), "initial_swing": (60, 75), "mid_swing": (75, 87), "terminal_swing": (87, 100),
    }
    for side in ("left", "right"):
        assert _sub(reference, side, "initial_contact").available
        for name, (a, b) in expected.items():
            p = _sub(reference, side, name)
            assert p.available, (side, name, p.reason)
            assert p.start_pct == pytest.approx(a, abs=4.0), (side, name)
            assert p.end_pct == pytest.approx(b, abs=4.0), (side, name)


def test_individual_cycles_reviewable(reference):
    valid = [c for c in reference.cycles if c.included_in_aggregate]
    assert len(valid) >= 6
    for c in valid:
        assert c.status == "valid"
        assert c.stance_s + c.swing_s == pytest.approx(c.duration_s, abs=1e-3)
        assert c.min_event_confidence >= MIN_EVENT_CONFIDENCE
    partial = [c for c in reference.cycles if "partial" in c.cycle_id]
    assert partial and all(c.status == "incomplete" and not c.included_in_aggregate for c in partial)


# --------------------------------------------------------------------------- #
# Variants                                                                    #
# --------------------------------------------------------------------------- #

def test_asymmetric_stance_detected():
    res = analyze_gait_cycles(make_walker(stance_frac=(0.65, 0.55)), "side", FPS)
    assert _metric(res, "stance_pct", "left").value == pytest.approx(65.0, abs=3.0)
    assert _metric(res, "stance_pct", "right").value == pytest.approx(55.0, abs=3.0)
    assert _metric(res, "stance_pct_asymmetry").value == pytest.approx(symmetry_index(65, 55), abs=6.0)


def test_right_to_left_walking_gives_same_results():
    res = analyze_gait_cycles(make_walker(direction=-1), "side", FPS)
    assert res.walking_direction == "right_to_left"
    assert _metric(res, "stance_pct", "left").value == pytest.approx(60.0, abs=3.0)


def test_treadmill_uses_facing_direction():
    res = analyze_gait_cycles(make_walker(speed=0.0), "side", FPS)
    assert res.direction_source == "facing_direction"
    assert _metric(res, "stance_pct", "right").value == pytest.approx(60.0, abs=3.0)


@pytest.mark.parametrize("view", ["front", "rear"])
def test_front_and_rear_views_not_forced(view):
    res = analyze_gait_cycles(make_walker(), view, FPS)
    assert res.status == "not_supported_view"
    assert res.events == [] and res.cycles == [] and res.phase_metrics == []


def test_low_confidence_detections_flagged_and_excluded():
    res = analyze_gait_cycles(make_walker(conf=0.4), "side", FPS)
    assert res.events and all(e.low_confidence for e in res.events)
    assert res.counts["cycles_valid"] == 0
    assert res.counts["cycles_low_confidence"] > 0
    assert res.status == "insufficient_data"
    assert _metric(res, "stance_time", "left").status == "unavailable"
    assert res.cadence.status == "unavailable"


def test_landmark_gap_marks_cycle_incomplete():
    res = analyze_gait_cycles(make_walker(gap=("left", 2.5, 3.0)), "side", FPS)
    left = [c for c in res.cycles if c.side == "left" and "partial" not in c.cycle_id]
    gapped = [c for c in left if c.start_s < 3.0 and (c.end_s or 0) > 2.5]
    assert gapped and all(c.status == "incomplete" and not c.included_in_aggregate for c in gapped)
    assert any(c.included_in_aggregate for c in left)  # other cycles still used
    # Aggregates are unaffected by the excluded cycle.
    assert _metric(res, "stance_pct", "left").value == pytest.approx(60.0, abs=3.0)


def test_ankle_proxy_landmarks_flagged_and_heel_off_not_guessed():
    res = analyze_gait_cycles(make_walker(heel_tracked=False, toe_tracked=False, planted_ankle=True), "side", FPS)
    assert "proxy" in res.landmarks_used["left_initial_contact"]
    assert "proxy" in res.landmarks_used["left_toe_off"]
    # Ankle-only events still recover the reference stance (60 %), with reduced confidence.
    assert _metric(res, "stance_pct", "left").value == pytest.approx(60.0, abs=4.0)
    assert max(e.confidence for e in res.events) <= 0.9 * 0.85 + 1e-6
    assert any("proxy" in w for w in res.warnings)
    for side in ("left", "right"):
        assert not _sub(res, side, "midstance").available
        assert "Heel landmark" in _sub(res, side, "midstance").reason
        assert not _sub(res, side, "terminal_stance").available


def test_short_recording_insufficient():
    res = analyze_gait_cycles(make_walker(duration=1.0), "side", FPS)
    assert res.status == "insufficient_data"


# --------------------------------------------------------------------------- #
# Hand-calculated cycle examples                                              #
# --------------------------------------------------------------------------- #

def _ev(kind, side, t, conf=0.9):
    return CycleEvent(event_type=kind, side=side, frame_index=int(round(t * 100)), timestamp_s=t,
                      confidence=conf, low_confidence=conf < MIN_EVENT_CONFIDENCE, landmark="x")


def _timeline(t_end=3.0):
    return np.arange(0.0, t_end, 0.01)


def test_hand_calculated_cycle_values():
    # Left: IC 0.0, TO 0.62, IC 1.0. Right: TO 0.12, IC 0.50.
    events = [_ev("initial_contact", "left", 0.0), _ev("toe_off", "right", 0.12), _ev("initial_contact", "right", 0.5),
              _ev("toe_off", "left", 0.62), _ev("initial_contact", "left", 1.0)]
    t = _timeline(1.0)
    cycles = build_cycles(events, t, {"left": np.ones_like(t, bool), "right": np.ones_like(t, bool)})
    c = next(c for c in cycles if c.cycle_id == "left_cycle_1")
    assert c.status == "valid"
    assert c.duration_s == pytest.approx(1.0)
    assert c.stance_s == pytest.approx(0.62) and c.swing_s == pytest.approx(0.38)
    assert c.stance_pct == pytest.approx(62.0) and c.swing_pct == pytest.approx(38.0)
    assert c.initial_double_support_s == pytest.approx(0.12)
    assert c.terminal_double_support_s == pytest.approx(0.12)
    assert c.double_support_s == pytest.approx(0.24) and c.double_support_pct == pytest.approx(24.0)


def test_double_support_requires_contralateral_events():
    events = [_ev("initial_contact", "left", 0.0), _ev("toe_off", "left", 0.62), _ev("initial_contact", "left", 1.0)]
    t = _timeline(1.0)
    c = build_cycles(events, t, {"left": np.ones_like(t, bool)})[0]
    assert c.status == "valid"
    assert c.double_support_s is None and c.double_support_pct is None
    assert any("Double support not estimated" in r for r in c.reasons)

    low = events + [_ev("toe_off", "right", 0.12, conf=0.3), _ev("initial_contact", "right", 0.5)]
    c = build_cycles(sorted(low, key=lambda e: e.timestamp_s), t, {"left": np.ones_like(t, bool)})[0]
    assert c.double_support_s is None  # low-confidence contralateral event


def test_missing_or_duplicate_toe_off_is_incomplete():
    t = _timeline(1.0)
    m = {"left": np.ones_like(t, bool)}
    none = [_ev("initial_contact", "left", 0.0), _ev("initial_contact", "left", 1.0)]
    assert build_cycles(none, t, m)[0].status == "incomplete"
    dup = [_ev("initial_contact", "left", 0.0), _ev("toe_off", "left", 0.5), _ev("toe_off", "left", 0.6),
           _ev("initial_contact", "left", 1.0)]
    c = build_cycles(dup, t, m)[0]
    assert c.status == "incomplete" and c.stance_s is None


def test_implausible_and_low_confidence_cycles_excluded():
    t = _timeline(3.0)
    m = {"left": np.ones_like(t, bool)}
    long_cycle = [_ev("initial_contact", "left", 0.0), _ev("toe_off", "left", 1.8), _ev("initial_contact", "left", 2.9)]
    c = build_cycles(long_cycle, t, m)[0]
    assert c.status == "implausible" and not c.included_in_aggregate
    weak = [_ev("initial_contact", "left", 0.0), _ev("toe_off", "left", 0.6, conf=0.4), _ev("initial_contact", "left", 1.0)]
    c = build_cycles(weak, t, m)[0]
    assert c.status == "low_confidence" and not c.included_in_aggregate


def test_symmetry_index_reference_values():
    assert symmetry_index(0.6, 0.6) == 0.0
    assert symmetry_index(0.66, 0.6) == pytest.approx(9.52, abs=0.01)  # |0.06| / 0.63 * 100
    assert symmetry_index(None, 0.6) is None


# --------------------------------------------------------------------------- #
# Integration helpers: labelled view and cadence hand-off                     #
# --------------------------------------------------------------------------- #

from src.gait_events.gait_cycle_analysis import apply_labelled_view, cadence_for_assessment  # noqa: E402


def test_labelled_side_view_overrides_detector():
    poses = make_walker()
    detected = analyze_gait_cycles(poses, "front", FPS)  # detector got it wrong
    out = apply_labelled_view(detected, poses, "side", FPS)
    assert out.status == "analysed" and out.camera_view == "side"
    assert out.view_source == "labelled" and out.detected_view == "front"
    assert any("automatic view detector suggested 'front'" in w for w in out.warnings)


def test_labelled_view_matching_detector_has_no_warning():
    poses = make_walker()
    a = analyze_gait_cycles(poses, "side", FPS)
    out = apply_labelled_view(a, poses, "side", FPS)
    assert out is a and out.view_source == "labelled"
    assert not any("view detector" in w for w in out.warnings)


def test_unlabelled_recording_keeps_detector_view():
    poses = make_walker()
    a = analyze_gait_cycles(poses, "unknown", FPS)
    out = apply_labelled_view(a, poses, None, FPS)
    assert out.view_source == "detected" and out.camera_view == "unknown"


def test_cadence_for_assessment_only_when_supported():
    good = analyze_gait_cycles(make_walker(), "side", FPS)
    value, conf = cadence_for_assessment(good)
    assert value == pytest.approx(120.0 / T, abs=3.0) and 0.5 <= conf <= 1.0
    assert cadence_for_assessment(analyze_gait_cycles(make_walker(conf=0.4), "side", FPS)) is None
    assert cadence_for_assessment(analyze_gait_cycles(make_walker(), "front", FPS)) is None
    assert cadence_for_assessment(None) is None
