import base64
import json
import os
from datetime import date, datetime

import boto3
import requests
import urllib3
from date_detection import create_date, get_date_regex
from dialogflow_fulfillment import Payload, WebhookClient

LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
BUCKET_NAME = os.getenv("BUCKET_NAME")
BUCKET_REGION = os.getenv("BUCKET_REGION")
TABLE_NAME = os.getenv("TABLE_NAME")

assert LINE_ACCESS_TOKEN is not None
assert TABLE_NAME is not None
assert BUCKET_NAME is not None
assert BUCKET_REGION is not None

rekog_client = boto3.client("rekognition")
dynamodb_client = boto3.client("dynamodb")
s3_client = boto3.client("s3")
date_regex = get_date_regex()
http = urllib3.PoolManager()


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

    get_item_res = dynamodb_client.get_item(
        TableName=TABLE_NAME,
        Key=item_key,
    )
    print(f"{get_item_res}")
    if "Item" in get_item_res:
        res = dynamodb_client.update_item(
            TableName=TABLE_NAME,
            Key=item_key,
            UpdateExpression="ADD s3Url :u",
            ExpressionAttributeValues={":u": {"SS": [product_id]}},
        )
        print("update item res", res)
    else:
        res = dynamodb_client.put_item(
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
            if detected_date is not None:
                detected_dates.append(detected_date)

    detected_dates.sort(reverse=True)

    try:
        exp_date = detected_dates[0]
        agent.context.set(
            "noteexp-expimage-followup",
            lifespan_count=1,
            parameters={"expDate": str(exp_date), "imageId": image_id},
        )
        agent.add(
            Payload(
                {
                    "line": {
                        "type": "text",
                        "text": f"วันหมดอายุของสินค้าคือวันที่ {exp_date.strftime('%d %B %Y')} ใช่หรือไม่",
                        "quickReply": {
                            "items": [
                                {
                                    "type": "action",
                                    "action": {
                                        "type": "message",
                                        "label": "ใช่",
                                        "text": "ใช่",
                                    },
                                },
                                {
                                    "type": "action",
                                    "action": {
                                        "type": "message",
                                        "label": "ไม่ใช่",
                                        "text": "ไม่ใช่",
                                    },
                                },
                            ]
                        },
                    }
                }
            )
        )
    except IndexError:
        agent.context.set(
            "noteexp-product-followup",
            lifespan_count=1,
        )
        agent.context.set(
            "note-process",
            lifespan_count=1,
        )
        agent.add(
            Payload(
                {
                    "line": {
                        "type": "text",
                        "text": "ไม่พบวันหมดอายุในรูป กรุณาส่งรูปหรือข้อความแสดงวันหมดอายุอีกครั้ง",
                        "quickReply": {
                            "items": [
                                {
                                    "action": {"type": "camera", "label": "ถ่ายรูป"},
                                    "type": "action",
                                },
                                {
                                    "action": {
                                        "type": "cameraRoll",
                                        "label": "เลือกรูป",
                                    },
                                    "type": "action",
                                },
                                {
                                    "action": {
                                        "type": "datetimepicker",
                                        "data": "date",
                                        "label": "เลือกวัน",
                                        "mode": "date",
                                    },
                                    "type": "action",
                                },
                            ]
                        },
                    }
                }
            )
        )


def exp_text_handler(agent: WebhookClient):
    print("Exp text handler")
    exp_date = datetime.fromisoformat(agent.parameters["expDate"]).date()
    agent.context.set(
        "noteexp-expimage-followup",
        lifespan_count=1,
        parameters={"expDate": str(exp_date)},
    )
    agent.add(
        Payload(
            {
                "line": {
                    "type": "text",
                    "text": f"วันหมดอายุของสินค้าคือวันที่ {exp_date.strftime('%d %B %Y')} ใช่หรือไม่",
                    "quickReply": {
                        "items": [
                            {
                                "type": "action",
                                "action": {
                                    "type": "message",
                                    "label": "ใช่",
                                    "text": "ใช่",
                                },
                            },
                            {
                                "type": "action",
                                "action": {
                                    "type": "message",
                                    "label": "ไม่ใช่",
                                    "text": "ไม่ใช่",
                                },
                            },
                        ]
                    },
                }
            }
        )
    )


def get_memo_custom_handler(agent: WebhookClient):
    exp_date = datetime.fromisoformat(agent.parameters["expDate"]).date()
    user_id = agent.original_request["payload"]["data"]["source"]["userId"]

    dynamodb_response = dynamodb_client.scan(
        TableName=TABLE_NAME,
        FilterExpression="userId = :userId AND expDate <= :expDate",
        ExpressionAttributeValues={
            ":userId": {"S": user_id},
            ":expDate": {"S": str(exp_date)},
        },
    )

    items = dynamodb_response.get("Items", [])
    all_s3_url = [url for item in items for url in item["s3Url"]["SS"]]

    if len(all_s3_url) == 0:
        msg = {
            "type": "text",
            "text": f"คุณไม่มีสินค้าที่กำลังจะหมดอายุในวันที่ {exp_date.strftime('%d %B %Y')} ค่ะ",
        }
        push_message(user_id, msg)
        return

    msg = {
        "type": "text",
        "text": f"คุณมีสินค้าที่กำลังจะหมดอายุในวันที่ {exp_date.strftime('%d %B %Y')} จำนวน {len(all_s3_url)} รายการ",
    }
    push_message(user_id, msg)

    # each carousel message can contain no more than 12 images
    for i in range(0, len(all_s3_url), 12):
        msg = {
            "type": "flex",
            "altText": "รายการสินค้าใกล้หมดอายุ",
            "contents": {
                "type": "carousel",
                "contents": [
                    {
                        "type": "bubble",
                        "body": {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "image",
                                    "url": f"https://{BUCKET_NAME}.s3.{BUCKET_REGION}.amazonaws.com/{url}",
                                    "size": "full",
                                },
                                {
                                    "type": "text",
                                    "text": f"วันหมดอายุ :",
                                }
                            ],
                            "paddingAll": "0px",
                        },
                    }
                    for url in all_s3_url[i : i + 12]
                ],
            },
        }
        push_message(user_id, msg)


def lambda_handler(event, context):
    body = json.loads(event["body"])
    print(body)

    agent = WebhookClient(body)
    handler = {
        "Note Exp - exp image": exp_image_handler,
        "Note Exp - exp text": exp_text_handler,
        "Note Exp - exp image - yes": save_handler,
        "Get memo - start - custom": get_memo_custom_handler,
    }
    agent.handle_request(handler)

    return agent.response


def push_message(user_id, payload):
    http.request(
        "POST",
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        body=json.dumps({"to": user_id, "messages": [payload]}),
        retries=False,
    )
