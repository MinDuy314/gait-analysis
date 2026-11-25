# Gait Analysis Frontend

Desktop-first, accessible web application for quantitative biomechanical gait analysis powered by YOLO pose estimation and computer vision.

## Features

- **Multi-Role & Organization Support:** Dedicated workflows for Patients (Individual) and Clinicians/Researchers (Professional & Administrator) with RBAC domain boundaries.
- **Complete End-to-End Workflow:**
  1. Organization / Account Onboarding (`/login`, `/register`)
  2. Subject & Patient Management (`/subjects`, `/subjects/[id]`)
  3. Experimental Session Setup (`/subjects/[id]/sessions/new`) with expandable biomechanical parameters.
  4. Video Upload (`/sessions/[id]/upload`) with drag & drop, 200MB limit check, and progress indicator.
  5. Camera View Confirmation (`/sessions/[id]/confirm-view`) for Frontal vs. Sagittal (Side) kinematics.
  6. Real-Time Analysis Progress (`/sessions/[id]/analysis`) with asynchronous job polling and pipeline stages.
  7. Dual-Audience Results (`/sessions/[id]/results`):
     - Large Native Video Player streaming annotated MP4 skeleton overlays (`COCO 17` keypoints).
     - Biomechanical gait metrics (cadence, stride timing, symmetry).
     - Audience toggle: Plain-language Patient summary vs. In-depth Clinician breakdown.
     - Scientific & medical disclaimer.
  8. Structured Reports (`/sessions/[id]/reports`): Generate and download Patient or Professional Markdown reports.
  9. Longitudinal Progress (`/progress`): Track gait stability across therapy cycles.
- **Bilingual Localization:** Seamless switching between Vietnamese (`vi`) and English (`en`).

## Tech Stack

- **Framework:** Next.js 16 (App Router) + TypeScript
- **Styling:** Tailwind CSS v4 + Lucide Icons
- **State & Data Fetching:** TanStack React Query + Axios
- **File Handling:** react-dropzone
- **Internationalization:** i18next + react-i18next

## Getting Started

### Prerequisites

- Node.js 18+ (tested on Node.js 26)
- Running Gait Analysis FastAPI Backend on `http://127.0.0.1:8000`

### Installation

```bash
cd frontend
npm install
```

### Environment Configuration

Create `.env.local` inside `frontend/`:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

### Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Production Build

```bash
npm run build
npm run start
```
