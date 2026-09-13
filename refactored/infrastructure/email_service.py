"""Infrastructure layer: notification delivery.

Currently "sends" email by printing and logging in memory, exactly
like the legacy script. If a real email provider is added later,
only this file needs to change.
"""

from typing import Dict, List

from domain.models import EnrollmentDecision, EnrollmentRequest


class EmailNotifier:
    def __init__(self):
        self._log: List[Dict[str, str]] = []

    def notify(self, request: EnrollmentRequest, decision: EnrollmentDecision) -> None:
        subject = "Enrollment {}: {}".format(decision.status, request.course_code)
        body = "Hi {},\n\n{}\n\nReason: {}\n".format(
            request.name, subject, decision.reason
        )
        self._log.append({"to": request.email, "subject": subject, "body": body})
        print("[EMAIL SIMULATED] To: {} | Subject: {}".format(request.email, subject))

    @property
    def log(self) -> List[Dict[str, str]]:
        return self._log
