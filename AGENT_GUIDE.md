# Agent Development & Verification Guide

This document serves as the permanent development, execution, and verification guide for the Gait Analysis repository. All agents and developers working on this codebase must adhere strictly to these rules.

---

## 1. Project Overview & Architecture

### Repository Structure
- **Root Directory**: `C:\Users\nduym\Documents\Gait-analysis`
- **Backend (`src/`)**: Python / FastAPI / SQLAlchemy / Ultralytics YOLO / OpenCV / PyTorch
  - `src/api/`: FastAPI routers (`subjects.py`, `sessions.py`, `uploads.py`, `analysis.py`, `jobs.py`, `assessments.py`, `reports.py`, `progress.py`), dependencies, authentication & security.
  - `src/assessment/`: Biomechanical assessment engine, rules, clinical interpretation, and domain groupings (Temporal, Spatial, Kinematic, Symmetry, Postural).
  - `src/database/`: SQLite database setup (`database.py`), declarative SQLAlchemy ORM models (`models.py`), and repositories (`repositories.py`).
  - `src/jobs/`: Thread-pool job manager (`job_manager.py`), job lifecycle status schemas (`job_schema.py`), retry handling (`retry_manager.py`), and end-to-end task execution (`task_registry.py`).
  - `src/pose_estimation/`: Pose estimator adapters (`yolo_estimator.py`, `synthetic_estimator.py`), factory, and common landmark schema (`landmark_schema.py`).
  - `src/video/`: Video validation, OpenCV frame extraction (`frame_extractor.py`), metadata extraction, and full processing pipeline runner (`video_pipeline_runner.py`).
  - `src/gait_events/`: Gait event detection (initial contact, toe-off) and cycle segmentation.
  - `src/feature_extraction/`: Biomechanical temporal, spatial, and kinematic parameter calculations.
  - `src/reporting/`: Individual patient and professional clinical PDF/HTML report generators.
  - `src/visualization/`: Video skeleton overlay annotation and MP4 generation (`video_annotator.py`).
- **Frontend (`frontend/`)**: Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS, Lucide icons
  - `frontend/src/app/`: App router routes (e.g. `/sessions/[id]/results`, `/sessions/[id]/analysis`, `/sessions/[id]/upload`, `/sessions/[id]/confirm-view`, `/sessions/[id]/reports`, `/progress`, `/subjects`, `/login`).
  - `frontend/src/lib/`: Typed API client (`api.ts`, `api-client.ts`) utilizing Axios with JWT Bearer interception.
  - `frontend/src/types/`: TypeScript definitions (`api.ts`) mirroring FastAPI schemas.
  - `frontend/src/context/`: Auth context (`AuthContext.tsx`) and bilingual English/Vietnamese language context (`LanguageContext.tsx`).
- **Tests (`tests/`)**: Pytest test suite covering API endpoints, database operations, security/RBAC, pipeline jobs, video processing, gait features, and reporting.

---

## 2. Environments & Execution Commands

### Backend Environment
- **Python Executable**: `"C:\Users\nduym\miniforge3\envs\yolo\python.exe"` (Conda `yolo` environment with PyTorch, Ultralytics, OpenCV, FastAPI, Pandas).
- **Environment Variable**: `PYTHONPATH="C:\Users\nduym\Documents\Gait-analysis"` must always be set when executing commands.
- **Starting Backend**:
  - Script: Double-click or run `start_backend.bat` or `start_backend.ps1` from the repo root.
  - Direct Command:
    ```powershell
    $env:PYTHONPATH="C:\Users\nduym\Documents\Gait-analysis"
    & "C:\Users\nduym\miniforge3\envs\yolo\python.exe" -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
    ```

### Frontend Environment
- **Node.js runtime**: Node v20+ with npm.
- **PowerShell Execution Policy Note**: On Windows where script execution (`.ps1`) is restricted, invoke npm via `node` directly or via `cmd /c`:
  - Dev Server: `cd frontend; node "C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js" run dev` (runs on `http://localhost:3000`).
  - Production Build: `cd frontend; node "C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js" run build`
- **Production Deployment**: Frontend is deployed on Vercel at `https://gait-analysis-abc-790d.vercel.app` and auto-deploys from GitHub `MinDuy314/gait-analysis` (`main` branch).

### Backend Test Execution
- Run specific test file:
  ```powershell
  $env:PYTHONPATH="C:\Users\nduym\Documents\Gait-analysis"; & "C:\Users\nduym\miniforge3\envs\yolo\python.exe" -m pytest tests/<test_file>.py -v
  ```
- Run targeted tests:
  ```powershell
  $env:PYTHONPATH="C:\Users\nduym\Documents\Gait-analysis"; & "C:\Users\nduym\miniforge3\envs\yolo\python.exe" -m pytest tests/<test_file>.py -k "<test_name>" -v
  ```

---

## 3. Verification Rules

1. **Inspect Before Modifying**: Always read and understand the existing implementation and test setup before making code changes. Never assume schemas or function signatures.
2. **Smallest Relevant Test Set**: Identify and execute only the minimal set of tests directly related to the changed code.
3. **Tiered Verification**:
   - First: Run targeted tests for the changed module.
   - Second: Run regression tests only when interfaces, dependencies, or database schemas have been touched.
4. **Targeted Frontend Builds**: Run `npm run build` only when frontend code (`frontend/src/`) or shared API contracts change. Do not run it for purely backend edits.
5. **Never Loop or Re-run Repeatedly**: Never run the same failing command repeatedly without diagnosing the root cause and modifying the offending code.
6. **No Phantom Passes**: Never claim a test or build succeeded unless the actual terminal output confirms zero errors and passing status.
7. **Cache & Reuse**: Do not re-run tests that previously passed if the tested code was not modified.

---

## 4. Milestone Workflow

For every milestone or prompt request:
1. **Inspect**: Inspect the relevant backend/frontend files and identify existing patterns.
2. **Focused Implementation**: Make *only* the specific changes required for that milestone. Avoid out-of-scope refactoring or aesthetic changes.
3. **Verify**:
   - Run the smallest relevant backend pytest suite.
   - Run the frontend build if frontend files were touched.
4. **Fix Genuine Failures**: If a test or build fails, fix the underlying bug and re-run only the affected check.
5. **Report Concisely**: Report:
   - Specific files modified.
   - Exact test/build commands run and their outcomes.
   - Any remaining limitations or next steps.
6. **Stop & Await**: Stop after completing the milestone and wait for the user's approval or next prompt.

---

## 5. Token & Execution Efficiency

- **No Redundant Scanning**: Do not re-scan the entire directory tree when relevant file paths are already known.
- **Log Summarization**: Truncate or summarize passing pytest runs; display only relevant failure traces.
- **Batch Independent Operations**: Execute independent file reads, tool calls, or status checks in parallel where appropriate.
- **Preserve Existing Architecture**: Maintain FastAPI router patterns, SQLite idempotent migrations, bilingual English/Vietnamese UI text, and JWT-authenticated video streaming. Never introduce fake clinical diagnoses or synthetic data substitutes for clinical measurements.

---

## 6. Completion Criteria

A milestone is considered complete **only** when:
- The requested feature/fix is fully implemented.
- Targeted verification tests have run and passed with zero errors.
- Frontend production build (`next build`) compiles cleanly (if frontend was modified).
- Remaining limitations or future dependencies are clearly documented in the response.

---

## 7. Guide Maintenance

Update this guide only when directory structures, runtime environments, build commands, or architectural patterns materially change. Do not rewrite this file during routine feature or bugfix milestones.
