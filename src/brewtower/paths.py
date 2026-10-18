"""Where the generator and the pipeline read and write. One place, so a folder move is a one-line change."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"      # daily source files as received, written by generate.py
GOLD = ROOT / "data" / "gold"    # star-schema CSVs Power BI imports
SQL = ROOT / "sql"               # staging, checks and marts, one statement per file
