"""Offline ML utilities for governed, reproducible BancoCloud experiments.

Nothing in this package participates in transaction authorization. Promotion to
online scoring requires a separate architecture decision and evidence gate.
"""

from .dataset import FEATURE_NAMES, FORBIDDEN_INPUTS, build_temporal_matrix

__all__ = ["FEATURE_NAMES", "FORBIDDEN_INPUTS", "build_temporal_matrix"]
