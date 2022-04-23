import base64
import hashlib
import hmac
import json

import urllib3
from dotenv import dotenv_values

config = dotenv_values()
LINE_ACCESS_TOKEN = config["LINE_ACCESS_TOKEN"]
DIALOGFLOW_URL = config["DIALOGFLOW_URL"]
CHANNEL_SECRET = config["CHANNEL_SECRET"]

http = urllib3.PoolManager()


def lambda_handler(event, context):
    headers = event["headers"]
    body = json.loads(event["body"])
    print(event)
    # print(body)

    message_type = body["events"][0]["message"]["type"]
    if message_type == "text":
        # body["events"][0]["message"]["text"] = "สวัสดี"
        dialogflow_handler(headers, body)
    elif message_type == "image":
        body["events"][0]["message"]["type"] = "text"
        body["events"][0]["message"]["text"] = body["events"][0]["message"]["id"]
        dialogflow_handler(headers, body)
    else:
        reply(
            body["events"][0]["replyToken"],
            {
                "type": "text",
                "text": f"ไม่เข้าใจข้อความประเภท {message_type}",
            },
        )

    return {"statusCode": 200, "body": json.dumps("Done!")}


def dialogflow_handler(headers, body):
    headers["host"] = "dialogflow.cloud.google.com"
    headers.pop("content-length")
    headers["x-line-signature"] = get_signature(to_json(body), CHANNEL_SECRET)

    print(headers)
    print(body)

    http.request(
        "POST",
        DIALOGFLOW_URL,
        headers=headers,
        body=to_json(body).encode(),
        retries=False,
    )


def get_signature(message, key):
    return base64.b64encode(
        hmac.new(key.encode(), message.encode(), digestmod=hashlib.sha256).digest()
    ).decode()


def to_json(data):
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def reply(token, payload):
    http.request(
        "POST",
        "https://api.line.me/v2/bot/message/reply",
        headers={
            "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        body=json.dumps({"replyToken": token, "messages": [payload]}),
        retries=False,
    )