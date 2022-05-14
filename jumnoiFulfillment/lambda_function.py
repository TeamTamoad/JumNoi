import base64
import calendar
import itertools
import urllib3

import json
import os
from datetime import date, datetime

import boto3
import requests
from date_detection import create_date, get_date_regex
from dialogflow_fulfillment import Payload, QuickReplies, WebhookClient
from dotenv import dotenv_values


config = dotenv_values()
LINE_ACCESS_TOKEN = config["LINE_ACCESS_TOKEN"]
BUCKET_NAME = config["BUCKET_NAME"]
BUCKET_REGION = config["BUCKET_REGION"]
TABLE_NAME = config["TABLE_NAME"]

dynamodb_client = boto3.client("dynamodb")

http = urllib3.PoolManager()


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
            f"วันหมดอายุของสินค้าคือวันที่ {exp_date.strftime('%d %B %Y')} ใช่หรือไม่"
        )
        # agent.add(
        #     QuickReplies(
        #         title=f"วันหมดอายุของสินค้าคือวันที่ {exp_date.strftime('%d %B %Y')} ใช่หรือไม่",
        #         quick_replies=["ใช่เลย", "ไม่ใช่"],
        #     )
        # )
    except IndexError:
        agent.context.set(
            "noteexp-product-followup",
            lifespan_count=1,
        )
        agent.context.set(
            "note-process",
            lifespan_count=1,
        )
        # agent.add("ไม่พบวันหมดอายุในรูป กรุณาส่งรูปหรือข้อความแสดงวันหมดอายุอีกครั้ง")
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
    # print(f"text original {agent.original_request}")
    # print(f"text parameter {agent.parameters}")
    # print(agent.query)
    exp_date = datetime.fromisoformat(agent.parameters["expDate"]).date()
    agent.context.set(
        "noteexp-expimage-followup",
        lifespan_count=1,
        parameters={"expDate": str(exp_date)},
    )
    agent.add(
        f"วันหมดอายุของสินค้าคือวันที่ {exp_date.strftime('%d %B %Y')} ใช่หรือไม่"
    )
    # agent.add(
    #     QuickReplies(
    #         title=f"วันหมดอายุของสินค้าคือวันที่ {exp_date.strftime('%d %B %Y')} ใช่หรือไม่",
    #         quick_replies=["ใช่เลย", "ไม่ใช่"],
    #     )
    # )


handler = {
    "Note Exp - exp image": exp_image_handler,
    "Note Exp - exp text": exp_text_handler,
    "Note Exp - exp image - yes": save_handler,
}


def lambda_handler(event, context):
    body = json.loads(event["body"])
    print(body)
        
    def save_handler(agent: WebhookClient):
        print(agent.parameters)
        agent.add(f"บันทึกเรียบร้อย")

    def exp_image_handler(agent: WebhookClient):
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
        dates = []
        for text in res["TextDetections"]:
            # remove all whitespaces from the testing string
            text["DetectedText"] = "".join(text["DetectedText"].split())
            result = date_regex.match(text["DetectedText"])
            if result:
                capture_groups = result.groups()
                date = create_date(
                    capture_groups[0], capture_groups[2], capture_groups[3]
                )
                dates.append(str(date))

        dt = dates[0]
        agent.context.set(
            "noteexp-expimage-followup", lifespan_count=2, parameters={"expDate": dt}
        )
        agent.add(f"วันหมดอายุของสินค้าคือวันที่ {dt} ใช่หรือไม่")
        # agent.add(QuickReplies(quick_replies=['ใช่เลย', 'ไม่ใช่']))

    def exp_text_handler(agent: WebhookClient):
        print(body["queryResult"]["parameters"]["expDate"])
        dt = body["queryResult"]["parameters"]["expDate"]
        agent.context.set(
            "noteexp-expimage-followup", lifespan_count=2, parameters={"expDate": dt}
        )
        agent.add(f"วันหมดอายุของสินค้าคือวันที่ {dt} ใช่หรือไม่")
        # agent.add(QuickReplies(quick_replies=['ใช่เลย', 'ไม่ใช่']))

    def getMemoCustom_handler(agent: WebhookClient):
        expDate = body["queryResult"]["parameters"]["expDate"].split("T")[0]
        userId = body["originalDetectIntentRequest"]["payload"]["data"]["source"]["userId"]
        
        dynamodb_response = dynamodb_client.query(
            TableName=TABLE_NAME,
            KeyConditionExpression="userId = :userId AND expDate = :expDate",
            ExpressionAttributeValues={":userId": {"S": userId}, ":expDate": {"S": expDate}},
        )
        
        if len(dynamodb_response.get("Items", [])) == 0:
            msg = {
                "type": "text",
                "text": f"คุณไม่มีสินค้าที่กำลังจะหมดอายุในวันที่ {expDate} ค่ะ",
            }
            push_message(userId, msg)
        
        
        for item in dynamodb_response.get("Items", []):
            s3_url = [e.get("S") for e in item.get("s3Url", {}).get("L", [])]
    
            msg = {
                "type": "text",
                "text": f"คุณมีสินค้าที่กำลังจะหมดอายุในวันที่ {expDate} จำนวน {len(s3_url)} รายการ",
            }
            push_message(userId, msg)
    
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
                                        }
                                    ],
                                    "paddingAll": "0px",
                                },
                            }
                            for url in s3_url[i : i + 12]
                        ],
                    },
                }
                push_message(userId, msg)
        
        # agent.add(f"รายการที่หมดอายุในวันที่ {expDate} มีดังนี้")
    


    agent = WebhookClient(body)

    handler = {
        "Note Exp - exp image": exp_image_handler,
        "Note Exp - exp text": exp_text_handler,
        "Note Exp - exp image - yes": save_handler,
        
        "Get memo - start - custom" : getMemoCustom_handler,
    }


    agent.handle_request(handler)

    return agent.response
    

def push_message(userId, payload):
    http.request(
        "POST",
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        body=json.dumps({"to": userId, "messages": [payload]}),
        retries=False,
    )
    
