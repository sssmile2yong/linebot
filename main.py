from fastapi import FastAPI, Request, Header
from linebot import LineBotApi, WebhookParser
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from gpt import get_gpt_response
import os

app = FastAPI()

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
parser = WebhookParser(os.getenv("LINE_CHANNEL_SECRET"))


@app.get("/")
def read_root():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request, x_line_signature: str = Header(None)):
    body = await request.body()
    body_str = body.decode("utf-8")

    try:
        events = parser.parse(body_str, x_line_signature)
    except Exception as e:
        print("Signature error:", e)
        return "Signature error"

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessage):
            user_input = event.message.text
            reply = get_gpt_response(user_input)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply)
            )

    return "OK"
