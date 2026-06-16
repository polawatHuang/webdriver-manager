"""Pure parsing/dedup logic — no Playwright dependency, fully unit-testable."""
import re

from config import EMPLOYEE_ID_PATTERN

_LEADING_SEPARATORS = re.compile(r"^[\s\-:,]+")


def parse_employee(comment_text: str) -> tuple[str, str] | None:
    """Extract (employee_id, employee_name) from a raw comment body.

    Returns None when no 8-digit employee ID is present (e.g. "ร่วมกิจกรรมครับ").
    """
    if not comment_text:
        return None

    match = EMPLOYEE_ID_PATTERN.search(comment_text)
    if not match:
        return None

    employee_id = match.group()
    remainder = comment_text[: match.start()] + comment_text[match.end() :]
    employee_name = _LEADING_SEPARATORS.sub("", remainder).strip()
    return employee_id, employee_name


def dedupe_records(records: list[dict]) -> list[dict]:
    """Keep the FIRST occurrence of each employee_id, preserving original order."""
    seen: set[str] = set()
    result: list[dict] = []
    for record in records:
        employee_id = record["employee_id"]
        if employee_id in seen:
            continue
        seen.add(employee_id)
        result.append(record)
    return result
