"""Domain layer: plain data structures with no I/O, no SQL, no HTML.

These are the "nouns" of the enrollment business: a request coming in,
a course as defined by the catalog, and the decision produced by the
business rules.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Course:
    code: str
    credits: int
    prerequisites: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class EnrollmentRequest:
    student_id: str
    name: str
    email: str
    gpa: float
    completed_courses: List[str]
    course_code: str
    override_prereq: bool


@dataclass(frozen=True)
class EnrollmentDecision:
    status: str  # "SUCCESS" or "FAILED"
    reason: str
    credits_applied: int = 0

    @property
    def is_success(self) -> bool:
        return self.status == "SUCCESS"
