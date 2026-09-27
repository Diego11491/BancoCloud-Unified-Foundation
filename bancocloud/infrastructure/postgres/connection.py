"""Reuses the repository's existing LOCAL FIRST connection factory."""
from bancocloud.db import connect

__all__ = ["connect"]
