"""Run the independent Event Hubs → ADLS Bronze consumer."""

from .azure_medallion import run_bronze


if __name__ == "__main__":
    run_bronze()
