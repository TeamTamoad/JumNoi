import json
import os
from datetime import datetime, timedelta, timezone

import boto3
import urllib3

LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
BUCKET_NAME = os.getenv("BUCKET_NAME")
BUCKET_REGION = os.getenv("BUCKET_REGION")
TABLE_NAME = os.getenv("TABLE_NAME")

assert LINE_ACCESS_TOKEN is not None
assert BUCKET_NAME is not None
assert BUCKET_REGION is not None
assert TABLE_NAME is not None

dynamodb_client = boto3.client("dynamodb")
http = urllib3.PoolManager()


def lambda_handler(event, context):
    bangkok_tz = timezone(timedelta(hours=7))
    tomorrow = (datetime.now(tz=bangkok_tz) + timedelta(days=1)).strftime("%Y-%m-%d")

    dynamodb_response = dynamodb_client.query(
        TableName=TABLE_NAME,
        KeyConditionExpression="expDate = :expDate",
        ExpressionAttributeValues={":expDate": {"S": tomorrow}},
    )

    for item in dynamodb_response.get("Items", []):
        user_id = item.get("userId", {}).get("S")
        s3_url = [e for e in item.get("s3Url", {}).get("SS", [])]

        msg = {
            "type": "text",
            "text": f"คุณมีสินค้าที่กำลังจะหมดอายุในวันพรุ่งนี้จำนวน {len(s3_url)} รายการ ดังนี้",
        }
        push_message(user_id, msg)

        # each carousel message can contain no more than 12 images
        for i in range(0, len(s3_url), 12):
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
                                                                "text": "หมดอายุวันพรุ่งนี้",
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
                                        "backgroundColor": "#e61919",
                                        "justifyContent": "center",
                                        "alignItems": "center",
                                        "paddingTop": "10px",
                                        "paddingBottom": "10px",
                                    },
                                    {
                                        "type": "box",
                                        "layout": "vertical",
                                        "contents": [
                                            {
                                                "type": "text",
                                                "text": "WARNING",
                                                "color": "#ffffff",
                                                "align": "center",
                                                "size": "xs",
                                                "offsetTop": "1px",
                                                "weight": "bold",
                                            }
                                        ],
                                        "position": "absolute",
                                        "cornerRadius": "20px",
                                        "offsetTop": "18px",
                                        "backgroundColor": "#e61919",
                                        "offsetStart": "18px",
                                        "height": "30px",
                                        "width": "80px",
                                        "justifyContent": "center",
                                        "alignItems": "center",
                                    },
                                ],
                                "paddingAll": "0px",
                            },
                        }
                        for url in s3_url[i : i + 12]
                    ],
                },
            }
            push_message(user_id, msg)

    return {"statusCode": 200, "body": json.dumps("Done!")}


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
