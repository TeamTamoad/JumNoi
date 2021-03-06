import base64
import json
import os
from datetime import date, datetime, timezone, timedelta
import random

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
    agent.add(f"?????????????????????????????????????????????")


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
                        "text": f"???????????????????????????????????????????????????????????????????????????????????? {exp_date.strftime('%d %B %Y')} ??????????????????????????????",
                        "quickReply": {
                            "items": [
                                {
                                    "type": "action",
                                    "action": {
                                        "type": "message",
                                        "label": "?????????",
                                        "text": "?????????",
                                    },
                                },
                                {
                                    "type": "action",
                                    "action": {
                                        "type": "message",
                                        "label": "??????????????????",
                                        "text": "??????????????????",
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
                        "text": "???????????????????????????????????????????????????????????? ????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????",
                        "quickReply": {
                            "items": [
                                {
                                    "action": {"type": "camera", "label": "?????????????????????"},
                                    "type": "action",
                                },
                                {
                                    "action": {
                                        "type": "cameraRoll",
                                        "label": "????????????????????????",
                                    },
                                    "type": "action",
                                },
                                {
                                    "action": {
                                        "type": "datetimepicker",
                                        "data": "date",
                                        "label": "????????????????????????",
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
                    "text": f"???????????????????????????????????????????????????????????????????????????????????? {exp_date.strftime('%d %B %Y')} ??????????????????????????????",
                    "quickReply": {
                        "items": [
                            {
                                "type": "action",
                                "action": {
                                    "type": "message",
                                    "label": "?????????",
                                    "text": "?????????",
                                },
                            },
                            {
                                "type": "action",
                                "action": {
                                    "type": "message",
                                    "label": "??????????????????",
                                    "text": "??????????????????",
                                },
                            },
                        ]
                    },
                }
            }
        )
    )


def get_memo_custom_handler(agent: WebhookClient):
    colors = [
        "#03303A",
        "#FF6B6E",
        "#464F69",
        "#A17DF5",
        "#0D8186",
        "#CC6D1B",
        "#579918",
    ]
    random.shuffle(colors)

    bangkok_tz = timezone(timedelta(hours=7))
    today = datetime.now(tz=bangkok_tz).date()

    exp_date = datetime.fromisoformat(agent.parameters["expDate"]).date()
    user_id = agent.original_request["payload"]["data"]["source"]["userId"]

    dynamodb_response = dynamodb_client.scan(
        TableName=TABLE_NAME,
        FilterExpression="userId = :userId AND expDate >= :today AND expDate <= :expDate",
        ExpressionAttributeValues={
            ":userId": {"S": user_id},
            ":expDate": {"S": str(exp_date)},
            ":today": {"S": str(today)},
        },
    )

    items = dynamodb_response.get("Items", [])
    all_data = [
        (url, item.get("expDate", {}).get("S"), colors[i % len(colors)])
        for i, item in enumerate(items)
        for url in item.get("s3Url", {}).get("SS", [])
    ]
    all_data.sort(key=lambda x: x[1])

    if len(all_data) == 0:
        msg = {
            "type": "text",
            "text": f"?????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????? {exp_date.strftime('%d %B %Y')}",
        }
        push_message(user_id, msg)
        return

    msg = {
        "type": "text",
        "text": f"????????????????????????????????????????????????????????????????????????????????????????????????????????????????????? {exp_date.strftime('%d %B %Y')} ??????????????? {len(all_data)} ??????????????????",
    }
    push_message(user_id, msg)

    # each carousel message can contain no more than 12 images
    for i in range(0, len(all_data), 12):
        msg = {
            "type": "flex",
            "altText": "?????????????????????????????????????????????????????????????????????",
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
                                    "type": "box",
                                    "layout": "vertical",
                                    "contents": [
                                        {
                                            "type": "box",
                                            "layout": "vertical",
                                            "contents": [
                                                {"type": "filler"},
                                                {
                                                    "type": "box",
                                                    "layout": "baseline",
                                                    "contents": [
                                                        {"type": "filler"},
                                                        {
                                                            "type": "text",
                                                            "text": f"??????????????????????????????: {datetime.strptime(exp_date_text, '%Y-%m-%d').date().strftime('%d %B %Y')}",
                                                            "color": "#ffffff",
                                                            "flex": 0,
                                                            "weight": "bold",
                                                            "align": "center",
                                                            "size": "md",
                                                        },
                                                        {"type": "filler"},
                                                    ],
                                                    "spacing": "sm",
                                                },
                                                {"type": "filler"},
                                            ],
                                            "spacing": "sm",
                                            "margin": "none",
                                        }
                                    ],
                                    "position": "absolute",
                                    "offsetBottom": "0px",
                                    "offsetStart": "0px",
                                    "offsetEnd": "0px",
                                    "backgroundColor": color,
                                    "justifyContent": "center",
                                    "alignItems": "center",
                                    "paddingTop": "10px",
                                    "paddingBottom": "10px",
                                },
                            ],
                            "paddingAll": "0px",
                        },
                    }
                    for (url, exp_date_text, color) in all_data[i : i + 12]
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
