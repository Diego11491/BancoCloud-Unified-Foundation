"""Database connection factory for LOCAL FIRST; cloud SQL is not configured."""
import os


def connect():
    import psycopg
    return psycopg.connect(os.environ["DATABASE_URL"])
