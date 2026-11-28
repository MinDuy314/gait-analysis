"""Evaluate detected gait events against manual reference annotations.

Usage:
    python tools/validation/evaluate_events.py CLIPS_DIR [--models yolo mediapipe]
                                               [--tolerance-ms 100] [--out OUT_DIR]

CLIPS_DIR holds side-view videos and their reference files "<clip>.<annotator>.events.csv"
(made with annotate_events.py). Only clips with at least one reference file are evaluated.
Poses are cached in OUT_DIR/pose_cache so re-running (e.g. after changing the gait-cycle
method) does not re-run the pose models.

Outputs in OUT_DIR (default: CLIPS_DIR/validation_output):
    validation_report.md   human-readable report
    validation_results.json full per-clip, per-model results
    event_errors.csv       one row per matched event (for your own statistics)
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.gait_events.gait_cycle_analysis import analyze_gait_cycles  # noqa: E402
from src.pose_estimation.landmark_schema import FramePose  # noqa: E402
from src.validation.gait_event_kit import (  # noqa: E402
    ANNOTATION_SUFFIX,
    aggregate,
    evaluate_clip,
    find_annotations,
    inter_rater,
    read_annotation,
    render_markdown,
)

VIDEO_EXT = {".mp4", ".mov", ".avi", ".webm", ".mkv"}


def load_or_estimate_poses(video: Path, model: str, cache_dir: Path):
    cache = cache_dir / f"{video.stem}.{model}.poses.json"
    if cache.exists() and cache.stat().st_mtime >= video.stat().st_mtime:
        data = json.loads(cache.read_text(encoding="utf-8"))
        return [FramePose.model_validate(p) for p in data["poses"]], data["fps"]
    from src.pose_estimation.pose_factory import create_pose_estimator
    from src.video.frame_extractor import extract_frames
    from src.video.video_validator import validate_video

    meta = validate_video(video).metadata
    fps = meta.fps if meta and meta.fps > 0 else None
    est = create_pose_estimator(model)
    poses = [est.estimate_frame(f.image_bgr, f.frame_index, f.timestamp_s, f.orig_width, f.orig_height)
             for f in extract_frames(video_path=video)]
    if hasattr(est, "close"):
        est.close()
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"fps": fps, "poses": [p.model_dump() for p in poses]}), encoding="utf-8")
    return poses, fps


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clips_dir", type=Path)
    ap.add_argument("--models", nargs="+", default=["yolo", "mediapipe"], choices=["yolo", "mediapipe"])
    ap.add_argument("--tolerance-ms", type=float, default=100.0)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    out = args.out or args.clips_dir / "validation_output"
    out.mkdir(parents=True, exist_ok=True)
    videos = sorted(p for p in args.clips_dir.iterdir()
                    if p.suffix.lower() in VIDEO_EXT and find_annotations(p))
    if not videos:
        sys.exit(f"No clips with '*{ANNOTATION_SUFFIX}' reference files found in {args.clips_dir}")

    results, inter, frame_ms = [], [], []
    for video in videos:
        anns = [read_annotation(p) for p in find_annotations(video)]
        primary = anns[0]
        if len(anns) > 1:
            inter.append({"clip": video.stem, "annotators": f"{anns[1].annotator} vs {anns[0].annotator}",
                          "rows": inter_rater(anns[0], anns[1], args.tolerance_ms)})
        for model in args.models:
            print(f"[{video.name}] {model}: estimating/loading poses ...", flush=True)
            poses, fps = load_or_estimate_poses(video, model, out / "pose_cache")
            if fps:
                frame_ms.append(1000.0 / fps)
            analysis = analyze_gait_cycles(poses, "side", fps)  # validation clips are side views
            frame_times = {p.frame_index: p.timestamp_s for p in poses}
            ev = evaluate_clip(analysis, primary, args.tolerance_ms, frame_times)
            results.append({"clip": video.stem, "model": model, "annotator": primary.annotator, "evaluation": ev})

    summary = aggregate(results)
    md = render_markdown(results, summary, inter, args.tolerance_ms,
                         sum(frame_ms) / len(frame_ms) if frame_ms else None)
    (out / "validation_report.md").write_text(md, encoding="utf-8")
    (out / "validation_results.json").write_text(
        json.dumps({"tolerance_ms": args.tolerance_ms, "summary": summary, "inter_rater": inter, "clips": results},
                   indent=2), encoding="utf-8")
    with open(out / "event_errors.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["clip", "model", "side", "event_type", "signed_error_ms"])
        for r in results:
            for row in r["evaluation"]["events"]:
                for e in row["errors_ms"]:
                    w.writerow([r["clip"], r["model"], row["side"], row["event_type"], e])
    print(f"\nReport: {out / 'validation_report.md'}")


if __name__ == "__main__":
    main()
