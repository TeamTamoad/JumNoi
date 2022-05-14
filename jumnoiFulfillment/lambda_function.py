import base64
import json
import os
from datetime import date, datetime

import boto3
import requests
from date_detection import create_date, get_date_regex
from dialogflow_fulfillment import QuickReplies, WebhookClient

LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
TABLE_NAME = os.getenv("TABLE_NAME")
BUCKET_NAME = os.getenv("BUCKET_NAME")

assert LINE_ACCESS_TOKEN is not None
assert TABLE_NAME is not None
assert BUCKET_NAME is not None


rekog_client = boto3.client("rekognition")
dynamo_client = boto3.client("dynamodb")
s3_client = boto3.client("s3")
date_regex = get_date_regex()


def save_handler(agent: WebhookClient):
    """Save item image to S3 and save meta-data to dynamodb"""
    print("Save handler")
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
    print(f"{get_item_res}")
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
    s3_client.put_object(Bucket=BUCKET_NAME, Key=product_id, Body=image_data.content)
    agent.add(f"บันทึกเรียบร้อย")


def exp_image_handler(agent: WebhookClient):
    """Detect the exp date from the image"""
    print("Exp image handler")

    image_id = agent.original_request["payload"]["data"]["message"]["id"]
    print(f"{image_id}")
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
        agent.context.set(
            "noteexp-product-followup",
            lifespan_count=1,
        )
        agent.context.set(
            "note-process",
            lifespan_count=1,
        )
        agent.add("ไม่พบวันหมดอายุในรูป กรุณาส่งรูปหรือข้อความแสดงวันหมดอายุอีกครั้ง")
        return

    agent.context.set(
        "noteexp-expimage-followup",
        lifespan_count=1,
        parameters={"expDate": str(exp_date), "imageId": image_id},
    )
    # agent.add(
    #     f"วันหมดอายุของสินค้าคือวันที่ {exp_date.strftime('%d %B %Y')} ใช่หรือไม่"
    # )
    agent.add(
        QuickReplies(
            title=f"วันหมดอายุของสินค้าคือวันที่ {exp_date.strftime('%d %B %Y')} ใช่หรือไม่",
            quick_replies=["ใช่เลย", "ไม่ใช่"],
        )
    )


def exp_text_handler(agent: WebhookClient):
    print("Exp text handler")
    # print(f"text original {agent.original_request}")
    # print(f"text parameter {agent.parameters}")
    # print(agent.query)
    exp_date = datetime.strptime(agent.parameters["expDate"], "%Y-%m-%dT%H:%M:%S%z")
    agent.context.set(
        "noteexp-expimage-followup",
        lifespan_count=1,
        parameters={"expDate": str(exp_date)},
    )
    # agent.add(
    #     f"วันหมดอายุของสินค้าคือวันที่ {exp_date.strftime('%d %B %Y')} ใช่หรือไม่"
    # )
    agent.add(
        QuickReplies(
            title=f"วันหมดอายุของสินค้าคือวันที่ {exp_date.strftime('%d %B %Y')} ใช่หรือไม่",
            quick_replies=["ใช่เลย", "ไม่ใช่"],
        )
    )


handler = {
    "Note Exp - exp image": exp_image_handler,
    "Note Exp - exp text": exp_text_handler,
    "Note Exp - exp image - yes": save_handler,
}


def lambda_handler(event, context):
    body = json.loads(event["body"])
    print(body)

    agent = WebhookClient(body)
    agent.handle_request(handler)

    return agent.response
