import ollama

response = ollama.chat(
    model="qwen3:4b",
    messages=[
        {
            "role": "user",
            "content": "전기차 열관리 시스템 개발 직무를 한 줄로 요약해줘."
        }
    ]
)

print(response["message"]["content"])