"""Lab Phase 2 -- Verify the refactor preserved behavior.

Same golden data as test_legacy_characterization.py, but run against
refactored/main.py instead. If every test here passes using the exact
same EXPECTED_RESULTS the legacy suite locked in, the refactor is proven
behavior-preserving -- this is the safety net referenced on the
"Locking the Behavior" slide.
"""

import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from golden_results import EXPECTED_FAIL_COUNT, EXPECTED_RESULTS, EXPECTED_SUCCESS_COUNT

REPO_ROOT = Path(__file__).resolve().parent.parent
REFACTORED_DIR = REPO_ROOT / "refactored"
SOURCE_CSV = REPO_ROOT / "original" / "students.csv"


def run_refactored(tmp_path: Path) -> Path:
    """Copies the refactored package + CSV into an isolated tmp dir and runs main.py there."""
    work_dir = tmp_path / "refactored_run"
    shutil.copytree(
        REFACTORED_DIR,
        work_dir,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "enrollment.db", "report.html"),
    )
    shutil.copy(SOURCE_CSV, work_dir / "students.csv")

    env = dict(os.environ)
    env["PYTHONPATH"] = str(work_dir)

    result = subprocess.run(
        [sys.executable, "main.py"],
        cwd=work_dir,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, "Refactored main.py crashed:\n" + result.stderr
    return work_dir


def read_db_rows(db_path: Path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT student_id, course_code, status, reason FROM enrollments ORDER BY id"
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def test_refactored_produces_expected_number_of_rows(tmp_path):
    work_dir = run_refactored(tmp_path)
    rows = read_db_rows(work_dir / "enrollment.db")
    assert len(rows) == len(EXPECTED_RESULTS)


def test_refactored_matches_golden_results_exactly(tmp_path):
    """This is the core proof: identical (student_id, course, status, reason)
    tuples, in identical order, to what the untouched legacy script produced."""
    work_dir = run_refactored(tmp_path)
    rows = read_db_rows(work_dir / "enrollment.db")
    assert rows == EXPECTED_RESULTS


def test_refactored_html_report_has_expected_counts(tmp_path):
    work_dir = run_refactored(tmp_path)
    html = (work_dir / "report.html").read_text(encoding="utf-8")
    assert "Successful: {}".format(EXPECTED_SUCCESS_COUNT) in html
    assert "Failed: {}".format(EXPECTED_FAIL_COUNT) in html


def test_refactored_prints_summary_counts(tmp_path):
    work_dir = run_refactored(tmp_path)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(work_dir)
    result = subprocess.run(
        [sys.executable, "main.py"],
        cwd=work_dir,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        stdin=subprocess.DEVNULL,

    )
    assert "Processed {} enrollment requests.".format(len(EXPECTED_RESULTS)) in result.stdout
    assert "{} emails simulated.".format(len(EXPECTED_RESULTS)) in result.stdout


def test_refactored_skips_rows_with_missing_student_id(tmp_path):
    work_dir = run_refactored(tmp_path)
    rows = read_db_rows(work_dir / "enrollment.db")
    names_in_db = {r[0] for r in rows}
    assert "" not in names_in_db
