"""Validation kit: annotation files, matching, timing statistics and report."""
import pytest

from src.gait_events.gait_cycle_analysis import analyze_gait_cycles
from src.validation.gait_event_kit import (
    ReferenceAnnotation,
    ReferenceEvent,
    aggregate,
    align_to_frames,
    annotation_path,
    compare_events,
    evaluate_clip,
    find_annotations,
    inter_rater,
    read_annotation,
    reference_stance_pct,
    render_markdown,
    write_annotation,
)
from tests.test_gait_cycle_analysis import FPS, T, make_walker


def _truth(duration=6.0, first=(0.2, 0.2 + T / 2), stance=0.6, shift_s=0.0, annotator="ref"):
    """Reference marks at the synthetic walker's true event times (optionally shifted)."""
    events = []
    for side, t0 in zip(("left", "right"), first):
        k = 0
        while t0 + k * T < duration:
            for et, t in (("initial_contact", t0 + k * T), ("toe_off", t0 + k * T + stance * T)):
                if t < duration - 0.05:
                    ts = round(t + shift_s, 4)
                    events.append(ReferenceEvent(side, et, int(round(ts * FPS)), ts))
            k += 1
    return ReferenceAnnotation("clip", annotator, events)


def test_annotation_roundtrip_and_discovery(tmp_path):
    video = tmp_path / "walk01.mp4"
    video.write_bytes(b"0")
    ann = ReferenceAnnotation("walk01", "Dr A", [ReferenceEvent("left", "initial_contact", 12, 0.5, "clear")])
    path = annotation_path(video, "Dr A")
    assert path.name == "walk01.DrA.events.csv"
    write_annotation(path, ann)
    back = read_annotation(path)
    assert back.annotator == "Dr A" and back.events[0].frame_index == 12 and back.events[0].note == "clear"
    assert find_annotations(video) == [path]


def test_invalid_annotation_rows_rejected(tmp_path):
    p = tmp_path / "x.a.events.csv"
    p.write_text("clip,side,event_type,frame_index,timestamp_s,annotator,note\nx,middle,initial_contact,1,0.1,a,\n")
    with pytest.raises(ValueError, match="side must be left/right"):
        read_annotation(p)


def test_compare_events_known_offsets():
    det = {("left", "initial_contact"): [1.02, 2.02, 3.5]}  # +20 ms twice, one false positive
    ref = {("left", "initial_contact"): [1.0, 2.0, 2.9]}  # 2.9 missed (outside 100 ms of 3.5)
    row = next(r for r in compare_events(det, ref, 100.0) if r["side"] == "left" and r["event_type"] == "initial_contact")
    assert (row["true_positives"], row["false_positives"], row["false_negatives"]) == (2, 1, 1)
    assert row["bias_ms"] == pytest.approx(20.0) and row["mae_ms"] == pytest.approx(20.0)
    assert row["precision"] == pytest.approx(0.667, abs=1e-3) and row["recall"] == pytest.approx(0.667, abs=1e-3)


def test_reference_stance_from_manual_marks():
    st = reference_stance_pct(_truth(), 6.0)
    assert st["left"] == pytest.approx(60.0, abs=0.5) and st["right"] == pytest.approx(60.0, abs=0.5)


def test_align_to_frames_uses_pipeline_timestamps():
    ann = ReferenceAnnotation("c", "a", [ReferenceEvent("left", "toe_off", 10, 0.999)])
    aligned = align_to_frames(ann, {10: 0.4167})
    assert aligned.events[0].timestamp_s == 0.4167 and ann.events[0].timestamp_s == 0.999


def test_evaluate_clip_on_reference_walker():
    poses = make_walker()
    analysis = analyze_gait_cycles(poses, "side", FPS)
    frame_times = {p.frame_index: p.timestamp_s for p in poses}
    res = evaluate_clip(analysis, _truth(), 100.0, frame_times)
    for row in res["events"]:
        assert row["recall"] >= 0.8 and row["precision"] >= 0.8, row
        assert row["mae_ms"] is not None and row["mae_ms"] <= 1.5 * 1000 / FPS
    for side in ("left", "right"):
        assert abs(res["stance_pct"][side]["difference"]) <= 3.0


def test_systematic_offset_shows_as_bias_and_loa():
    poses = make_walker()
    analysis = analyze_gait_cycles(poses, "side", FPS)
    late = _truth(shift_s=-2 / FPS)  # annotator marks 2 frames earlier -> detection appears ~+67 ms late
    res = [{"clip": "c", "model": "m", "annotator": "a", "evaluation": evaluate_clip(analysis, late, 100.0)}]
    summary = aggregate(res)
    ic = summary["m"]["by_event"]["initial_contact"]
    assert ic["bias_ms"] == pytest.approx(2000 / FPS, abs=20.0)
    assert ic["loa_ms"][0] <= ic["bias_ms"] <= ic["loa_ms"][1]
    md = render_markdown(res, summary, [], 100.0, 1000 / FPS)
    assert "| m | initial contact |" in md and "not evidence of clinical validity" in md


def test_inter_rater_agreement():
    a, b = _truth(annotator="a"), _truth(shift_s=1 / FPS, annotator="b")
    rows = inter_rater(a, b)
    ic = next(r for r in rows if r["side"] == "left" and r["event_type"] == "initial_contact")
    assert ic["recall"] == 1.0 and ic["bias_ms"] == pytest.approx(1000 / FPS, abs=1.0)


def test_annotation_tool_with_scripted_keys(tmp_path, monkeypatch):
    """Drive tools/validation/annotate_events.py off-screen with a scripted key sequence."""
    import importlib.util
    import sys
    from pathlib import Path

    import cv2
    import numpy as np

    video = tmp_path / "walk.mp4"
    w = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 25.0, (160, 120))
    for i in range(30):
        w.write(np.full((120, 160, 3), i * 8, dtype=np.uint8))
    w.release()

    keys = iter([ord("d"), ord("d"), ord("1"),            # frame 2: left IC
                 ord("c"), ord("2"),                      # frame 12: left TO
                 ord("3"), ord("u"),                      # add right IC then undo it
                 ord("a"), ord("4"),                      # frame 11: right TO
                 ord("x"),                                # delete marks on frame 11
                 ord("d"), ord("3"),                      # frame 12: right IC
                 ord("q")])
    monkeypatch.setattr(cv2, "namedWindow", lambda *a, **k: None)
    monkeypatch.setattr(cv2, "imshow", lambda *a, **k: None)
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda *a, **k: None)
    monkeypatch.setattr(cv2, "getWindowProperty", lambda *a, **k: 1.0)
    monkeypatch.setattr(cv2, "waitKeyEx", lambda *a, **k: next(keys))
    path = Path(__file__).resolve().parents[1] / "tools" / "validation" / "annotate_events.py"
    spec = importlib.util.spec_from_file_location("annotate_events", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(sys, "argv", ["annotate_events.py", str(video), "--annotator", "tester"])
    mod.main()

    ann = read_annotation(annotation_path(video, "tester"))
    marks = sorted((e.frame_index, e.side, e.event_type) for e in ann.events)
    assert marks == [(2, "left", "initial_contact"), (12, "left", "toe_off"), (12, "right", "initial_contact")]
    assert ann.annotator == "tester"
    assert all(e.timestamp_s == pytest.approx(e.frame_index / 25.0, abs=0.05) for e in ann.events)
