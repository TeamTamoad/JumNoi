import json
import urllib3
import boto3
from datetime import timedelta, datetime, timezone
import os

BUCKET_NAME = os.getenv("BUCKET_NAME")
BUCKET_REGION = os.getenv("BUCKET_REGION")
TABLE_NAME = os.getenv("TABLE_NAME")

dynamodb_client = boto3.client("dynamodb")
s3_client = boto3.client("s3")
http = urllib3.PoolManager()


def lambda_handler(event, context):
    bangkok_tz = timezone(timedelta(hours=7))
    today = datetime.now(tz=bangkok_tz).strftime("%Y-%m-%d")
    # (datetime.now(tz=bangkok_tz) + timedelta(days=1)).strftime("%Y-%m-%d")

    dynamodb_key = []
    s3_key = []

    # for i in range(7):

    dynamodb_response = dynamodb_client.query(
        TableName=TABLE_NAME,
        KeyConditionExpression="expDate = :expDate",
        ExpressionAttributeValues={":expDate": {"S": "2020-08-08"}},
    )

    for item in dynamodb_response.get("Items", []):
        dynamodb_key.append(
            {"expDate": {"S": "2020-08-08"}, "userId": item.get("userId", {})}
        )
        s3_key.extend([{"Key": e.get("S")} for e in item.get("s3Url", {}).get("L", [])])

    print(dynamodb_key)
    print(s3_key)

    for i in range(0, len(s3_key), 1000):
        s3_client.delete_objects(
            Bucket=BUCKET_NAME, Delete={"Objects": s3_key[i : i + 1000]}
        )

    for i in range(0, len(dynamodb_key), 25):
        dynamodb_client.batch_write_item(
            RequestItems={
                TABLE_NAME: [{"DeleteRequest": key} for key in s3_key[i : i + 25]]
            }
        )

    return {"statusCode": 200, "body": json.dumps("Done!")}