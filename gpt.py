# gpt.py
import os
from openai import OpenAI

try:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("CRITICAL ERROR: OPENAI_API_KEY environment variable not set. OpenAI calls will fail.")
        client = None
    else:
        client = OpenAI(api_key=api_key)
        print("OpenAI client initialized successfully.")
except Exception as e:
    print(f"CRITICAL ERROR initializing OpenAI client: {e}")
    client = None

# --- 在這裡定義你的「預設語料」或「系統提示」 ---
DEFAULT_SYSTEM_PROMPT = """
你是一個樂於助人且知識淵博的 AI 助理。
你的目標是用清晰、簡潔且友好的方式回答用戶的問題。
請盡量提供準確的資訊。
如果遇到不知道答案的問題，請誠實告知，不要編造答案。
請使用繁體中文回答。
"""
# 你可以根據你的需求修改上面的 DEFAULT_SYSTEM_PROMPT

def get_gpt_response(prompt: str, system_message: str = DEFAULT_SYSTEM_PROMPT) -> str:
    if not client:
        error_message = "OpenAI client is not initialized. Please check logs for API key issues."
        print(error_message)
        return error_message

    try:
        messages = [
            {"role": "system", "content": system_message}, # <--- 你的預設語料/系統提示
            {"role": "user", "content": prompt}           # <--- 用戶的實際輸入
        ]
        # 你也可以在這裡根據需要加入更多的 user/assistant 訊息來構造更長的對話歷史

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages
            # 你可以在這裡加入其他參數，如 temperature, max_tokens 等
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error during OpenAI API call: {e}")
        # 根據錯誤類型，你可能想返回不同的訊息
        # 例如，如果是 API金鑰無效或配額問題，可以提示檢查
        return "抱歉，我目前無法處理您的請求，請稍後再試。錯誤詳情請查看伺服器日誌。"