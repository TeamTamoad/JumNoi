import base64
import calendar
import itertools
import urllib3
import json
import re
from datetime import date

import boto3
import requests
from dialogflow_fulfillment import QuickReplies, WebhookClient
from dotenv import dotenv_values

config = dotenv_values()
LINE_ACCESS_TOKEN = config["LINE_ACCESS_TOKEN"]
BUCKET_NAME = config["BUCKET_NAME"]
BUCKET_REGION = config["BUCKET_REGION"]
TABLE_NAME = config["TABLE_NAME"]

dynamodb_client = boto3.client("dynamodb")

http = urllib3.PoolManager()

MONTH_NUMBER = {
    month.upper(): idx for (idx, month) in enumerate(calendar.month_abbr)
} | {month.upper(): idx for (idx, month) in enumerate(calendar.month_name)}


def get_date_regex() -> re.Pattern[str]:
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
date_regex = get_date_regex()


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
    
    def getMemo_handler(agent: WebhookClient):
        userId = body["originalDetectIntentRequest"]["payload"]["data"]["source"]["userId"]
        
        payload = {
                    "type": "flex",
                    "altText": "This is a Flex Message",
                    "contents": {
                        "type": "bubble",
                        "hero": {
                            "type": "image",
                            "size": "full",
                            "aspectRatio": "20:13",
                            "aspectMode": "cover",
                            "url": "https://scdn.line-apps.com/n/channel_devcenter/img/fx/01_5_carousel.png"
                        },
                        "body": {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "sm",
                            "contents": [{
                                            "type": "text",
                                            "text": "กรุณาเลือกวันที่",
                                            "wrap": True,
                                            "weight": "regular",
                                            "size": "xl"
                                        },
                                        {
                                            "type": "box",
                                            "layout": "baseline",
                                            "contents": [{
                                                        "type": "text",
                                                        "text": "เลือกวันเพื่อแสดงรายการสินค้าที่มีวันหมดอายุภายในวันที่เลือก",
                                                        "wrap": True,
                                                        "weight": "regular",
                                                        "flex": 0
                                                        }]
                                        }]
                            },
                            "footer": {
                                    "type": "box",
                                    "layout": "vertical",
                                    "spacing": "sm",
                                    "contents": [
                                      {
                                        "type": "button",
                                        "style": "primary",
                                        "action": {
                                          "type": "datetimepicker",
                                          "label": "เลือกวัน",
                                          "data": "เลือกวัน",
                                          "mode": "date"
                                        }
                                      },
                                      {
                                        "type": "button",
                                        "action": {
                                          "type": "postback",
                                          "label": "ยกเลิก",
                                          "data": "ยกเลิก"
                                        }
                                      }
                                    ]
                                  }
                        }
                    }
        
                       
        push_message(userId, payload)
        
    agent = WebhookClient(body)

    handler = {
        "Note Exp - exp image": exp_image_handler,
        "Note Exp - exp text": exp_text_handler,
        "Note Exp - exp image - yes": save_handler,
        
        "Get memo - start - custom" : getMemoCustom_handler,
        "Get memo - start": getMemo_handler

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
    
