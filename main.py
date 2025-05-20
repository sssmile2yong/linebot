from fastapi import FastAPI, Request, Header, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from gpt import get_gpt_response, SHANGHAI_AESTHETIC_SYSTEM_PROMPT
import os
import redis
import json



app = FastAPI()

# 環境變數讀取與檢查
LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_KEY = os.getenv("OPENAI_API_KEY") # 雖然 gpt.py 會檢查，這裡也確保主應用知道
REDIS_URL = os.getenv("REDIS_URL")

print("--- Application Startup ---")
print(f"LINE_TOKEN is set: {bool(LINE_TOKEN)}")
print(f"LINE_SECRET is set: {bool(LINE_SECRET)}")
print(f"OPENAI_KEY is set: {bool(OPENAI_KEY)}")
print(f"REDIS_URL is set: {bool(REDIS_URL)}")

# 初始化 Line Bot SDK
try:
    if not LINE_TOKEN or not LINE_SECRET:
        raise ValueError("LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET must be set.")
    line_bot_api = LineBotApi(LINE_TOKEN)
    parser = WebhookParser(LINE_SECRET)
    print("Line Bot SDK initialized successfully.")
except ValueError as ve:
    print(f"CRITICAL ERROR (Line Bot SDK): {ve}")
    # 在這種情況下，應用程式無法正常工作，可以考慮讓它啟動失敗
    # exit(1) # 如果希望直接退出
    line_bot_api = None
    parser = None
except Exception as e:
    print(f"CRITICAL ERROR initializing Line Bot SDK: {e}")
    line_bot_api = None
    parser = None
    # raise # 重新拋出異常，可能會讓 Railway 部署失敗，從而更容易發現問題

# 初始化 Redis Client
redis_client = None
if REDIS_URL:
    try:
        redis_client = redis.from_url(REDIS_URL, socket_connect_timeout=5) # 增加連接超時
        redis_client.ping()
        print("Redis client initialized and connected successfully.")
    except redis.exceptions.ConnectionError as rce:
        print(f"CRITICAL ERROR: Could not connect to Redis at {REDIS_URL}. Error: {rce}")
        redis_client = None # 確保 client 設為 None
    except Exception as e:
        print(f"CRITICAL ERROR initializing Redis client: {e}")
        redis_client = None
else:
    print("WARNING: REDIS_URL is not set. Conversation history will not be persistent.")
    # 如果 Redis 是必需的，你可以在這裡也讓應用啟動失敗

print("--------------------------")


MAX_CONVERSATION_HISTORY = 10  # 保留的 user/assistant 對話輪數
CONVERSATION_TTL = 86400 * 7   # Redis key 的過期時間 (7 天)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Shanghai Aesthetic Bot is running."}

@app.post("/webhook")
async def webhook(request: Request, x_line_signature: str = Header(None)):
    if not line_bot_api or not parser:
        print("Error: Line Bot SDK not initialized. Cannot process webhook.")
        raise HTTPException(status_code=500, detail="Line Bot SDK not initialized")

    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")

    try:
        events = parser.parse(body_str, x_line_signature)
    except InvalidSignatureError:
        print("Error: Invalid signature. Please check your channel secret and access token.")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        print(f"Error parsing webhook: {e}")
        raise HTTPException(status_code=500, detail="Error parsing webhook")

    for event in events:
        if not isinstance(event, MessageEvent) or not isinstance(event.message, TextMessage):
            continue

        user_id = event.source.user_id
        user_input = event.message.text
        print(f"Received message from user {user_id}: {user_input}")

        current_user_history = []

        if not redis_client:
            print("Warning: Redis client not available. Proceeding without conversation history.")
            # 降級處理：如果 Redis 不可用，則不使用歷史記錄
            current_user_history = [
                {"role": "system", "content": SHANGHAI_AESTHETIC_SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ]
            ai_reply_content = get_gpt_response(current_user_history)
        else:
            redis_key = f"conversation:{user_id}"
            try:
                # 1. 從 Redis 取得歷史
                cached_history = redis_client.get(redis_key)
                if cached_history:
                    current_user_history = json.loads(cached_history)
                    print(f"Retrieved history for {user_id} from Redis. Length: {len(current_user_history)}")
                else:
                    current_user_history = [
                        {"role": "system", "content": SHANGHAI_AESTHETIC_SYSTEM_PROMPT}
                    ]
                    print(f"No history found for {user_id}. Initializing.")
                
                # 2. 將用戶的最新訊息加入歷史
                current_user_history.append({"role": "user", "content": user_input})

                # 3. 控制歷史記錄長度 (System + N*2 messages)
                # 確保 System prompt 始終在第一個位置
                if len(current_user_history) > 1 + (MAX_CONVERSATION_HISTORY * 2):
                    system_prompt = current_user_history[0]
                    recent_exchanges = current_user_history[-(MAX_CONVERSATION_HISTORY * 2):]
                    current_user_history = [system_prompt] + recent_exchanges
                    print(f"History for {user_id} trimmed. New length: {len(current_user_history)}")


                # 4. 呼叫 GPT API
                ai_reply_content = get_gpt_response(current_user_history)
                
                # 5. 將 AI 的回覆加入歷史
                current_user_history.append({"role": "assistant", "content": ai_reply_content})
                # 再次修剪，以防 AI 回覆導致超長 (雖然通常不會一步到位，但保持邏輯完整)
                if len(current_user_history) > 1 + (MAX_CONVERSATION_HISTORY * 2):
                    system_prompt = current_user_history[0]
                    recent_exchanges = current_user_history[-(MAX_CONVERSATION_HISTORY * 2):]
                    current_user_history = [system_prompt] + recent_exchanges

                # 6. 將更新後的歷史存回 Redis
                redis_client.set(redis_key, json.dumps(current_user_history), ex=CONVERSATION_TTL)
                print(f"Updated history for {user_id} in Redis. TTL: {CONVERSATION_TTL}s")

            except redis.exceptions.RedisError as re:
                print(f"Redis Error for user {user_id}: {re}. Proceeding without saving history for this turn.")
                # Redis 錯誤時，本次可能無法儲存歷史，但仍嘗試回覆 (使用當前記憶體中的歷史)
                # 為了簡化，我們假設如果讀取歷史時出錯，則退回到無歷史模式
                # 如果是在寫入歷史時出錯，則用戶下次的歷史會是舊的
                # 這裡可以根據需求設計更複雜的重試或錯誤處理
                current_user_history_for_gpt = [ # 重新構建一個無 Redis 依賴的 messages
                    {"role": "system", "content": SHANGHAI_AESTHETIC_SYSTEM_PROMPT},
                    {"role": "user", "content": user_input}
                ]
                if len(current_user_history) > 1 : # 如果記憶體中至少有一輪user/assistant對話
                    # 嘗試使用記憶體中的最後一輪對話（如果有的話），但要小心這可能不完整
                    if current_user_history[-1]["role"] == "user": # 上一條是 user
                         current_user_history_for_gpt = current_user_history
                    elif len(current_user_history) > 2 and current_user_history[-2]["role"] == "user": # 上兩條是 user, assistant
                         current_user_history_for_gpt = current_user_history[:-1] # 去掉上次的 assistant 回覆

                ai_reply_content = get_gpt_response(current_user_history_for_gpt)
                # 這裡就不將 AI 的回覆加入記憶體的 current_user_history 了，因為下次還是會從 Redis 讀 (或失敗)

            except Exception as e:
                print(f"Unexpected error processing history for user {user_id}: {e}")
                # 通用錯誤，嘗試無歷史回覆
                ai_reply_content = get_gpt_response([
                    {"role": "system", "content": SHANGHAI_AESTHETIC_SYSTEM_PROMPT},
                    {"role": "user", "content": user_input}
                ])


        # 7. 回覆用戶
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=ai_reply_content)
            )
            print(f"Replied to user {user_id}: {ai_reply_content[:50]}...") # 只印出回覆的前50字
        except Exception as e:
            print(f"Error sending LINE reply to {user_id}: {e}")

    return "OK"
