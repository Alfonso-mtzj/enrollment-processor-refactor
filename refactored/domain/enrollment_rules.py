"""Domain layer: the actual business rules.

Everything here is pure logic: no database, no file I/O, no HTML.
It can be unit-tested with plain Python objects and no fixtures.
"""

from typing import List, Tuple

from .catalog import CourseCatalog
from .models import EnrollmentDecision, EnrollmentRequest

STANDARD_CREDIT_LIMIT = 18
HONORS_CREDIT_LIMIT = 21
HONORS_GPA_THRESHOLD = 3.5


def get_credit_limit(gpa: float) -> int:
    if gpa >= HONORS_GPA_THRESHOLD:
        return HONORS_CREDIT_LIMIT
    return STANDARD_CREDIT_LIMIT


def check_prerequisites(
    completed_courses: List[str], prerequisites: List[str], override: bool
) -> Tuple[bool, str]:
    missing = [p for p in prerequisites if p not in completed_courses]
    if missing and not override:
        return False, "Missing prerequisites: " + ", ".join(missing)
    if missing and override:
        return True, "Prerequisite override applied for: " + ", ".join(missing)
    return True, ""


class CreditLedger:
    """Tracks how many credits each student has committed to during
    this processing run. Kept as a small, explicit, injectable class
    instead of a module-level global (unlike the legacy script)."""

    def __init__(self):
        self._totals = {}

    def total_for(self, student_id: str) -> int:
        return self._totals.get(student_id, 0)

    def add(self, student_id: str, credits: int) -> None:
        self._totals[student_id] = self.total_for(student_id) + credits


class EnrollmentPolicy:
    """Evaluates a single enrollment request against the business
    rules: course existence, prerequisites, and credit limits."""

    def __init__(self, catalog: CourseCatalog, ledger: CreditLedger = None):
        self._catalog = catalog
        self._ledger = ledger if ledger is not None else CreditLedger()

    def evaluate(self, request: EnrollmentRequest) -> EnrollmentDecision:
        course = self._catalog.get(request.course_code)
        if course is None:
            return EnrollmentDecision(
                status="FAILED",
                reason="Course does not exist: " + request.course_code,
            )

        prereq_ok, prereq_reason = check_prerequisites(
            request.completed_courses, course.prerequisites, request.override_prereq
        )
        if not prereq_ok:
            return EnrollmentDecision(status="FAILED", reason=prereq_reason)

        limit = get_credit_limit(request.gpa)
        current_total = self._ledger.total_for(request.student_id)
        new_total = current_total + course.credits

        if new_total > limit:
            return EnrollmentDecision(
                status="FAILED",
                reason="Credit limit exceeded ({} > {})".format(new_total, limit),
            )

        self._ledger.add(request.student_id, course.credits)
        reason = prereq_reason if prereq_reason else "Enrolled successfully"
        return EnrollmentDecision(
            status="SUCCESS", reason=reason, credits_applied=course.credits
        )
