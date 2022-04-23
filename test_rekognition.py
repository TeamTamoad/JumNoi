import json

import boto3

rekog_client = boto3.client("rekognition")


def lambda_handler(event, context):
    # image = event["body"]
    # print(f"{image=}")

    # res = rekog_client.detect_text(Image={"Bytes": image})
    res = rekog_client.detect_text(
        Image={"S3Object": {"Bucket": "jumnoi", "Name": "oreo_milk.jpg"}}
    )
    for text in res["TextDetections"]:
        text.pop("Geometry")

    return {"statusCode": 200, "body": json.dumps(res)}
