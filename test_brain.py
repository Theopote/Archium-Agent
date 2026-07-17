from archium.infrastructure.llm import LLMRequest, get_llm_provider


def main() -> None:
    provider = get_llm_provider()
    response = provider.generate_text(LLMRequest(system_prompt="", user_prompt="你好"))


if __name__ == "__main__":
    main()
