from scraper.parser import dedupe_records, parse_employee


def test_parses_id_with_single_name():
    assert parse_employee("11212155 นิรพงษ์") == ("11212155", "นิรพงษ์")


def test_parses_id_with_full_name():
    assert parse_employee("11212155 สมชาย ใจดี") == ("11212155", "สมชาย ใจดี")


def test_parses_id_immediately_followed_by_thai():
    # "20000777ปิยะวัฒน์" — no space between ID and name (common in real comments)
    assert parse_employee("20000777ปิยะวัฒน์ วิชัยยา") == ("20000777", "ปิยะวัฒน์ วิชัยยา")


def test_skips_comment_without_id():
    assert parse_employee("ร่วมกิจกรรมครับ") is None
    assert parse_employee("โชคดีครับ") is None


def test_skips_id_embedded_in_longer_number():
    # 9-digit sequence must not match any 8-digit substring
    assert parse_employee("112121551 สมชาย") is None


def test_skips_empty_comment():
    assert parse_employee("") is None


def test_strips_leading_separators_after_id():
    assert parse_employee("11212155 - สมชาย") == ("11212155", "สมชาย")
    assert parse_employee("11212155: สมชาย") == ("11212155", "สมชาย")


def test_dedupe_keeps_first_occurrence():
    records = [
        {"employee_id": "11212155", "employee_name": "First"},
        {"employee_id": "99999999", "employee_name": "Other"},
        {"employee_id": "11212155", "employee_name": "Second (duplicate)"},
    ]
    result = dedupe_records(records)
    assert len(result) == 2
    assert result[0]["employee_name"] == "First"
    assert result[1]["employee_id"] == "99999999"
