# Gait Analysis Backend MVP

A modular research and monitoring support backend for human gait analysis, combining:
1. **Biomechanical Reference Pipeline (NPZ)**: Processes laboratory motion-capture trials (Plug-in Gait 3D kinematics, kinetics, and ground reaction forces).
2. **Video-Based Gait Analysis Pipeline**: Extracts 2D/estimated pose landmarks, gait events, and view-specific biomechanical features from walking videos.

> **Disclaimer**: This is a research and monitoring support system, **not** a medical diagnostic tool.

## Directory Structure
- `data/raw/`: Original `npz`, `c3d`, and `txt` trial files (preserved read-only).
- `data/processed/`: Extracted trial features, normalized gait curves, and quality control reports.
- `data/video/`: Uploaded raw and processed video recordings.
- `analysis/`: Exploratory, biomechanical, statistical, and validation workflows.
- `src/`: Modular Python backend (`core`, `data_loader`, `preprocessing`, `feature_extraction`, `gait_analysis`, `visualization`, `validation`, etc.).
- `config/`: YAML pipeline and feature configurations.
- `metadata/`: Generated `trial_index.csv`, `subject_index.csv`, and `variable_dictionary.csv`.
- `tests/`: Automated `pytest` test suite.
