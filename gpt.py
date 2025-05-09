# gpt.py
import os
from openai import OpenAI # <--- 1. 修改 import

# 2. 初始化 OpenAI client
# 確保 OPENAI_API_KEY 環境變數已正確設定
# 最好在應用程式啟動時只初始化一次，但為簡單起見，我們先這樣處理
# 注意：如果 OPENAI_API_KEY 沒有設定，這裡的初始化或後續的 API 呼叫會失敗
try:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("CRITICAL ERROR: OPENAI_API_KEY environment variable not set. OpenAI calls will fail.")
        # 你可以選擇在這裡拋出異常，讓應用程式啟動失敗，以便更快發現問題
        # raise ValueError("OPENAI_API_KEY is not set")
        client = None # 或者設定為 None，並在下面檢查
    else:
        client = OpenAI(api_key=api_key)
        print("OpenAI client initialized successfully.")
except Exception as e:
    print(f"CRITICAL ERROR initializing OpenAI client: {e}")
    client = None # 發生錯誤時也設定為 None

def get_gpt_response(prompt: str) -> str:
    if not client:
        error_message = "OpenAI client is not initialized. Please check logs for API key issues."
        print(error_message)
        return error_message # 或者返回一個更友好的錯誤提示給用戶

    try:
        response = client.chat.completions.create( # <--- 3. 修改 API 呼叫方式
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        # 捕獲 API 呼叫時可能發生的錯誤
        print(f"Error during OpenAI API call: {e}")
        # 根據錯誤類型，你可能想返回不同的訊息
        # 例如，如果是 API金鑰無效，可以提示檢查金鑰
        # 如果是速率限制，可以提示稍後再試
        return "抱歉，我目前無法處理您的請求，請稍後再試。"