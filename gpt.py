import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")


def get_gpt_response(prompt: str) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
