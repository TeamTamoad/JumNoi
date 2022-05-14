import unittest
from datetime import date
from typing import Optional

from date_detection import create_date, get_date_regex


class TestDetectExpDate(unittest.TestCase):
    date_regex = get_date_regex()

    @classmethod
    def detect_date(cls, input: str) -> Optional[date]:
        res = cls.date_regex.match(input)
        if res is not None:
            groups = res.groups()
            return create_date(groups[0], groups[2], groups[3])
        return None

    def assert_detect_date(self, input: str, day: int, month: int, year: int):
        self.assertEqual(self.detect_date(input), date(year, month, day))

    def assert_not_detect_date(self, input: str):
        self.assertIsNone(self.detect_date(input))

    def test_no_seperator(self):
        self.assert_not_detect_date("11122122")
        self.assert_not_detect_date("20asdf22")

    def test_basic(self):
        self.assert_detect_date("15/12/2022", day=15, month=12, year=2022)

    def test_not_detect_date(self):
        self.assert_not_detect_date("asd23423")
        self.assert_not_detect_date("15-15-2022")
        self.assert_not_detect_date("9-12/2023")


if __name__ == "__main__":
    unittest.main()
