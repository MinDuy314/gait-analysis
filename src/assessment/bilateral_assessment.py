from typing import Any, Dict, List, Optional
from src.assessment.assessment_schema import BilateralResult


def assess_bilateral_features(
    bilateral_features: Dict[str, Any],
    side_mapping_verified: bool = False,
) -> List[BilateralResult]:
    results = []

    # Identify feature pairs: primary + _contra
    primary_keys = [
        k for k in bilateral_features
        if not k.endswith("_contra") and k + "_contra" in bilateral_features
    ]

    for feat in primary_keys:
        pval = bilateral_features.get(feat)
        cval = bilateral_features.get(feat + "_contra")

        if pval is None or cval is None:
            results.append(BilateralResult(
                feature_name=feat,
                primary_value=pval,
                contra_value=cval,
                limitations=["One or both sides unavailable."],
                interpretation="Bilateral comparison not possible \u2014 missing data.",
            ))
            continue

        abs_diff = abs(float(pval) - float(cval))

        # Symmetry index (careful: only for non-zero denominators and ratio-meaningful features)
        sym_idx = None
        avg = (abs(float(pval)) + abs(float(cval))) / 2
        if avg > 0.01:
            sym_idx = float(abs_diff / avg * 100)

        if not side_mapping_verified:
            interp = (
                f"Absolute difference between primary and contralateral limb: {abs_diff:.2f}. "
                "Note: 'primary' and 'contralateral' designations are not verified anatomical left/right mappings. "
                "A bilateral difference is not automatically evidence of pathology."
            )
            limitations = [
                "Side mapping (left/right) not verified \u2014 primary/contra labels used instead.",
                "A bilateral difference is not automatically evidence of pathology.",
            ]
        else:
            interp = (
                f"Absolute difference between sides: {abs_diff:.2f}."
                " Bilateral differences should be interpreted in clinical context."
            )
            limitations = ["Bilateral asymmetry is not automatically evidence of pathology."]

        results.append(BilateralResult(
            feature_name=feat,
            primary_value=float(pval),
            contra_value=float(cval),
            absolute_difference=abs_diff,
            symmetry_index=sym_idx,
            confidence=0.7 if side_mapping_verified else 0.4,
            side_mapping_verified=side_mapping_verified,
            interpretation=interp,
            limitations=limitations,
        ))

    return results
