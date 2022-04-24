import calendar
import itertools
import json
import re
from datetime import date

import boto3

MONTH_NUMBER = {
    month.upper(): idx for (idx, month) in enumerate(calendar.month_abbr)
} | {month.upper(): idx for (idx, month) in enumerate(calendar.month_name)}


def get_date_regex() -> re.Pattern[str]:
    seperator = r"\/|-|\."
    month_name = "|".join(itertools.chain(calendar.month_abbr, calendar.month_name))
    month_number = r"1[0-2]|0?[1-9]"
    day = r"3[01]|[12][0-9]|0?[1-9]"
    year = r"(?:20)?\d{2}"
    return re.compile(
        f"({year}|{month_number}|{day})({seperator})?({month_name}|{month_number}|{day})\\2({year}|{day})",
        re.IGNORECASE,
    )


def create_date(front: str, middle: str, back: str) -> date:
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

    # handle case dd/mm/yy
    if year_num < 2000:
        year_num += 2000

    # handle case mm/dd/yyyy
    if month_num > 12:
        day_num, month_num = month_num, day_num

    return date(day=day_num, month=month_num, year=year_num)


rekog_client = boto3.client("rekognition")
date_regex = get_date_regex()


def lambda_handler(event, context):
    image_name = event["body"]

    # res = rekog_client.detect_text(Image={"Bytes": image})
    res = rekog_client.detect_text(
        Image={"S3Object": {"Bucket": "jumnoi", "Name": image_name}}
    )

    dates = []
    for text in res["TextDetections"]:
        # remove all whitespaces from the testing string
        text["DetectedText"] = "".join(text["DetectedText"].split())
        result = date_regex.match(text["DetectedText"])
        if result:
            capture_groups = result.groups()
            date = create_date(capture_groups[0], capture_groups[2], capture_groups[3])
            text["Groups"] = capture_groups
            text["DetectedDate"] = str(date)
            text.pop("Geometry")
            dates.append(text)

    return {"statusCode": 200, "body": json.dumps(dates)}
