"""Feature interpretation utilities and rule-based evaluation."""

from typing import Any, Dict, List, Optional
from src.assessment.assessment_schema import FeatureInterpretation, AssessmentStatus
from src.assessment.biomechanical_rules import BiomechanicalRule, build_default_rules


class FeatureInterpreter:
    """Interprets raw and processed gait features using configurable rules."""

    def __init__(self, rules: Optional[List[BiomechanicalRule]] = None):
        self.rules = rules or build_default_rules()

    def interpret_features(
        self,
        features: Dict[str, Any],
        camera_view: str,
        confidences: Optional[Dict[str, float]] = None,
    ) -> List[FeatureInterpretation]:
        confidences = confidences or {}
        interpretations: List[FeatureInterpretation] = []
        for rule in self.rules:
            result = rule.evaluate(features, camera_view, confidences)
            if result is not None:
                interpretations.append(result)
        return interpretations
