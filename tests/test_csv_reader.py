"""Unit tests for the extracted CSV-parsing infrastructure.

Locks in every quirk of the legacy cleanup logic: messy headers,
whitespace, GPA parse fallback, pipe-delimited completed courses, and
the specific set of strings that count as an override flag.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "refactored"))

from infrastructure.csv_reader import EnrollmentCsvReader

MESSY_CSV = """ Student_ID , Name,EMAIL,GPA,Completed_Courses ,course_code, override_prereq
S100,Test One,  TEST.ONE@Example.com ,3.7,cs101|math110,cs201,YES
S101,Test Two,test.two@example.com,not-a-number,,eng100,
S102,Test Three,test.three@example.com,2.0,,hist101,TRUE
,Ghost,ghost@example.com,3.0,,cs101,
S103,Test Four,test.four@example.com,2.5,,art120,no
"""


def _write_csv(tmp_path, content=MESSY_CSV):
    path = tmp_path / "students.csv"
    path.write_text(content, encoding="utf-8")
    return path


def test_headers_are_normalized_despite_spacing_and_case(tmp_path):
    path = _write_csv(tmp_path)
    requests = EnrollmentCsvReader().read(str(path))
    assert len(requests) == 4  # the ghost row (no student_id) is dropped


def test_row_with_missing_student_id_is_skipped(tmp_path):
    path = _write_csv(tmp_path)
    requests = EnrollmentCsvReader().read(str(path))
    ids = [r.student_id for r in requests]
    assert "" not in ids
    assert len(ids) == len(set(ids))  # no accidental blank-id duplicates


def test_email_is_trimmed_and_lowercased(tmp_path):
    path = _write_csv(tmp_path)
    requests = EnrollmentCsvReader().read(str(path))
    s100 = next(r for r in requests if r.student_id == "S100")
    assert s100.email == "test.one@example.com"


def test_course_code_is_uppercased(tmp_path):
    path = _write_csv(tmp_path)
    requests = EnrollmentCsvReader().read(str(path))
    s100 = next(r for r in requests if r.student_id == "S100")
    assert s100.course_code == "CS201"


def test_completed_courses_split_on_pipe_and_uppercased(tmp_path):
    path = _write_csv(tmp_path)
    requests = EnrollmentCsvReader().read(str(path))
    s100 = next(r for r in requests if r.student_id == "S100")
    assert s100.completed_courses == ["CS101", "MATH110"]


def test_invalid_gpa_falls_back_to_zero(tmp_path):
    path = _write_csv(tmp_path)
    requests = EnrollmentCsvReader().read(str(path))
    s101 = next(r for r in requests if r.student_id == "S101")
    assert s101.gpa == 0.0


def test_override_flag_recognizes_yes_true_variants(tmp_path):
    path = _write_csv(tmp_path)
    requests = EnrollmentCsvReader().read(str(path))
    by_id = {r.student_id: r for r in requests}
    assert by_id["S100"].override_prereq is True  # "YES"
    assert by_id["S102"].override_prereq is True  # "TRUE"


def test_override_flag_treats_no_and_blank_as_false(tmp_path):
    path = _write_csv(tmp_path)
    requests = EnrollmentCsvReader().read(str(path))
    by_id = {r.student_id: r for r in requests}
    assert by_id["S101"].override_prereq is False  # blank
    assert by_id["S103"].override_prereq is False  # "no"


def test_empty_completed_courses_becomes_empty_list(tmp_path):
    path = _write_csv(tmp_path)
    requests = EnrollmentCsvReader().read(str(path))
    s101 = next(r for r in requests if r.student_id == "S101")
    assert s101.completed_courses == []


def test_missing_name_defaults_to_unknown_student(tmp_path):
    csv_with_blank_name = (
        " Student_ID , Name,EMAIL,GPA,Completed_Courses ,course_code, override_prereq\n"
        "S200,,blank.name@example.com,3.0,,cs101,\n"
    )
    path = _write_csv(tmp_path, csv_with_blank_name)
    requests = EnrollmentCsvReader().read(str(path))
    assert requests[0].name == "Unknown Student"
