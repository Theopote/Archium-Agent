from config import GEMINI_MODEL, client


def main() -> None:
    response = client.chat.completions.create(
        model=GEMINI_MODEL,
        messages=[{"role": "user", "content": "你好"}],
    )
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
