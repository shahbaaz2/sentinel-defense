"""Shared incident-status vocabulary so the correlation engine and the API never drift apart on
what counts as "still open" for merge/metrics purposes."""

INCIDENT_STATUSES = ("OPEN", "INVESTIGATING", "MONITORING", "RESOLVED", "DISMISSED")
TERMINAL_INCIDENT_STATUSES = ("RESOLVED", "DISMISSED")
INCIDENT_DISPOSITIONS = (
    "TRUE_POSITIVE",
    "BENIGN_TRUE_POSITIVE",
    "FALSE_POSITIVE",
    "TEST_SCENARIO",
    "UNDETERMINED",
)
