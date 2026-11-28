"""Frame-by-frame gait event annotation tool (reference marks for validation).

Usage:
    python tools/validation/annotate_events.py VIDEO --annotator NAME

Keys (shown on screen; press H to toggle help):
    D / A or → / ←   next / previous frame          C / Z   +10 / -10 frames
    Space            play / pause                   Home    first frame
    1  left initial contact      2  left toe-off
    3  right initial contact     4  right toe-off
    X  delete marks on this frame        U  undo last mark
    N  jump to next mark                 S  save          Q / Esc  save and quit

Definitions (mark the FIRST frame where the event is visible):
    initial contact = first frame the foot (usually heel) touches the ground
    toe-off         = first frame the foot has left the ground (toe no longer in contact)

Marks are saved to "<video stem>.<annotator>.events.csv" next to the video and loaded again
when you reopen the same clip with the same annotator name.
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.video.frame_extractor import extract_frames  # noqa: E402
from src.validation.gait_event_kit import (  # noqa: E402
    ReferenceAnnotation,
    ReferenceEvent,
    annotation_path,
    read_annotation,
    write_annotation,
)

KEYMAP = {
    ord("1"): ("left", "initial_contact"),
    ord("2"): ("left", "toe_off"),
    ord("3"): ("right", "initial_contact"),
    ord("4"): ("right", "toe_off"),
}
ARROW_RIGHT = {2555904, 65363, 63235}  # Windows, Linux (GTK), macOS
ARROW_LEFT = {2424832, 65361, 63234}
HOME = {2359296, 65360, 63273}
COLORS = {("left", "initial_contact"): (60, 200, 60), ("left", "toe_off"): (0, 140, 255),
          ("right", "initial_contact"): (255, 120, 60), ("right", "toe_off"): (200, 60, 200)}
LABEL = {("left", "initial_contact"): "L IC", ("left", "toe_off"): "L TO",
         ("right", "initial_contact"): "R IC", ("right", "toe_off"): "R TO"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--annotator", required=True, help="Your name or initials (stored with every mark)")
    ap.add_argument("--max-width", type=int, default=1280, help="Display width limit in pixels")
    args = ap.parse_args()

    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        sys.exit(f"Cannot open {args.video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.release()
    # Decode with the analysis pipeline's own frame extractor so frame numbers and
    # timestamps are identical to what the pose models see.
    frames, times = [], []
    for f in extract_frames(video_path=args.video):
        frames.append(f.image_bgr)
        times.append(f.timestamp_s)
    if not frames:
        sys.exit("No frames decoded.")

    out_path = annotation_path(args.video, args.annotator)
    ann = read_annotation(out_path) if out_path.exists() else ReferenceAnnotation(args.video.stem, args.annotator)
    ann.annotator = args.annotator
    history = []
    idx, playing, show_help, dirty = 0, False, True, False
    scale = min(1.0, args.max_width / frames[0].shape[1])
    win = f"Annotate gait events - {args.video.name} ({args.annotator})"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    def save():
        nonlocal dirty
        write_annotation(out_path, ann)
        dirty = False
        print(f"Saved {len(ann.events)} marks to {out_path}")

    while True:
        img = frames[idx].copy()
        if scale < 1.0:
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]
        # Timeline with marks
        bar_y = h - 24
        cv2.rectangle(img, (0, bar_y - 14), (w, h), (30, 30, 30), -1)
        for e in ann.events:
            x = int(e.frame_index / max(1, len(frames) - 1) * (w - 1))
            cv2.line(img, (x, bar_y - 12), (x, h - 2), COLORS[(e.side, e.event_type)], 2)
        cx = int(idx / max(1, len(frames) - 1) * (w - 1))
        cv2.line(img, (cx, bar_y - 14), (cx, h), (255, 255, 255), 1)
        here = [LABEL[(e.side, e.event_type)] for e in ann.events if e.frame_index == idx]
        status = f"frame {idx}/{len(frames) - 1}  t={times[idx]:.3f}s  marks={len(ann.events)}" + \
                 (f"  HERE: {', '.join(here)}" if here else "") + ("  *unsaved*" if dirty else "")
        cv2.putText(img, status, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(img, status, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        if show_help:
            for i, line in enumerate(["A/D or arrows: +-1 frame  Z/C: +-10  Space: play  N: next mark",
                                      "1 L-IC  2 L-TO  3 R-IC  4 R-TO   X delete  U undo  S save  Q quit  H help"]):
                cv2.putText(img, line, (8, 48 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
                cv2.putText(img, line, (8, 48 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1, cv2.LINE_AA)
        cv2.imshow(win, img)

        key = cv2.waitKeyEx(int(1000 / fps) if playing else 0)
        if playing and key == -1:
            idx = min(idx + 1, len(frames) - 1)
            playing = idx < len(frames) - 1
            continue
        k = key & 0xFF if key != -1 else -1
        if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
            k = ord("q")
        if k in (ord("q"), 27):
            if dirty or not out_path.exists():
                save()
            break
        playing = False if key != -1 and k != ord(" ") else playing
        if key in ARROW_RIGHT or k == ord("d"):
            idx = min(idx + 1, len(frames) - 1)
        elif key in ARROW_LEFT or k == ord("a"):
            idx = max(idx - 1, 0)
        elif k == ord("c"):
            idx = min(idx + 10, len(frames) - 1)
        elif k == ord("z"):
            idx = max(idx - 10, 0)
        elif key in HOME:
            idx = 0
        elif k == ord(" "):
            playing = not playing
        elif k == ord("h"):
            show_help = not show_help
        elif k == ord("s"):
            save()
        elif k == ord("n"):
            later = sorted(e.frame_index for e in ann.events if e.frame_index > idx)
            idx = later[0] if later else idx
        elif k == ord("x"):
            removed = [e for e in ann.events if e.frame_index == idx]
            if removed:
                ann.events = [e for e in ann.events if e.frame_index != idx]
                history.append(("del", removed))
                dirty = True
        elif k == ord("u") and history:
            op, items = history.pop()
            if op == "add":
                ann.events = [e for e in ann.events if e is not items[0]]
            else:
                ann.events.extend(items)
            dirty = True
        elif key in KEYMAP or k in KEYMAP:
            side, et = KEYMAP.get(key) or KEYMAP[k]
            if not any(e.frame_index == idx and e.side == side and e.event_type == et for e in ann.events):
                ev = ReferenceEvent(side=side, event_type=et, frame_index=idx, timestamp_s=round(times[idx], 4))
                ann.events.append(ev)
                history.append(("add", [ev]))
                dirty = True

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
