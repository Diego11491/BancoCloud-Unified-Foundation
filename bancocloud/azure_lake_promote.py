"""Promote the Azure Bronze snapshot to Silver, Gold and Quarantine."""

from .azure_medallion import run_promotion


if __name__ == "__main__":
    run_promotion()
