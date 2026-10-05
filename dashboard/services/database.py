"""
services/database.py: single shared connection + query helper.

Every page in the dashboard reads from the same read-only SQLite
database. Centralizing the connection and query caching here (instead of
duplicating it in every page module) means there's exactly one place
that knows the database path and exactly one cached connection, which
keeps Streamlit's caching behavior predictable across pages.
"""

import os
import sqlite3

import pandas as pd
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .../AlignED
DB_PATH = os.path.join(BASE_DIR, "database", "aligned.db")


def _db_version():
    """Changes whenever the database file is replaced (e.g. a redeploy
    that ships a regenerated aligned.db). Used as a cache key below.
    Without it, a long-running app keeps serving results from the old
    file: the cached connection still points at the replaced file, and
    cached query results never expire."""
    stat = os.stat(DB_PATH)
    return f"{stat.st_mtime_ns}-{stat.st_size}"


@st.cache_resource
def _connect(version):
    # check_same_thread=False is safe here because this app only ever
    # reads from the database, it never writes, so there's no risk
    # of concurrent write conflicts across Streamlit's internal threads.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    # Foreign keys are OFF by default in SQLite even when a schema
    # declares them; each connection has to opt in explicitly.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_connection():
    return _connect(_db_version())


@st.cache_data
def _cached_query(sql, params, version):
    return pd.read_sql_query(sql, _connect(version), params=params)


def run_query(sql, params=()):
    return _cached_query(sql, params, _db_version())
