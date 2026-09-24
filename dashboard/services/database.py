"""
services/database.py -- single shared connection + query helper.

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


@st.cache_resource
def get_connection():
    # check_same_thread=False is safe here because this app only ever
    # reads from the database -- it never writes -- so there's no risk
    # of concurrent write conflicts across Streamlit's internal threads.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    # Foreign keys are OFF by default in SQLite even when a schema
    # declares them -- each connection has to opt in explicitly. This
    # connection is read-only in practice, but enabling this is what
    # makes the schema's declared relationships actually enforced rather
    # than just documentation, and it's the same pragma the write-side
    # pipeline scripts now set too (see scripts/).
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@st.cache_data
def run_query(sql, params=()):
    conn = get_connection()
    return pd.read_sql_query(sql, conn, params=params)
