import json
import re

import boto3

rekog_client = boto3.client("rekognition")
date_regex = re.compile(
    r"^(?:(?:31(\/|-|\.)?(?:0?[13578]|1[02]|(?:Jan|Mar|May|Jul|Aug|Oct|Dec)))\1|(?:(?:29|30)(\/|-|\.)?(?:0?[1,3-9]|1[0-2]|(?:Jan|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))\2))(?:(?:1[6-9]|[2-9]\d)?\d{2})$|^(?:29(\/|-|\.)?(?:0?2|(?:Feb))\3(?:(?:(?:1[6-9]|[2-9]\d)?(?:0[48]|[2468][048]|[13579][26])|(?:(?:16|[2468][048]|[3579][26])00))))$|^(?:0?[1-9]|1\d|2[0-8])(\/|-|\.)?(?:(?:0?[1-9]|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep))|(?:1[0-2]|(?:Oct|Nov|Dec)))\4(?:(?:1[6-9]|[2-9]\d)?\d{2})$"
)


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
        if date_regex.match(text["DetectedText"]):
            text.pop("Geometry")
            dates.append(text)

    return {"statusCode": 200, "body": json.dumps(dates)}
