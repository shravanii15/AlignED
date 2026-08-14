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
    return sqlite3.connect(DB_PATH, check_same_thread=False)


@st.cache_data
def run_query(sql, params=()):
    conn = get_connection()
    return pd.read_sql_query(sql, conn, params=params)
