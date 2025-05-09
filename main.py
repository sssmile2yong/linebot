from fastapi import FastAPI, Request, Header
from linebot import LineBotApi, WebhookParser
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from gpt import get_gpt_response
import os

app = FastAPI()

LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
RAILWAY_PORT_CHECK = os.getenv("PORT") # 再次確認 PORT

print("--- Railway Environment Variable Check ---")
print(f"LINE_CHANNEL_ACCESS_TOKEN is set: {LINE_TOKEN is not None}")
print(f"LINE_CHANNEL_SECRET is set: {LINE_SECRET is not None}")
print(f"OPENAI_API_KEY is set: {OPENAI_KEY is not None}")
print(f"PORT from env: {RAILWAY_PORT_CHECK}")
print("----------------------------------------")

app = FastAPI()

# 確保在檢查後才初始化，並加入 try-except
try:
    if LINE_TOKEN and LINE_SECRET:
        line_bot_api = LineBotApi(LINE_TOKEN)
        parser = WebhookParser(LINE_SECRET)
        print("Line Bot SDK initialized.")
    else:
        print("ERROR: Line Bot SDK credentials not fully set. Some features might fail.")
        # 根據你的需求，這裡可能需要更強硬的錯誤處理，例如直接讓應用程式啟動失敗
        line_bot_api = None
        parser = None
except Exception as e:
    print(f"CRITICAL ERROR during SDK initialization: {e}")
    # 這裡拋出異常可能會讓部署直接失敗，更容易發現問題
    # raise e # 如果你希望初始化失敗就停止部署

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
