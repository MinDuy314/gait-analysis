"""Custom exceptions for the Gait Analysis Backend MVP."""


class GaitAnalysisError(Exception):
    """Base exception for all gait analysis backend errors."""


class ConfigurationError(GaitAnalysisError):
    """Raised when configuration files are missing or invalid."""


class DatasetDiscoveryError(GaitAnalysisError):
    """Raised when dataset discovery fails."""


class SchemaValidationError(GaitAnalysisError):
    """Raised when an NPZ or data file fails strict schema validation."""


class VideoAnnotationError(Exception):
    """Raised when annotated video generation fails.

    Intentionally NOT a subclass of GaitAnalysisError so annotation failures
    are distinguishable from pose-estimation and assessment failures.
    """
