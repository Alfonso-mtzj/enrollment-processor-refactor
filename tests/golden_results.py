"""Single source of truth for expected enrollment outcomes.

This is the "locked behavior" from Lab Phase 1: derived by running the
original, unmodified legacy_enrollment_processor.py against students.csv
and recording exactly what it produced. Both the legacy characterization
suite and the refactored characterization suite are checked against this
same list, so a pass on both proves bug-for-bug behavioral equivalence.

Tuple shape: (student_id, course_code, status, reason)
"""

EXPECTED_RESULTS = [
    ("S001", "CS201", "SUCCESS", "Enrolled successfully"),
    ("S001", "MATH210", "SUCCESS", "Enrolled successfully"),
    ("S001", "PHYS150", "SUCCESS", "Enrolled successfully"),
    ("S001", "PHYS250", "FAILED", "Missing prerequisites: PHYS150, MATH210"),
    ("S002", "CS301", "SUCCESS", "Prerequisite override applied for: CS201"),
    ("S002", "ENG100", "SUCCESS", "Enrolled successfully"),
    ("S002", "HIST101", "SUCCESS", "Enrolled successfully"),
    ("S002", "ART120", "SUCCESS", "Enrolled successfully"),
    ("S002", "MATH110", "SUCCESS", "Enrolled successfully"),
    ("S003", "CS201", "FAILED", "Missing prerequisites: CS101"),
    ("S004", "ENG100", "SUCCESS", "Enrolled successfully"),
    ("S005", "PHYS250", "FAILED", "Missing prerequisites: MATH210"),
    ("S006", "BIO500", "FAILED", "Course does not exist: BIO500"),
    ("S007", "CS301", "SUCCESS", "Enrolled successfully"),
    ("S008", "MATH110", "SUCCESS", "Enrolled successfully"),
    ("S008", "PHYS150", "SUCCESS", "Prerequisite override applied for: MATH110"),
    ("S008", "HIST101", "SUCCESS", "Enrolled successfully"),
    ("S008", "ENG100", "SUCCESS", "Enrolled successfully"),
    ("S008", "ART120", "SUCCESS", "Enrolled successfully"),
    ("S008", "CS101", "FAILED", "Credit limit exceeded (19 > 18)"),
]

EXPECTED_SUCCESS_COUNT = sum(1 for r in EXPECTED_RESULTS if r[2] == "SUCCESS")
EXPECTED_FAIL_COUNT = sum(1 for r in EXPECTED_RESULTS if r[2] == "FAILED")
EXPECTED_ROW_COUNT = len(EXPECTED_RESULTS)
