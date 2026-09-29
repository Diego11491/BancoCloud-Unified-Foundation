"""Compatibility exports for earlier LOCAL FIRST entrypoints.

New deployments should use ``bancocloud.api.core:app`` and
``bancocloud.api.fraud:app`` directly.
"""
from bancocloud.api.core import app as core_app
from bancocloud.api.fraud import app as fraud_app

__all__ = ["core_app", "fraud_app"]
