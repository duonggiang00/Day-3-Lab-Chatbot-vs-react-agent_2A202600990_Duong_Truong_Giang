import os
import sys
import time
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.provider_factory import get_llm_provider
from src.agent.agent import ReActAgent
from src.tools.gearvn_tools import (
    GEARVN_TOOLS,
    crawl_steam_requirements,
    format_steam_crawl_reply,
    sanitize_gearvn_links,
)
from src.telemetry.metrics import tracker
from src.guardrails.topic_guard import (
    SCOPE_RULES_PROMPT,
    ask_budget_response,
    extract_steam_store_url,
    is_on_topic,
    is_primarily_steam_link,
    off_topic_response,
    should_ask_for_budget,
)

load_dotenv()

app = FastAPI(title="GearVN PC Tư Vấn")

CHATBOT_SYSTEM_PROMPT = f"""Bạn là G-BOT - trợ lý tư vấn PC chơi game của GearVN (gearvn.com).
Nhiệm vụ: giúp khách chọn cấu hình PC / linh kiện phù hợp để chơi game theo ngân sách.

{SCOPE_RULES_PROMPT}

Quy tắc trả lời:
- Luôn trả lời bằng tiếng Việt, thân thiện và ngắn gọn.
- Chỉ tư vấn PC gaming và sản phẩm GearVN.
- Nếu khách chưa nêu ngân sách nhưng cần gợi ý PC, hãy hỏi mức giá (triệu VND) trước — đừng đoán ngân sách.
- Không bịa giá hoặc link sản phẩm."""

class ChatRequest(BaseModel):
    message: str
    mode: str  # "chatbot" or "agent"

def get_provider():
    try:
        return get_llm_provider()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.get("/api/status")
async def status_endpoint():
    try:
        _, provider_name, model_name = get_provider()
        return {
            "provider": provider_name,
            "model": model_name
        }
    except Exception as e:
        return {
            "provider": "unknown",
            "model": "unknown",
            "error": str(e)
        }

def _off_topic_payload(answer: str | None = None) -> dict:
    return {
        "answer": answer or off_topic_response(),
        "steps": [],
        "metrics": {
            "latency_ms": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
        },
    }


@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    user_message = (request.message or "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Tin nhắn không được để trống.")

    if not is_on_topic(user_message):
        return _off_topic_payload()

    if should_ask_for_budget(user_message):
        return _off_topic_payload(answer=ask_budget_response(user_message))

    if is_primarily_steam_link(user_message):
        steam_url = extract_steam_store_url(user_message) or user_message
        t0 = time.time()
        crawled = crawl_steam_requirements(steam_url)
        latency_ms = int((time.time() - t0) * 1000)
        return {
            "answer": format_steam_crawl_reply(crawled),
            "steps": [
                {
                    "step": 1,
                    "thought": "Người dùng gửi link Steam — crawl cấu hình trước khi hỏi ngân sách.",
                    "action": "crawl_steam_requirements",
                    "action_input": steam_url,
                    "observation": crawled[:2000],
                }
            ],
            "metrics": {
                "latency_ms": latency_ms,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost": 0.0,
            },
        }

    provider, provider_name, model_name = get_provider()
    
    try:
        if request.mode == "chatbot":
            # Run simple chatbot generate
            response = provider.generate(user_message, system_prompt=CHATBOT_SYSTEM_PROMPT)
            content = response["content"]
            usage = response["usage"]
            latency_ms = response["latency_ms"]
            
            # Simple chatbot has no reasoning steps
            steps = []
            
            # Track request in telemetry
            tracker.track_request(provider_name, model_name, usage, latency_ms)
            
            cost = tracker._calculate_cost(model_name, usage)
            
            return {
                "answer": sanitize_gearvn_links(content),
                "steps": steps,
                "metrics": {
                    "latency_ms": latency_ms,
                    "prompt_tokens": usage["prompt_tokens"],
                    "completion_tokens": usage["completion_tokens"],
                    "total_tokens": usage["total_tokens"],
                    "cost": cost
                }
            }
        
        elif request.mode == "agent":
            # Run ReAct Agent
            agent = ReActAgent(llm=provider, tools=GEARVN_TOOLS, max_steps=4)
            result = agent.run(user_message)
            
            # Aggregate metrics across all LLM steps
            total_prompt_tokens = 0
            total_completion_tokens = 0
            total_latency = 0
            
            for step in result["steps"]:
                usage = step.get("usage", {})
                total_prompt_tokens += usage.get("prompt_tokens", 0)
                total_completion_tokens += usage.get("completion_tokens", 0)
                total_latency += step.get("latency_ms", 0)
                
                # Also track each sub-request in the global logger
                tracker.track_request(provider_name, model_name, usage, step.get("latency_ms", 0))
                
            total_tokens = total_prompt_tokens + total_completion_tokens
            cost = (total_tokens / 1000) * 0.01  # Match the mock cost calculation
            
            return {
                "answer": result["answer"],
                "steps": result["steps"],
                "metrics": {
                    "latency_ms": total_latency,
                    "prompt_tokens": total_prompt_tokens,
                    "completion_tokens": total_completion_tokens,
                    "total_tokens": total_tokens,
                    "cost": cost
                }
            }
        else:
            raise HTTPException(status_code=400, detail="Invalid mode. Must be 'chatbot' or 'agent'")
            
    except Exception as e:
        err = str(e)
        if "429" in err:
            if "quota" in err.lower():
                detail = (
                    "Gemini đã hết quota free tier (20 request/ngày/model). "
                    "Đổi DEFAULT_PROVIDER=mimo trong .env, đợi quota reset, hoặc dùng OPENAI."
                )
            else:
                detail = (
                    "MiMo/API đang bị giới hạn tần suất (429). "
                    "Đợi vài phút rồi thử lại, hoặc gửi chỉ link Steam để crawl cấu hình không cần LLM."
                )
            raise HTTPException(status_code=429, detail=detail) from e
        if "401" in err and "invalid" in err.lower():
            raise HTTPException(
                status_code=401,
                detail=(
                    "API key không hợp lệ. Key tp-* cần MIMO_BASE_URL Token Plan; "
                    "key sk-* dùng https://api.xiaomimimo.com/v1. "
                    "Tạo key mới tại https://platform.xiaomimimo.com"
                ),
            ) from e
        raise HTTPException(status_code=500, detail=err) from e

# Setup Static Files directory serving
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:app", host="0.0.0.0", port=8000, reload=True)
