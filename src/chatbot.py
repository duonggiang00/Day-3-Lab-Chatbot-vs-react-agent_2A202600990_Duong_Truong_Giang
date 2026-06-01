import os
import sys
from dotenv import load_dotenv

# Add project root to path if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.provider_factory import get_llm_provider
from src.telemetry.metrics import tracker
from src.telemetry.logger import logger
from src.guardrails.topic_guard import (
    SCOPE_RULES_PROMPT,
    ask_budget_response,
    is_on_topic,
    off_topic_response,
    should_ask_for_budget,
)

CHATBOT_SYSTEM_PROMPT = f"""Bạn là G-BOT - trợ lý tư vấn PC chơi game của GearVN.
{SCOPE_RULES_PROMPT}
Trả lời ngắn gọn bằng tiếng Việt."""

def run_chatbot():
    load_dotenv()
    
    try:
        provider, provider_name, model_name = get_llm_provider()
    except ValueError as exc:
        print(f"❌ Error: {exc}")
        return

    print(f"==================================================")
    print(f"🤖 Starting Chatbot Baseline...")
    print(f"Provider: {provider_name.upper()}")
    print(f"Model: {model_name}")
    print(f"==================================================")
    print("Type 'exit' or 'quit' to end the chat.\n")

    logger.log_event("CHATBOT_START", {"provider": provider_name, "model": model_name})

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            
            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            if not is_on_topic(user_input):
                print(off_topic_response())
                print("-" * 50)
                continue

            if should_ask_for_budget(user_input):
                print(ask_budget_response(user_input))
                print("-" * 50)
                continue
                
            print("Chatbot: ", end="", flush=True)
            
            response_data = provider.generate(user_input, system_prompt=CHATBOT_SYSTEM_PROMPT)
            
            content = response_data["content"]
            usage = response_data["usage"]
            latency_ms = response_data["latency_ms"]
            
            print(content)
            print(f"\n[Latency: {latency_ms}ms | Prompt Tokens: {usage['prompt_tokens']} | Completion Tokens: {usage['completion_tokens']}]")
            print("-" * 50)
            
            # Log metrics using our PerformanceTracker
            tracker.track_request(
                provider=provider_name,
                model=model_name,
                usage=usage,
                latency_ms=latency_ms
            )
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            logger.error(f"Chatbot execution error: {e}")

if __name__ == "__main__":
    run_chatbot()
