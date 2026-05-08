"""
Centralized environment loader for the backend.
Always loads from the root Attendance/.env (two levels up from this file).
"""
import pathlib
from dotenv import load_dotenv

# This file sits at: Attendance/backend/env_loader.py
# Root .env sits at: Attendance/.env → go 2 levels up
ROOT_ENV = pathlib.Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=ROOT_ENV, override=True)
