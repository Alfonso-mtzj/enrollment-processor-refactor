"""Domain layer: the course catalog.

This is business reference data (what courses exist, how many credits
they carry, and what they require) -- not infrastructure. It has no
knowledge of CSV files, databases, or HTML.
"""

from typing import Dict, Optional

from .models import Course


class CourseCatalog:
    def __init__(self, courses: Optional[Dict[str, Course]] = None):
        self._courses = courses if courses is not None else self._default_courses()

    @staticmethod
    def _default_courses() -> Dict[str, Course]:
        raw = {
            "CS101": (3, []),
            "CS201": (3, ["CS101"]),
            "CS301": (4, ["CS201"]),
            "MATH110": (4, []),
            "MATH210": (4, ["MATH110"]),
            "ENG100": (3, []),
            "PHYS150": (4, ["MATH110"]),
            "PHYS250": (4, ["PHYS150", "MATH210"]),
            "HIST101": (3, []),
            "ART120": (2, []),
        }
        return {
            code: Course(code=code, credits=credits, prerequisites=prereqs)
            for code, (credits, prereqs) in raw.items()
        }

    def get(self, course_code: str) -> Optional[Course]:
        return self._courses.get(course_code)
