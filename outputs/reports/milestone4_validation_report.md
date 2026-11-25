# Milestone 4: Biomechanical Validation Report

**Dataset**: Nature Scientific Data 2025 (`s41597-025-06535-y`) / Figshare 29300888.v1  
**Scope**: Verification of feature compatibility, agreement metrics, gait event matching, and curve comparison between computer-vision video estimates and laboratory motion capture.

---

## 1. Feature Compatibility Matrix

| Video Feature | Reference Variable | Plane | Video Units | Ref Units | Compatibility Status | Core Limitation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `left_knee_flexion_extension_rom` | `kneeAx` | Sagittal | degrees | degrees | **Conditionally Comparable** | 2D projection vs 3D Cardan angle; requires true side view |
| `right_knee_flexion_extension_rom` | `kneeAx_contra` | Sagittal | degrees | degrees | **Conditionally Comparable** | Contralateral self-occlusion in monocular side view |
| `ankle_angle_planar` | `ankleAx` | Sagittal | degrees | degrees | **Conditionally Comparable** | Surface landmark noise on foot; static zero offset differences |
| `cadence` | `gait_speed` | Spatiotemporal | steps/min | m/s | **Not Comparable** | Unit & concept mismatch; physical scale unavailable |
| `trunk_lateral_displacement_px` | `thoraxAy` | Frontal | pixels | degrees | **Not Comparable** | Uncalibrated pixel distance vs 3D angular degrees |

---

## 2. Pairing & Testability Status on Real Dataset

* **Raw Video Recordings Found**: `0` files in `data/video/raw/`.
* **Experimental Fact**: The public Figshare repository `29300888.v1` provides optical motion capture files (`.c3d`, `.txt`) and preprocessed NumPy arrays (`.npz`), but **does not bundle synchronized raw video files**.
* **Status**:
  * Event validation on real data: **`not_testable`** (requires genuine paired video).
  * Joint angle agreement on real data: **`not_testable`** until paired video recordings are collected.
  * Incompatible features: **`not_comparable`** (explicitly rejected).

---

## 3. Implemented Validation Framework

The validation layer (`src/validation/`) implements:
1. **Agreement Metrics (`calculate_agreement_metrics`)**: Bias, MAE, RMSE, Pearson $r$, Spearman $\rho$, Bland–Altman 95% Limits of Agreement, and participant-level cluster bootstrap 95% confidence intervals.
2. **Gait Event Validation (`evaluate_gait_events`)**: Greedy temporal tolerance window (e.g. 100ms), precision, recall, F1-score, and signed timing errors (MAE, RMSE, SD).
3. **101-Point Gait Curve Validation (`validate_gait_curves`)**: Pointwise MAE and bias curves across 0–100% of the gait cycle, preserving NaNs without silent imputation.
4. **Participant Isolation**: Strict adherence to `metadata/participant_splits.csv` (7 train, 2 val, 2 test) to prevent cross-contamination across repeated trials.

---

## 4. Scientific Constraints & Limitations

1. **Non-Equivalence**: 2D monocular video estimates cannot be presented as equivalent to calibrated 3D Plug-in Gait laboratory measurements.
2. **Correlation vs Agreement**: Correlation measures linear association, not agreement. Bland–Altman limits and systematic bias are required.
3. **Synthetic Tests**: Unit tests use deterministic synthetic signals to guarantee algorithmic correctness, but synthetic tests do **not** constitute clinical or biological validation.
