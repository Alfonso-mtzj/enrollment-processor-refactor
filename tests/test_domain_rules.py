"""Unit tests for the extracted domain layer.

These are only possible *because* the refactor succeeded: the legacy
version has no importable, side-effect-free version of these rules to
test in isolation (they're welded to sqlite3 and module-level globals).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "refactored"))

from domain.catalog import CourseCatalog
from domain.enrollment_rules import (
    CreditLedger,
    EnrollmentPolicy,
    check_prerequisites,
    get_credit_limit,
)
from domain.models import EnrollmentRequest


# --- get_credit_limit boundary tests ---

def test_credit_limit_below_honors_threshold_is_standard():
    assert get_credit_limit(3.49) == 18


def test_credit_limit_at_exact_honors_threshold_is_honors():
    # boundary is inclusive: gpa >= 3.5, matching the legacy script exactly
    assert get_credit_limit(3.5) == 21


def test_credit_limit_above_honors_threshold_is_honors():
    assert get_credit_limit(4.0) == 21


def test_credit_limit_zero_gpa_is_standard():
    assert get_credit_limit(0.0) == 18


# --- check_prerequisites tests ---

def test_prerequisites_satisfied_no_override_needed():
    ok, reason = check_prerequisites(["CS101"], ["CS101"], override=False)
    assert ok is True
    assert reason == ""


def test_prerequisites_missing_without_override_fails():
    ok, reason = check_prerequisites([], ["CS101"], override=False)
    assert ok is False
    assert reason == "Missing prerequisites: CS101"


def test_prerequisites_missing_with_override_succeeds_with_warning():
    ok, reason = check_prerequisites([], ["CS101"], override=True)
    assert ok is True
    assert reason == "Prerequisite override applied for: CS101"


def test_prerequisites_no_requirements_always_passes():
    ok, reason = check_prerequisites([], [], override=False)
    assert ok is True
    assert reason == ""


# --- CourseCatalog tests ---

def test_catalog_returns_known_course():
    catalog = CourseCatalog()
    course = catalog.get("CS101")
    assert course is not None
    assert course.credits == 3
    assert course.prerequisites == []


def test_catalog_returns_none_for_unknown_course():
    catalog = CourseCatalog()
    assert catalog.get("BIO500") is None


# --- EnrollmentPolicy tests (the composed business rule) ---

def _make_request(**overrides):
    defaults = dict(
        student_id="S999",
        name="Test Student",
        email="test@example.com",
        gpa=3.0,
        completed_courses=[],
        course_code="CS101",
        override_prereq=False,
    )
    defaults.update(overrides)
    return EnrollmentRequest(**defaults)


def test_policy_rejects_unknown_course():
    policy = EnrollmentPolicy(catalog=CourseCatalog())
    decision = policy.evaluate(_make_request(course_code="BIO500"))
    assert decision.status == "FAILED"
    assert decision.reason == "Course does not exist: BIO500"


def test_policy_accepts_course_with_no_prerequisites():
    policy = EnrollmentPolicy(catalog=CourseCatalog())
    decision = policy.evaluate(_make_request(course_code="CS101"))
    assert decision.status == "SUCCESS"
    assert decision.reason == "Enrolled successfully"


def test_policy_enforces_credit_limit_across_multiple_calls():
    """Mirrors the legacy running_credit_totals global, but as an explicit,
    resettable object instead of module-level state."""
    ledger = CreditLedger()
    policy = EnrollmentPolicy(catalog=CourseCatalog(), ledger=ledger)

    # MATH110(4) + PHYS150(4, needs MATH110) + HIST101(3) + ENG100(3) + ART120(2) = 16
    for code, completed in [
        ("MATH110", []),
        ("PHYS150", ["MATH110"]),
        ("HIST101", ["MATH110"]),
        ("ENG100", ["MATH110"]),
        ("ART120", ["MATH110"]),
    ]:
        decision = policy.evaluate(
            _make_request(course_code=code, completed_courses=completed, gpa=3.1)
        )
        assert decision.status == "SUCCESS", (code, decision.reason)

    # one more 3-credit course pushes the student to 19 > 18 (standard limit)
    decision = policy.evaluate(
        _make_request(course_code="CS101", completed_courses=["MATH110"], gpa=3.1)
    )
    assert decision.status == "FAILED"
    assert decision.reason == "Credit limit exceeded (19 > 18)"


def test_policy_honors_student_gets_higher_limit():
    ledger = CreditLedger()
    policy = EnrollmentPolicy(catalog=CourseCatalog(), ledger=ledger)
    # same 19-credit load, but GPA 3.8 (honors) should still succeed since limit is 21
    for code, completed in [
        ("MATH110", []),
        ("PHYS150", ["MATH110"]),
        ("HIST101", ["MATH110"]),
        ("ENG100", ["MATH110"]),
        ("ART120", ["MATH110"]),
        ("CS101", ["MATH110"]),
    ]:
        decision = policy.evaluate(
            _make_request(course_code=code, completed_courses=completed, gpa=3.8)
        )
        assert decision.status == "SUCCESS", (code, decision.reason)


def test_policy_reports_override_reason_on_success():
    ledger = CreditLedger()
    policy = EnrollmentPolicy(catalog=CourseCatalog(), ledger=ledger)
    decision = policy.evaluate(
        _make_request(course_code="CS201", completed_courses=[], override_prereq=True)
    )
    assert decision.status == "SUCCESS"
    assert decision.reason == "Prerequisite override applied for: CS101"
