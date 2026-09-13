"""Lab Phase 1 -- Locking Behavior.

This suite is run against the ORIGINAL, unmodified
legacy_enrollment_processor.py before any refactoring happens. Per the
Golden Rule ("No tests. No refactoring."), every test here must pass on
the legacy code first. Only then is the same golden data used to verify
the refactored code in test_refactored_characterization.py.

We do not import the legacy module directly (its logic is tangled
together with module-level side effects like DROP TABLE / DB writes),
so it is run as a real subprocess against a temp working directory --
exactly how a human would run "python legacy_enrollment_processor.py"
during a characterization pass.
"""

import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from golden_results import EXPECTED_FAIL_COUNT, EXPECTED_RESULTS, EXPECTED_SUCCESS_COUNT

REPO_ROOT = Path(__file__).resolve().parent.parent
LEGACY_SCRIPT = REPO_ROOT / "original" / "legacy_enrollment_processor.py"
SOURCE_CSV = REPO_ROOT / "original" / "students.csv"


def run_legacy(tmp_path: Path) -> Path:
    """Copies the legacy script + CSV into an isolated tmp dir and runs it there."""
    work_dir = tmp_path / "legacy_run"
    work_dir.mkdir()
    shutil.copy(LEGACY_SCRIPT, work_dir / "legacy_enrollment_processor.py")
    shutil.copy(SOURCE_CSV, work_dir / "students.csv")

    result = subprocess.run(
        [sys.executable, "legacy_enrollment_processor.py"],
        cwd=work_dir,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, "Legacy script crashed:\n" + result.stderr
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


def test_legacy_produces_expected_number_of_rows(tmp_path):
    work_dir = run_legacy(tmp_path)
    rows = read_db_rows(work_dir / "enrollment.db")
    assert len(rows) == len(EXPECTED_RESULTS)


def test_legacy_matches_golden_results_exactly(tmp_path):
    work_dir = run_legacy(tmp_path)
    rows = read_db_rows(work_dir / "enrollment.db")
    assert rows == EXPECTED_RESULTS


def test_legacy_html_report_has_expected_counts(tmp_path):
    work_dir = run_legacy(tmp_path)
    html = (work_dir / "report.html").read_text(encoding="utf-8")
    assert "Successful: {}".format(EXPECTED_SUCCESS_COUNT) in html
    assert "Failed: {}".format(EXPECTED_FAIL_COUNT) in html


def test_legacy_prints_summary_counts(tmp_path):
    work_dir = run_legacy(tmp_path)
    # re-run and capture stdout for the summary lines specifically
    result = subprocess.run(
        [sys.executable, "legacy_enrollment_processor.py"],
        cwd=work_dir,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "Processed {} enrollment requests.".format(len(EXPECTED_RESULTS)) in result.stdout
    assert "{} emails simulated.".format(len(EXPECTED_RESULTS)) in result.stdout


def test_legacy_skips_rows_with_missing_student_id(tmp_path):
    """The 'Ghost Student' row in students.csv has no student_id and must
    never appear in the output -- this is a documented quirk (not a bug
    we're fixing), and the refactor must preserve it bug-for-bug."""
    work_dir = run_legacy(tmp_path)
    rows = read_db_rows(work_dir / "enrollment.db")
    names_in_db = {r[0] for r in rows}
    assert "" not in names_in_db
    # "Ghost Student" was tied to a blank student_id and a course_code of
    # CS101; make sure no row with that exact combination snuck in twice
    # for an unrelated student.
    ghost_like_rows = [r for r in rows if r[1] == "CS101" and r[0] not in ("S008",)]
    assert ghost_like_rows == []
