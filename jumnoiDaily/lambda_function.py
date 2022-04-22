import json
from datetime import datetime, timedelta, timezone

import boto3
import urllib3
from dotenv import dotenv_values

config = dotenv_values()
LINE_ACCESS_TOKEN = config["LINE_ACCESS_TOKEN"]
BUCKET_NAME = config["BUCKET_NAME"]
BUCKET_REGION = config["BUCKET_REGION"]
TABLE_NAME = config["TABLE_NAME"]

dynamodb_client = boto3.client("dynamodb")
http = urllib3.PoolManager()


def lambda_handler(event, context):
    bangkok_tz = timezone(timedelta(hours=7))
    tomorrow = (datetime.now(tz=bangkok_tz) + timedelta(days=1)).strftime("%Y-%m-%d")

    dynamodb_response = dynamodb_client.query(
        TableName=TABLE_NAME,
        KeyConditionExpression="expDate = :expDate",
        ExpressionAttributeValues={":expDate": {"S": "2020-08-08"}},
    )

    for item in dynamodb_response.get("Items", []):
        user_id = item.get("userId", {}).get("S")
        s3_url = [e.get("S") for e in item.get("s3Url", {}).get("L", [])]
        # print(user_id, s3_url)
        for obj_key in s3_url:
            object_url = (
                f"https://{BUCKET_NAME}.s3.{BUCKET_REGION}.amazonaws.com/{obj_key}"
            )

            msg = {
                "type": "image",
                "originalContentUrl": object_url,
                "previewImageUrl": object_url,
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


# {
#   "Items": [
#     {
#       "expDate": { "S": "2020-08-08" },
#       "userId": { "S": "user1" },
#       "s3Url": { "L": [{ "S": "image1.png" }, { "S": "image2.png" }] }
#     },
#     {
#       "expDate": { "S": "2020-08-08" },
#       "userId": { "S": "user2" },
#       "s3Url": { "L": [{ "S": "image3.png" }, { "S": "image4.png" }] }
#     }
#   ],
#   "Count": 2,
#   "ScannedCount": 2,
#   "ResponseMetadata": {
#     "RequestId": "GJS1K94LE8KA2PE21KM3VRH9OJVV4KQNSO5AEMVJF66Q9ASUAAJG",
#     "HTTPStatusCode": 200,
#     "HTTPHeaders": {
#       "server": "Server",
#       "date": "Wed, 20 Apr 2022 03:36:11 GMT",
#       "content-type": "application/x-amz-json-1.0",
#       "content-length": "254",
#       "connection": "keep-alive",
#       "x-amzn-requestid": "GJS1K94LE8KA2PE21KM3VRH9OJVV4KQNSO5AEMVJF66Q9ASUAAJG",
#       "x-amz-crc32": "1543826313"
#     },
#     "RetryAttempts": 0
#   }
# }

# msg = {
#     "type": "text",
#     "text": "daily message",
# }
# msg = {
#     "type": "image",
#     "originalContentUrl": "https://example.com/original.jpg",
#     "previewImageUrl": "https://example.com/preview.jpg"
# }
# push_message("U25344749ee878e72424647a2ef279d15", msg)

# {
#     "type": "image",
#     "originalContentUrl": "https://example.com/original.jpg",
#     "previewImageUrl": "https://example.com/preview.jpg"
# }
