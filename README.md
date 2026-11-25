# Gait Analysis Backend MVP (Milestones 1–6)

A modular, research-grounded backend system for human gait analysis. The platform combines laboratory motion-capture biomechanical reference models with video-based computer vision pose estimation, evidence-based assessment rules, longitudinal progress tracking, and a production-ready asynchronous FastAPI service.

> **Important Scientific & Medical Disclaimer**:
> This system is designed as a research, biomechanical observation, and monitoring support tool. **It is not a medical diagnostic device.** Video-derived kinematic estimates and statistical distributions must not be treated as clinical norms or used as substitutes for evaluation by qualified medical professionals.

---

## Architecture Overview

```text
gait_analysis/
├── config/                  # YAML dataset and feature extraction configurations
├── data/
│   ├── raw/                 # Original motion-capture datasets (NPZ, C3D, TXT)
│   ├── processed/           # Feature extractions, reference curves, baselines, QC
│   └── uploads/             # Video uploads managed with path-traversal protection
├── metadata/                # Trial index, subject index, participant splits, variable dictionary
├── outputs/
│   ├── figures/             # Validation and comparison plots
│   └── reports/             # Rendered individual and professional reports (Markdown/JSON)
├── src/
│   ├── api/                 # FastAPI routers, middleware, request/response schemas, dependencies
│   ├── assessment/          # Biomechanical rules, reference comparisons, bilateral symmetry, uncertainty
│   ├── core/                # Central AppConfig, custom exceptions, structured logging
│   ├── data_loader/         # NPZ discovery, schema validation, metadata extraction
│   ├── database/            # SQLAlchemy models, SQLite persistence, repositories
│   ├── feature_extraction/  # Motion-capture and video feature extraction (101-point cycle curves)
│   ├── gait_events/         # Foot strike/toe-off event detection and cycle segmentation
│   ├── jobs/                # Asynchronous job manager, worker pool, multi-stage task pipeline
│   ├── pose_estimation/     # Pluggable pose estimators (YOLOv8, synthetic) with CPU/CUDA support
│   ├── progress/            # Baseline builder, session comparability checks, trend analyzer
│   ├── reference/           # Reference curve builder and participant-independent splits
│   ├── reporting/           # Plain-language individual and clinical-grade professional report engines
│   ├── storage/             # File storage service, SHA-256 integrity, retention manager
│   ├── validation/          # Video-to-reference compatibility matrix, Bland-Altman, bootstrap metrics
│   ├── video/               # Video decoding, frame extraction, container validation
│   └── view_detection/      # Camera view classification (side, front, rear, oblique)
└── tests/                   # Complete automated test suite (74 tests covering Milestones 1–6)
```

---

## Key Capabilities (Milestones 1–6)

1. **Biomechanical Reference Pipeline (M1–M2)**
   - Discovers, schema-validates, and indexes 658 multi-condition motion-capture trials across 11 participants.
   - Extracts 79 variables per trial, builds 101-point normalized gait-cycle curves, computes bilateral symmetry metrics, and generates condition-specific reference distributions.

2. **Video Processing & Pose Estimation (M3)**
   - Ingests MP4/AVI/MOV/MKV/WEBM videos with header inspection, frame rate, and dimension validation.
   - Executes human pose estimation (YOLOv8-pose or synthetic fallback) with automatic CPU/CUDA switching.
   - Automatically classifies camera viewpoint (`side`, `front`, `rear`, `oblique`).
   - Detects heel-strike and toe-off events from kinematic trajectories to segment complete gait cycles.

3. **Biomechanical Validation Framework (M4)**
   - Formal compatibility matrix mapping video features to Plug-in Gait motion-capture variables.
   - Computes statistical agreement: mean bias, MAE, RMSE, Pearson $r$, Spearman $\rho$, Bland-Altman 95% limits of agreement, and bootstrap confidence intervals.

4. **Evidence-Based Assessment & Progress Tracking (M5)**
   - **View-gated biomechanical rules**: Evaluates sagittal knee flexion ROM, cadence, hip range, and temporal asymmetry with confidence gating.
   - **Statistical Reference Comparison**: Contextualizes user features against reference distributions (percentiles, $z$-scores) while explicitly distinguishing research distributions from clinical norms.
   - **Uncertainty Propagation**: Separates landmark confidence, feature quality, event detection certainty, cycle quality, and calibration status.
   - **Individualized Baseline**: Constructs versioned, multi-session baselines with variance retention.
   - **Longitudinal Tracking**: Classifies session changes (`improvement`, `deterioration`, `no_meaningful_change`, `insufficient_evidence`) relative to baseline standard deviation, with strict comparability gating across camera views, speeds, and surfaces.
   - **Dual Reporting**: Generates plain-language **Individual Reports** and comprehensive **Professional Reports** with complete provenance.

5. **Asynchronous FastAPI Backend MVP (M6)**
   - **RESTful API**: Clean endpoints for Subjects, Sessions, Recordings, Analysis Jobs, Assessments, Baselines, Progress, and Reports.
   - **SQLite & SQLAlchemy**: Relational persistence tracking subjects, sessions, jobs, anthropometrics per session, and deletion audit logs.
   - **Secure File Storage**: UUID-based filenames, path-traversal prevention, streaming upload validation, and SHA-256 hashing.
   - **Non-blocking Worker**: In-process background job manager executing an 11-stage pipeline with partial-result preservation on failure and retry mechanisms.
   - **Interactive Documentation**: OpenAPI / Swagger UI served at `/docs` and ReDoc at `/redoc`.

---

## Installation & Setup

### Prerequisites
- Python 3.10 or 3.11 (Python 3.11 recommended)
- Git
- Optional: NVIDIA GPU with CUDA 11.8+ / 12.0+ for accelerated pose estimation

### 1. Clone the Repository
```bash
git clone https://github.com/MinDuy314/gait-analysis.git
cd gait-analysis
```

### 2. Set Up a Virtual Environment
```bash
# On Linux / macOS
python -m venv .venv
source .venv/bin/activate

# On Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Or using Conda:
```bash
conda create -n gait-analysis python=3.11 -y
conda activate gait-analysis
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Running the Backend API

Start the local FastAPI development server:

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

The application will automatically initialize the SQLite database (`data/gait_analysis.db`).

### Endpoints Overview
- **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: `GET http://localhost:8000/health`
- **System Status**: `GET http://localhost:8000/api/v1/system/status` (reports Python, platform, and CUDA availability)

---

## End-to-End Workflow & API Usage

### Step 1: Create a Subject
```bash
curl -X POST "http://localhost:8000/api/v1/subjects" \
     -H "Content-Type: application/json" \
     -d '{"display_name": "Subject 01"}'
```
*Response returns `{"id": "<SUBJECT_ID>", "display_name": "Subject 01", ...}`*

### Step 2: Create an Analysis Session
Context and anthropometrics are stored per session and never silently overwritten:
```bash
curl -X POST "http://localhost:8000/api/v1/subjects/<SUBJECT_ID>/sessions" \
     -H "Content-Type: application/json" \
     -d '{
       "camera_view": "side",
       "walking_speed_ms": 1.25,
       "walking_surface": "level",
       "height_m": 1.75,
       "mass_kg": 70.0
     }'
```
*Response returns `{"id": "<SESSION_ID>", ...}`*

### Step 3: Upload a Walking Video
```bash
curl -X POST "http://localhost:8000/api/v1/sessions/<SESSION_ID>/recordings" \
     -F "file=@path/to/walking_recording.mp4"
```
*Response returns `{"id": "<RECORDING_ID>", "server_filename": "<UUID>.mp4", "validation_status": "pending", ...}`*

### Step 4: Submit Analysis Job
Processing runs asynchronously in the background:
```bash
curl -X POST "http://localhost:8000/api/v1/sessions/<SESSION_ID>/analysis" \
     -H "Content-Type: application/json" \
     -d '{
       "recording_id": "<RECORDING_ID>",
       "camera_view": "side",
       "pose_model": "yolo"
     }'
```
*Response returns `{"id": "<JOB_ID>", "status": "queued", ...}` (HTTP 202 Accepted)*

### Step 5: Poll Job Status
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/<JOB_ID>"
```
*Status transitions: `queued` → `running` (with stage updates and progress %) → `completed`.*

### Step 6: Retrieve Assessment & Generate Reports
```bash
# Retrieve generated biomechanical assessment
curl -X GET "http://localhost:8000/api/v1/sessions/<SESSION_ID>/assessment"

# Generate Individual Report (plain-language markdown)
curl -X POST "http://localhost:8000/api/v1/sessions/<SESSION_ID>/reports" \
     -H "Content-Type: application/json" \
     -d '{"report_type": "individual"}'

# Generate Professional Report (clinical-grade tabular report)
curl -X POST "http://localhost:8000/api/v1/sessions/<SESSION_ID>/reports" \
     -H "Content-Type: application/json" \
     -d '{"report_type": "professional"}'

# Download Report Markdown file
curl -X GET "http://localhost:8000/api/v1/reports/<REPORT_ID>/download" --output report.md
```

### Step 7: Compare Historical Sessions & Longitudinal Progress
```bash
# Get progress history for a subject
curl -X GET "http://localhost:8000/api/v1/subjects/<SUBJECT_ID>/progress"

# Check comparability between two sessions
curl -X POST "http://localhost:8000/api/v1/subjects/<SUBJECT_ID>/compare-sessions" \
     -H "Content-Type: application/json" \
     -d '{"session_id_1": "<SESSION_1>", "session_id_2": "<SESSION_2>"}'
```

---

## Testing

The project contains automated unit, integration, and regression tests for all milestones.

Run the test suite:
```bash
pytest tests/ -v
```

### Test Breakdown
- `tests/test_milestone1_npz.py`: Motion capture dataset discovery, schema validator, trial index generation.
- `tests/test_milestone2_features.py`: Biomechanical feature extraction, 101-point cycle curves, bilateral symmetry, reference distributions.
- `tests/test_milestone3_video.py`: Video validation, pose estimators (synthetic/YOLOv8, CPU/CUDA), viewpoint classification, event detection, cycle segmentation.
- `tests/test_milestone4_validation.py`: Compatibility mapping, event timing metrics, Bland-Altman agreement, bootstrap confidence intervals, pointwise curve comparison.
- `tests/test_milestone5_assessment.py`: Biomechanical rule evaluation, confidence gating, view gating, bilateral analysis without verified mapping, uncertainty propagation.
- `tests/test_milestone5_progress.py`: Quality-controlled baseline construction, version preservation, comparability decision matrix, linear trend analyzer.
- `tests/test_milestone5_reporting.py`: Individual and professional report generation, limitation disclaimer verification, renderer output.
- `tests/test_milestone6_api.py`: Subject and session CRUD, upload endpoints, analysis submission, report generation, 404/422 validation.
- `tests/test_milestone6_database.py`: SQLAlchemy database models, foreign-key integrity, soft deletion.
- `tests/test_milestone6_uploads.py`: Path-traversal resistance, file extension whitelist, size limit enforcement, SHA-256 calculation.
- `tests/test_milestone6_jobs.py`: Asynchronous job execution, worker state transitions, stage progress tracking.
- `tests/test_milestone6_permissions.py`: User roles (`individual`, `professional`, `administrator`), audit deletion logging.
- `tests/test_milestone6_integration.py`: End-to-end integration workflow from subject creation to report retrieval.

All 74 tests pass deterministically without requiring external network calls.

---

## License & Provenance
Developed for academic and biomedical research in human movement analysis.
All analysis pipelines preserve software version, pose estimation model hashes, configuration version, and date-time provenance for scientific reproducibility.
