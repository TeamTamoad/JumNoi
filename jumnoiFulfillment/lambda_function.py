import json
from dialogflow_fulfillment import QuickReplies, WebhookClient


def lambda_handler(event, context):
    body = json.loads(event["body"])
    print(body)

    def save_handler(agent: WebhookClient):
        print(agent.parameters)
        agent.add(f"บันทึกเรียบร้อย")

    def exp_handler(agent: WebhookClient):
        print(agent.context.contexts.keys())
        print(agent.parameters)
        dt = "13/02/66"
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

    agent = WebhookClient(body)

    handler = {
        "Note Exp - exp image": exp_handler,
        "Note Exp - exp text": exp_text_handler,
        "Note Exp - exp image - yes": save_handler,
    }

    agent.handle_request(handler)

    return agent.response
