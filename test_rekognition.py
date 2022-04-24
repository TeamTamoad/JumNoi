import json
import re

import boto3


def get_date_regex() -> re.Pattern[str]:
    seperator = r"\/|-|\."
    month = r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|1[0-2]|0?[1-9]"
    day = r"3[01]|[12][0-9]|0?[1-9]"
    year = r"(?:20)?\d{2}"
    return re.compile(
        f"({year}|{month}|{day})({seperator})?({month}|{day})\\2({year}|{day})",
        re.IGNORECASE,
    )


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
            text.pop("Geometry")
            text["Groups"] = result.groups()
            dates.append(text)

    return {"statusCode": 200, "body": json.dumps(dates)}
