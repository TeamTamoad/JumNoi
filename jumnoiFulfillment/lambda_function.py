import base64
import calendar
import itertools
import json
import os
import re
from datetime import date

import boto3
import requests
from dialogflow_fulfillment import QuickReplies, WebhookClient

LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
TABLE_NAME = os.getenv("TABLE_NAME")
BUCKET_NAME = os.getenv("BUCKET_NAME")

assert LINE_ACCESS_TOKEN is not None
assert TABLE_NAME is not None
assert BUCKET_NAME is not None

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
    seperator = r"\/|-|\."
    month_name = "|".join(
        itertools.chain(calendar.month_abbr[1:], calendar.month_name[1:])
    )
    month_number = r"1[0-2]|0?[1-9]"
    day = r"3[01]|[12][0-9]|0?[1-9]"
    year_front = r"20\d{2}"
    year_back = r"(?:20)?\d{2}"
    return re.compile(
        f"({year_front}|{month_number}|{day})({seperator})?({month_name}|{month_number}|{day})\\2({year_back}|{day})",
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
dynamo_client = boto3.client("dynamodb")
s3_client = boto3.client("s3")
date_regex = get_date_regex()


def lambda_handler(event, context):
    body = json.loads(event["body"])
    print(body)

    def save_handler(agent: WebhookClient):
        """Save item image to S3 and save meta-data to dynamodb"""
        # print("agent.parameters in save_handler", agent.parameters)
        # print("body in save_handler", body)
        # print("agent original requests", agent.original_request)
        product_id = str(int(agent.parameters["productId"]))
        exp_date = agent.parameters["expDate"]
        user_id = agent.original_request["payload"]["data"]["source"]["userId"]
        print("product_id", product_id)
        print("exp_date", exp_date)
        print("user_id", user_id)

        item_key = {"expDate": {"S": exp_date}, "userId": {"S": user_id}}

        get_item_res = dynamo_client.get_item(
            TableName=TABLE_NAME,
            Key=item_key,
        )
        print(f"{get_item_res=}")
        if "Item" in get_item_res:
            res = dynamo_client.update_item(
                TableName=TABLE_NAME,
                Key=item_key,
                UpdateExpression="ADD s3Url :u",
                ExpressionAttributeValues={":u": {"SS": [product_id]}},
            )
            print("update item res", res)
        else:
            res = dynamo_client.put_item(
                TableName=TABLE_NAME,
                Item=item_key
                | {
                    "s3Url": {"SS": [product_id]},
                },
            )
        image_data = requests.get(
            f"https://api-data.line.me/v2/bot/message/{product_id}/content",
            headers={"Authorization": f"Bearer {LINE_ACCESS_TOKEN}"},
        )
        print("Image size:", len(image_data.content))
        s3_client.put_object(
            Bucket=BUCKET_NAME, Key=product_id, Body=image_data.content
        )
        agent.add(f"บันทึกเรียบร้อย")

    def exp_image_handler(agent: WebhookClient):
        """Detect the exp date from the image"""
        image_id = body["originalDetectIntentRequest"]["payload"]["data"]["message"][
            "id"
        ]
        image_data = requests.get(
            f"https://api-data.line.me/v2/bot/message/{image_id}/content",
            headers={"Authorization": f"Bearer {LINE_ACCESS_TOKEN}"},
        )
        print("content size", len(image_data.content))
        image = base64.decodebytes(base64.b64encode(image_data.content))

        res = rekog_client.detect_text(Image={"Bytes": image})
        detected_dates: list[date] = []
        for text in res["TextDetections"]:
            # remove all whitespaces from the testing string
            detected_text = "".join(text["DetectedText"].split())
            result = date_regex.match(detected_text)
            if result is not None:
                capture_groups = result.groups()
                detected_date = create_date(
                    capture_groups[0], capture_groups[2], capture_groups[3]
                )
                detected_dates.append(detected_date)

        detected_dates.sort(reverse=True)
        try:
            exp_date = detected_dates[0]
        except IndexError:
            exp_date = date.today()
        exp_date = str(exp_date)

        agent.context.set(
            "noteexp-expimage-followup",
            lifespan_count=2,
            parameters={"expDate": exp_date, "imageId": image_id},
        )
        agent.add(f"วันหมดอายุของสินค้าคือวันที่ {exp_date} ใช่หรือไม่")
        # agent.add(QuickReplies(quick_replies=["ใช่เลย", "ไม่ใช่"]))

    def exp_text_handler(agent: WebhookClient):
        print(body["queryResult"]["parameters"]["expDate"])
        exp_date = body["queryResult"]["parameters"]["expDate"]
        agent.context.set(
            "noteexp-expimage-followup",
            lifespan_count=2,
            parameters={"expDate": exp_date},
        )
        agent.add(f"วันหมดอายุของสินค้าคือวันที่ {exp_date} ใช่หรือไม่")
        # agent.add(QuickReplies(quick_replies=['ใช่เลย', 'ไม่ใช่']))

    agent = WebhookClient(body)

    handler = {
        "Note Exp - exp image": exp_image_handler,
        "Note Exp - exp text": exp_text_handler,
        "Note Exp - exp image - yes": save_handler,
    }

    agent.handle_request(handler)

    return agent.response
