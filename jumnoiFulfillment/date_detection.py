import calendar
import itertools
import re
from datetime import date
from typing import Optional

MONTH_NUMBER = {
    month.upper(): idx for (idx, month) in enumerate(calendar.month_abbr)
} | {month.upper(): idx for (idx, month) in enumerate(calendar.month_name)}


def get_date_regex() -> re.Pattern[str]:
    """
    Return a regex that can detect and capture the components of date.

    Capture group detail:
        - Group 1: The front part of date. Possible values are 'day', 'month' or 'year'
        - Group 2: The seperator. Possible values are '/', '-', '.' or empty string
        - Group 3: The middle part of date. Possible values are 'day' or 'month'
        - Group 4: The back part of date. Possible values are 'day' or 'year'
    """
    seperator = r"\/|-|\.|[ ]*"
    month_name = "|".join(
        itertools.chain(calendar.month_abbr[1:], calendar.month_name[1:])
    )
    month_number = r"1[0-2]|0?[1-9]"
    day = r"3[01]|[12][0-9]|0?[1-9]"
    year_front = r"20\d{2}"
    year_back = r"(?:20|25)?\d{2}"
    return re.compile(
        rf"({year_front}|{month_number}|{day})({seperator})({month_name}|{month_number}|{day})\2({year_back}|{day})",
        re.IGNORECASE,
    )


def create_date(front: str, middle: str, back: str) -> Optional[date]:
    """Create a date object from the given 3 parts"""
    try:
        month_num = int(middle)
    except ValueError:
        month_num = MONTH_NUMBER[middle.upper()]

    day_num = int(front)
    year_num = int(back)

    # handle case yyyy/mm/dd
    if day_num > 2000:
        day_num, year_num = year_num, day_num

    # handle case buddhist calendar
    if year_num > 2500:
        year_num -= 543
    elif 60 < year_num < 2000:
        year_num -= 43

    # handle case dd/mm/yy
    if year_num < 2000:
        year_num += 2000

    # handle case mm/dd/yyyy
    if month_num > 12:
        day_num, month_num = month_num, day_num

    try:
        return date(day=day_num, month=month_num, year=year_num)
    except ValueError:
        return None
