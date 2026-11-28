# Gait event validation kit

Checks how well the app's automatic gait events (initial contact, toe-off) and stance
percentages agree with careful manual marking on **your own real walking videos**, and compares
the YOLO and MediaPipe pose models.

> A good result shows agreement on the clips you tested. It is **not** proof of clinical
> validity, which needs an appropriate reference method (e.g. instrumented walkway or force
> plates), an adequate sample and clinical review.

## 1. Collect clips

- **Side view**, camera at hip height, perpendicular to the walkway, 3–4 m away, not moving.
- **Continuous walking**: at least 3 full strides per foot inside the frame
  (≈ 6–8 m of walkway, or a treadmill). Clips with only a few slow steps give no valid cycles.
- Good light, plain background, fitted clothing, feet clearly visible, one person in view.
- Start with **5–10 clips**, ideally from different people and walking speeds, including some
  patients whose gait you want the app to handle.
- Put them in one folder, e.g. `validation_clips/`. Keep it out of git if they show patients.

## 2. Mark the reference events

```powershell
$env:PYTHONPATH = "C:\Users\nduym\Documents\Gait-analysis"
& "C:\Users\nduym\miniforge3\envs\yolo\python.exe" tools\validation\annotate_events.py validation_clips\walk01.mp4 --annotator DrA
```

| Key | Action |
|---|---|
| `D` / `→`, `A` / `←` | next / previous frame |
| `C` / `Z` | +10 / −10 frames |
| `Space` | play / pause |
| `1` / `2` | left initial contact / left toe-off |
| `3` / `4` | right initial contact / right toe-off |
| `X` / `U` | delete marks on this frame / undo |
| `N` | jump to next mark |
| `S` / `Q` | save / save and quit |

**Definitions** – mark the *first frame* where the event is visible:

- **Initial contact**: the first frame the foot (normally the heel) touches the ground.
- **Toe-off**: the first frame the foot has completely left the ground.

Mark **every** event of both feet in the clip, including the first and last partial steps.
Marks are saved as `walk01.DrA.events.csv` next to the video; reopening the clip with the same
name continues where you left off.

**Inter-rater agreement (recommended):** have a second person mark the same clips with their own
`--annotator` name, without looking at the first person's marks. The report then shows how much
two humans differ, which is the realistic accuracy limit for comparison.

## 3. Run the evaluation

```powershell
& "C:\Users\nduym\miniforge3\envs\yolo\python.exe" tools\validation\evaluate_events.py validation_clips --models yolo mediapipe
```

Results go to `validation_clips/validation_output/`:

- `validation_report.md` – summary per model and per clip
- `validation_results.json` – full results
- `event_errors.csv` – one row per matched event, for your own statistics

Poses are cached, so re-running after a method change takes seconds. MediaPipe needs
`models/mediapipe/pose_landmarker_full.task` (see `src/pose_estimation/mediapipe_estimator.py`).

## 4. Read the report

| Measure | Meaning |
|---|---|
| Precision | Share of detected events that match a reference mark within ±100 ms |
| Recall | Share of reference events that were detected |
| Bias | Mean signed error, detected − reference (negative = app detects early) |
| MAE | Mean absolute timing error |
| 95% LoA | Bland–Altman limits of agreement: 95 % of errors fall in this range |
| Stance % difference | App's mean stance % minus the stance % from your marks, per side |

Context for interpretation: one frame is ~33 ms at 30 fps and ~42 ms at 24 fps, so errors of
about one frame are at the resolution limit of the video. Compare the model errors with the
inter-rater errors: if the app differs from a human about as much as two humans differ from
each other, event timing is as good as manual marking on that footage.

The matching tolerance can be changed with `--tolerance-ms`. Errors and agreement are reported,
not judged; what counts as acceptable depends on the clinical use and should be decided by the
clinical team.
