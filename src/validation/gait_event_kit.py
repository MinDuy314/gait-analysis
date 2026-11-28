"""Real-video gait-event validation kit: reference annotations, evaluation and report.

Workflow (see tools/validation/README.md):
  1. A clinician marks initial contact (IC) and toe-off (TO) frame by frame for each
     side-view clip with ``tools/validation/annotate_events.py``. Each annotator's marks
     are saved as ``<clip>.<annotator>.events.csv`` next to the clip.
  2. ``tools/validation/evaluate_events.py`` runs the pose model(s) + gait-cycle analysis
     on every annotated clip and compares the detected events and phase percentages
     with the reference.

Metrics
  * Event detection: precision, recall, F1 within a matching tolerance (default 100 ms).
  * Timing: bias (mean signed error, detected - reference), MAE, SD, per event type/side.
  * Phase agreement: per-side mean stance % from reference events vs. the analysis.
  * Inter-rater agreement when two annotators marked the same clip.

A good result on a small clip set shows the pipeline is plausible on that footage; it is
not proof of clinical validity, which needs an appropriate reference method and sample.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

from src.gait_events.gait_cycle_analysis import (
    CycleEvent,
    GaitCycleAnalysis,
    build_cycles,
)
from src.validation.event_validation import evaluate_gait_events

EVENT_TYPES = ("initial_contact", "toe_off")
SIDES = ("left", "right")
CSV_FIELDS = ["clip", "side", "event_type", "frame_index", "timestamp_s", "annotator", "note"]
ANNOTATION_SUFFIX = ".events.csv"


@dataclass
class ReferenceEvent:
    side: str
    event_type: str
    frame_index: int
    timestamp_s: float
    note: str = ""


@dataclass
class ReferenceAnnotation:
    clip: str
    annotator: str
    events: List[ReferenceEvent] = field(default_factory=list)

    def times(self, side: str, event_type: str) -> List[float]:
        return sorted(e.timestamp_s for e in self.events if e.side == side and e.event_type == event_type)


# --------------------------------------------------------------------------- #
# Annotation files                                                            #
# --------------------------------------------------------------------------- #

def annotation_path(video: Path, annotator: str) -> Path:
    safe = "".join(ch for ch in annotator if ch.isalnum() or ch in "-_") or "annotator"
    return video.with_name(f"{video.stem}.{safe}{ANNOTATION_SUFFIX}")


def write_annotation(path: Path, ann: ReferenceAnnotation) -> None:
    rows = sorted(ann.events, key=lambda e: (e.frame_index, e.side, e.event_type))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for e in rows:
            w.writerow({"clip": ann.clip, "side": e.side, "event_type": e.event_type,
                        "frame_index": e.frame_index, "timestamp_s": f"{e.timestamp_s:.4f}",
                        "annotator": ann.annotator, "note": e.note})


def read_annotation(path: Path) -> ReferenceAnnotation:
    events: List[ReferenceEvent] = []
    clip = annotator = ""
    with open(path, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            side, et = (row.get("side") or "").strip().lower(), (row.get("event_type") or "").strip().lower()
            if side not in SIDES or et not in EVENT_TYPES:
                raise ValueError(f"{path.name} line {i}: side must be left/right and event_type "
                                 f"initial_contact/toe_off (got {side!r}, {et!r})")
            events.append(ReferenceEvent(side=side, event_type=et, frame_index=int(row["frame_index"]),
                                         timestamp_s=float(row["timestamp_s"]), note=row.get("note") or ""))
            clip, annotator = row.get("clip") or clip, row.get("annotator") or annotator
    if not annotator:
        annotator = path.name[: -len(ANNOTATION_SUFFIX)].split(".")[-1]
    return ReferenceAnnotation(clip=clip or path.name.split(".")[0], annotator=annotator, events=events)


def find_annotations(video: Path) -> List[Path]:
    return sorted(video.parent.glob(f"{video.stem}.*{ANNOTATION_SUFFIX}"))


# --------------------------------------------------------------------------- #
# Comparison                                                                  #
# --------------------------------------------------------------------------- #

def _to_cycle_events(ann: ReferenceAnnotation) -> List[CycleEvent]:
    return [CycleEvent(event_type=e.event_type, side=e.side, frame_index=e.frame_index,
                       timestamp_s=e.timestamp_s, confidence=1.0, low_confidence=False, landmark="reference")
            for e in ann.events]


def reference_stance_pct(ann: ReferenceAnnotation, duration_s: float) -> Dict[str, Optional[float]]:
    """Per-side mean stance % computed from reference events with the same cycle rules."""
    t = np.arange(0.0, max(duration_s, 0.01), 0.01)
    cycles = build_cycles(_to_cycle_events(ann), t, {s: np.ones_like(t, dtype=bool) for s in SIDES})
    out: Dict[str, Optional[float]] = {}
    for side in SIDES:
        vals = [c.stance_pct for c in cycles if c.side == side and c.status == "valid"]
        out[side] = round(float(np.mean(vals)), 2) if vals else None
    return out


def _signed_errors_ms(detected: Sequence[float], reference: Sequence[float], tol_s: float) -> List[float]:
    """Signed errors of greedy nearest matches (same rule as evaluate_gait_events)."""
    used, errs = set(), []
    for d in sorted(detected):
        best, best_err = None, float("inf")
        for i, r in enumerate(sorted(reference)):
            if i in used:
                continue
            e = abs(d - r)
            if e <= tol_s and e < best_err:
                best, best_err = i, e
        if best is not None:
            used.add(best)
            errs.append((d - sorted(reference)[best]) * 1000.0)
    return errs


def compare_events(detected: Dict[tuple, List[float]], reference: Dict[tuple, List[float]],
                   tolerance_ms: float) -> List[dict]:
    """Rows per (side, event_type) with detection and timing metrics."""
    rows = []
    for side in SIDES:
        for et in EVENT_TYPES:
            det, ref = detected.get((side, et), []), reference.get((side, et), [])
            m = evaluate_gait_events(det, ref, event_type=et, side=side, tolerance_ms=tolerance_ms)
            errs = _signed_errors_ms(det, ref, tolerance_ms / 1000.0)
            rows.append({
                "side": side, "event_type": et,
                "n_reference": m.total_reference_events, "n_detected": m.total_detected_events,
                "true_positives": m.true_positives, "false_positives": m.false_positives,
                "false_negatives": m.false_negatives,
                "precision": m.precision, "recall": m.recall, "f1": m.f1_score,
                "bias_ms": round(float(np.mean(errs)), 1) if errs else None,
                "mae_ms": m.timing_mae_ms, "sd_ms": m.timing_error_sd_ms,
                "errors_ms": [round(e, 1) for e in errs],
            })
    return rows


def align_to_frames(ann: ReferenceAnnotation, frame_times: Dict[int, float]) -> ReferenceAnnotation:
    """Re-time reference marks from their frame numbers using the pipeline's frame timestamps.

    Comparing by frame number removes any timestamp offset between the annotation tool and the
    analysis decoder; marks on frames the pipeline never saw keep their stored timestamp.
    """
    events = [ReferenceEvent(side=e.side, event_type=e.event_type, frame_index=e.frame_index,
                             timestamp_s=frame_times.get(e.frame_index, e.timestamp_s), note=e.note)
              for e in ann.events]
    return ReferenceAnnotation(clip=ann.clip, annotator=ann.annotator, events=events)


def evaluate_clip(analysis: GaitCycleAnalysis, ann: ReferenceAnnotation, tolerance_ms: float = 100.0,
                  frame_times: Optional[Dict[int, float]] = None) -> dict:
    if frame_times:
        ann = align_to_frames(ann, frame_times)
    detected = {(s, et): [e.timestamp_s for e in analysis.events if e.side == s and e.event_type == et]
                for s in SIDES for et in EVENT_TYPES}
    reference = {(s, et): ann.times(s, et) for s in SIDES for et in EVENT_TYPES}
    ref_stance = reference_stance_pct(ann, analysis.duration_s or 0.0)
    pred_stance = {m.side: m.value for m in analysis.phase_metrics if m.name == "stance_pct" and m.side}
    stance = {}
    for side in SIDES:
        r, p = ref_stance.get(side), pred_stance.get(side)
        stance[side] = {"reference": r, "detected": p,
                        "difference": round(p - r, 2) if r is not None and p is not None else None}
    return {
        "status": analysis.status,
        "valid_cycles": analysis.counts.get("cycles_valid", 0),
        "landmarks": analysis.landmarks_used,
        "events": compare_events(detected, reference, tolerance_ms),
        "stance_pct": stance,
        "warnings": analysis.warnings,
    }


def inter_rater(a: ReferenceAnnotation, b: ReferenceAnnotation, tolerance_ms: float = 100.0) -> List[dict]:
    da = {(s, et): a.times(s, et) for s in SIDES for et in EVENT_TYPES}
    db = {(s, et): b.times(s, et) for s in SIDES for et in EVENT_TYPES}
    return compare_events(db, da, tolerance_ms)  # b relative to a


# --------------------------------------------------------------------------- #
# Aggregation & report                                                        #
# --------------------------------------------------------------------------- #

def aggregate(results: List[dict]) -> Dict[str, dict]:
    """Pool event errors and counts across clips, per model and event type."""
    out: Dict[str, dict] = {}
    for res in results:
        model = res["model"]
        agg = out.setdefault(model, {"clips": 0, "valid_cycles": 0, "by_event": {}, "stance_diff": []})
        agg["clips"] += 1
        agg["valid_cycles"] += res["evaluation"]["valid_cycles"]
        for row in res["evaluation"]["events"]:
            key = row["event_type"]
            e = agg["by_event"].setdefault(key, {"tp": 0, "fp": 0, "fn": 0, "errors": []})
            e["tp"] += row["true_positives"]
            e["fp"] += row["false_positives"]
            e["fn"] += row["false_negatives"]
            e["errors"].extend(row["errors_ms"])
        for side in SIDES:
            d = res["evaluation"]["stance_pct"][side]["difference"]
            if d is not None:
                agg["stance_diff"].append(d)
    for agg in out.values():
        for e in agg["by_event"].values():
            n_det, n_ref = e["tp"] + e["fp"], e["tp"] + e["fn"]
            e["precision"] = round(e["tp"] / n_det, 3) if n_det else None
            e["recall"] = round(e["tp"] / n_ref, 3) if n_ref else None
            errs = np.asarray(e.pop("errors"), dtype=float)
            e["n_matched"] = int(errs.size)
            e["bias_ms"] = round(float(errs.mean()), 1) if errs.size else None
            e["mae_ms"] = round(float(np.abs(errs).mean()), 1) if errs.size else None
            e["sd_ms"] = round(float(errs.std(ddof=1)), 1) if errs.size > 1 else None
            # 95 % limits of agreement (Bland-Altman) for timing error
            e["loa_ms"] = ([round(e["bias_ms"] - 1.96 * e["sd_ms"], 1), round(e["bias_ms"] + 1.96 * e["sd_ms"], 1)]
                           if e["sd_ms"] is not None else None)
        sd = np.asarray(agg.pop("stance_diff"), dtype=float)
        agg["stance_pct_mean_diff"] = round(float(sd.mean()), 2) if sd.size else None
        agg["stance_pct_mae"] = round(float(np.abs(sd).mean()), 2) if sd.size else None
        agg["stance_pct_n"] = int(sd.size)
    return out


def _fmt(v, suffix=""):
    return "—" if v is None else f"{v}{suffix}"


def render_markdown(results: List[dict], summary: Dict[str, dict], inter: List[dict], tolerance_ms: float,
                    frame_ms: Optional[float] = None) -> str:
    lines = [
        "# Gait event validation report",
        "",
        f"Clips evaluated: {len({r['clip'] for r in results})} · matching tolerance ±{tolerance_ms:.0f} ms"
        + (f" · one video frame ≈ {frame_ms:.0f} ms" if frame_ms else ""),
        "",
        "Reference = frame-by-frame manual annotation. Errors are detected minus reference "
        "(negative = detected early). Results describe agreement on these clips only; they are "
        "not evidence of clinical validity on their own.",
        "",
        "## Summary by model",
        "",
        "| Model | Event | Precision | Recall | Matched | Bias (ms) | MAE (ms) | SD (ms) | 95% LoA (ms) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for model, agg in summary.items():
        for et in EVENT_TYPES:
            e = agg["by_event"].get(et)
            if not e:
                continue
            loa = f"{e['loa_ms'][0]} to {e['loa_ms'][1]}" if e["loa_ms"] else "—"
            lines.append(f"| {model} | {et.replace('_', ' ')} | {_fmt(e['precision'])} | {_fmt(e['recall'])} | "
                         f"{e['n_matched']} | {_fmt(e['bias_ms'])} | {_fmt(e['mae_ms'])} | {_fmt(e['sd_ms'])} | {loa} |")
    lines += ["", "| Model | Valid cycles | Stance % difference, mean (MAE), n sides |", "|---|---|---|"]
    for model, agg in summary.items():
        lines.append(f"| {model} | {agg['valid_cycles']} | {_fmt(agg['stance_pct_mean_diff'])} "
                     f"({_fmt(agg['stance_pct_mae'])}), n={agg['stance_pct_n']} |")
    if inter:
        lines += ["", "## Inter-rater agreement", "",
                  "| Clip | Annotators | Event | Side | Matched | Bias (ms) | MAE (ms) |", "|---|---|---|---|---|---|---|"]
        for ir in inter:
            for row in ir["rows"]:
                lines.append(f"| {ir['clip']} | {ir['annotators']} | {row['event_type'].replace('_', ' ')} | {row['side']} | "
                             f"{row['true_positives']}/{row['n_reference']} | {_fmt(row['bias_ms'])} | {_fmt(row['mae_ms'])} |")
    lines += ["", "## Per clip", ""]
    for r in results:
        ev = r["evaluation"]
        lines.append(f"### {r['clip']} — {r['model']} (annotator: {r['annotator']})")
        lines.append(f"Status: {ev['status']} · valid cycles: {ev['valid_cycles']} · landmarks: "
                     f"{', '.join(f'{k}={v}' for k, v in ev['landmarks'].items()) or '—'}")
        lines += ["", "| Side | Event | Ref | Det | TP | FP | FN | Bias (ms) | MAE (ms) |", "|---|---|---|---|---|---|---|---|---|"]
        for row in ev["events"]:
            lines.append(f"| {row['side']} | {row['event_type'].replace('_', ' ')} | {row['n_reference']} | {row['n_detected']} | "
                         f"{row['true_positives']} | {row['false_positives']} | {row['false_negatives']} | "
                         f"{_fmt(row['bias_ms'])} | {_fmt(row['mae_ms'])} |")
        st = ev["stance_pct"]
        lines.append("")
        lines.append("Stance %: " + "; ".join(
            f"{s} ref {_fmt(st[s]['reference'])} vs det {_fmt(st[s]['detected'])} (diff {_fmt(st[s]['difference'])})"
            for s in SIDES))
        if ev["warnings"]:
            lines.append("")
            lines += [f"- ⚠ {w}" for w in ev["warnings"]]
        lines.append("")
    return "\n".join(lines) + "\n"
