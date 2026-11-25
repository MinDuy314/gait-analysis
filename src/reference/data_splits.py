"""Participant-independent data split generator with leakage verification."""

from pathlib import Path
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from src.core.config import AppConfig
from src.core.logging import get_logger

logger = get_logger(__name__)


def generate_participant_splits(cfg: Optional[AppConfig] = None) -> Path:
    """
    Create reproducible participant-independent train/val/test splits.
    All trials for a given participant are assigned to the same split.
    """
    cfg = cfg or AppConfig()
    trial_index_path = cfg.metadata_dir / "trial_index.csv"
    if not trial_index_path.exists():
        raise FileNotFoundError(f"Missing trial_index.csv at {trial_index_path}")

    trial_df = pd.read_csv(trial_index_path)
    usable_df = trial_df[trial_df["validation_status"] != "invalid"].copy()

    splits_cfg = cfg.dataset_cfg.get("dataset", {}).get("splits", {})
    seed = int(splits_cfg.get("random_seed", 42))
    props = splits_cfg.get("proportions", {"train": 0.64, "val": 0.18, "test": 0.18})
    dataset_version = str(cfg.dataset_cfg.get("dataset", {}).get("version", "29300888.v1"))

    participants = sorted(usable_df["participant_id"].unique().tolist())
    n_parts = len(participants)
    if n_parts < 3:
        raise ValueError(f"Need at least 3 participants for train/val/test split, found {n_parts}")

    rng = np.random.default_rng(seed)
    shuffled = list(participants)
    rng.shuffle(shuffled)

    n_val = max(1, int(round(n_parts * float(props.get("val", 0.18)))))
    n_test = max(1, int(round(n_parts * float(props.get("test", 0.18)))))
    n_train = n_parts - n_val - n_test
    if n_train < 1:
        raise ValueError("Invalid split proportions: train participant count < 1")

    assign_map: Dict[str, str] = {}
    for p in shuffled[:n_train]:
        assign_map[p] = "train"
    for p in shuffled[n_train : n_train + n_val]:
        assign_map[p] = "val"
    for p in shuffled[n_train + n_val :]:
        assign_map[p] = "test"

    # Leakage check: ensure disjoint participant sets
    train_p = {p for p, s in assign_map.items() if s == "train"}
    val_p = {p for p, s in assign_map.items() if s == "val"}
    test_p = {p for p, s in assign_map.items() if s == "test"}
    assert train_p.isdisjoint(val_p) and train_p.isdisjoint(test_p) and val_p.isdisjoint(test_p)

    rows: List[Dict] = []
    for p in participants:
        p_trials = usable_df[usable_df["participant_id"] == p]
        cond_counts = p_trials["condition"].value_counts().to_dict()
        rows.append(
            {
                "participant_id": p,
                "split": assign_map[p],
                "trial_count": int(len(p_trials)),
                "random_seed": seed,
                "dataset_version": dataset_version,
                "train_proportion_target": props.get("train"),
                "val_proportion_target": props.get("val"),
                "test_proportion_target": props.get("test"),
                "condition_distribution": ";".join(f"{k}:{v}" for k, v in sorted(cond_counts.items())),
            }
        )

    out_path = cfg.metadata_dir / "participant_splits.csv"
    pd.DataFrame(rows).to_csv(out_path, index=False)
    logger.info(
        "Generated participant-independent splits at %s (train=%d, val=%d, test=%d participants; seed=%d)",
        out_path,
        len(train_p),
        len(val_p),
        len(test_p),
        seed,
    )
    return out_path


if __name__ == "__main__":
    generate_participant_splits()
