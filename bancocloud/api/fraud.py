"""Compatibility wrapper: fraud API remains the existing source-of-truth implementation."""
from bancocloud.service import fraud_app as app

__all__ = ["app"]
