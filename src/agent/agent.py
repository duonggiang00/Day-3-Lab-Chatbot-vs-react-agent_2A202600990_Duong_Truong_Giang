import json
import re
import ast
from typing import List, Dict, Any, Optional, Set
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.tools.gearvn_tools import collect_verified_links_from_json, sanitize_gearvn_links
from src.guardrails.topic_guard import (
    SCOPE_RULES_PROMPT,
    ask_budget_response,
    is_on_topic,
    off_topic_response,
    should_ask_for_budget,
)

class ReActAgent:
    """
    A ReAct-style Agent that follows the Thought-Action-Observation loop.
    Implements the core loop logic and tool execution.
    """
    
    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 5):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.history = []
        self.steps = []  # Store detailed steps for the UI

    def get_system_prompt(self) -> str:
        """
        Generates the system prompt instructing the agent to follow the ReAct framework in Vietnamese.
        """
        tool_descriptions = "\n".join([f"- {t['name']}: {t['description']}" for t in self.tools])
        return f"""Bạn là G-BOT - trợ lý tư vấn PC chơi game của GearVN (https://gearvn.com).
Bạn giúp khách hàng chọn PC/laptop/linh kiện phù hợp để chơi game, theo ngân sách, hoặc từ link Steam.

{SCOPE_RULES_PROMPT}

Công cụ có sẵn:
{tool_descriptions}

Quy trình tư vấn:
1. Nếu khách gửi link Steam → dùng crawl_steam_requirements.
2. Nếu khách nêu tên game → dùng lookup_game_requirements.
3. Phân tích cấu hình game → xác định CPU/RAM/VGA cần thiết.
4. Nếu khách gửi link Steam mà chưa có ngân sách:
   - Bước 1: crawl_steam_requirements(link)
   - Bước 2: Final Answer tóm tắt cấu hình game + hỏi ngân sách (KHÔNG gọi get_gearvn_pc_by_budget).
5. Nếu khách CHƯA nêu ngân sách (không có link Steam) → hỏi ngân sách trước.
6. Nếu đã có ngân sách (triệu VND × 1.000.000) → get_gearvn_pc_by_budget.
7. Tìm linh kiện cụ thể → search_gearvn_products hoặc search_gearvn_by_category.
8. Cần chi tiết sản phẩm → get_gearvn_product_detail.

Bạn PHẢI tuân thủ quy trình ReAct. KHÔNG trả lời cuối cùng nếu chưa gọi công cụ lấy dữ liệu thực.
TUYỆT ĐỐI KHÔNG đoán ngân sách (VD: 30 triệu) nếu khách chưa nói.

QUY TẮC LINK (BẮT BUỘC):
- CHỈ được dùng trường "link" từ JSON Observation do hệ thống trả về.
- TUYỆT ĐỐI KHÔNG tự bịa URL, handle, tên sản phẩm hoặc giá.
- KHÔNG viết dòng Observation — hệ thống sẽ điền sau mỗi Action.
- Mỗi sản phẩm đề xuất phải copy nguyên "name", "price", "link" từ Observation.
- Định dạng link: [Tên sản phẩm](link) — KHÔNG thêm dấu . ) , sau link trong ngoặc.
- Trả lời ngắn gọn, tối đa 2-3 sản phẩm chính.
- Nếu Observation không có sản phẩm phù hợp, nói rõ và gợi ý khách tìm trên gearvn.com.

Định dạng (giữ nguyên nhãn tiếng Anh):

Thought: <Suy luận bằng tiếng Việt>
Action: tên_công_cụ(tham_số)

Lặp lại khi cần. Khi đủ thông tin (sau khi đã có Observation thật):

Final Answer: <Tư vấn tiếng Việt, chỉ dùng link từ Observation>

Ví dụ ngân sách 30 triệu chơi CS2:
Thought: Khách muốn PC 30 triệu chơi CS2. Tôi tra cấu hình game trước.
Action: lookup_game_requirements("Counter-Strike 2")
Thought: CS2 cần RAM 8GB, VGA 1GB+. Tôi tìm PC GearVN trong tầm 30 triệu.
Action: get_gearvn_pc_by_budget(30000000)
Final Answer: Dựa trên cấu hình CS2 và ngân sách 30 triệu, GearVN có PC phù hợp... (kèm link)
"""


    def run(self, user_input: str) -> Dict[str, Any]:
        """
        Runs the ReAct loop:
        1. Generate Thought + Action.
        2. Parse Action and execute Tool.
        3. Append Observation to prompt and repeat until Final Answer or max_steps.
        Returns:
            Dict containing 'answer' and a list of 'steps' details.
        """
        logger.log_event("AGENT_START", {"input": user_input, "model": self.llm.model_name})

        if not is_on_topic(user_input):
            reply = off_topic_response()
            logger.log_event("AGENT_OFF_TOPIC", {"input": user_input})
            return {"answer": reply, "steps": []}

        if should_ask_for_budget(user_input):
            reply = ask_budget_response(user_input)
            logger.log_event("AGENT_ASK_BUDGET", {"input": user_input})
            return {"answer": reply, "steps": []}
        
        self.steps = []
        self.verified_links: Set[str] = set()
        system_prompt = self.get_system_prompt()
        current_prompt = f"User: {user_input}\n"
        
        steps_count = 0
        final_answer = ""
        tools_executed = 0
        
        while steps_count < self.max_steps:
            # Generate LLM response
            response = self.llm.generate(current_prompt, system_prompt=system_prompt)
            llm_text = response["content"].strip()
            
            logger.log_event("LLM_RESPONSE", {
                "text": llm_text, 
                "latency_ms": response["latency_ms"],
                "usage": response["usage"]
            })
            
            # Append LLM response to current prompt trace
            current_prompt += f"\n{llm_text}\n"
            
            # Parse Thought, Action and Final Answer
            thought_match = re.search(r"Thought:\s*(.*?)(?=(?:Action:|Final Answer:|$))", llm_text, re.DOTALL)
            thought = thought_match.group(1).strip() if thought_match else ""
            
            action_match = re.search(r"Action:\s*(\w+)\((.*?)\)", llm_text)
            final_match = re.search(r"Final Answer:\s*(.*)", llm_text, re.DOTALL)

            # Ưu tiên thực thi Action nếu LLM gộp Action + Final Answer trong một lượt
            if final_match and action_match:
                final_match = None
            
            if final_match:
                if tools_executed == 0 and "gearvn.com" in final_match.group(1).lower():
                    current_prompt += (
                        "\nObservation: Lỗi: Bạn chưa gọi công cụ GearVN. "
                        "Hãy gọi get_gearvn_pc_by_budget hoặc search_gearvn_products trước khi đưa link.\n"
                    )
                    steps_count += 1
                    continue

                final_answer = final_match.group(1).strip()
                self.steps.append({
                    "step": steps_count + 1,
                    "thought": thought,
                    "action": None,
                    "args": None,
                    "observation": None,
                    "final_answer": final_answer,
                    "usage": response["usage"],
                    "latency_ms": response["latency_ms"]
                })
                break
                
            elif action_match:
                tool_name = action_match.group(1).strip()
                tool_args_str = action_match.group(2).strip()
                
                # Execute Tool
                if tool_name == "get_gearvn_pc_by_budget" and should_ask_for_budget(user_input):
                    observation = (
                        "Lỗi: Khách chưa nêu ngân sách. "
                        "Hãy trả Final Answer hỏi ngân sách (triệu VND), không gọi lại công cụ này."
                    )
                else:
                    observation = self._execute_tool(tool_name, tool_args_str)
                tools_executed += 1
                self._collect_verified_links(observation)
                
                self.steps.append({
                    "step": steps_count + 1,
                    "thought": thought,
                    "action": tool_name,
                    "args": tool_args_str,
                    "observation": observation,
                    "final_answer": None,
                    "usage": response["usage"],
                    "latency_ms": response["latency_ms"]
                })
                
                # Append Observation back into the prompt history
                current_prompt += f"Observation: {observation}\n"
            else:
                # Fallback: if the LLM generated response without proper tags, return it as final answer
                final_answer = llm_text
                self.steps.append({
                    "step": steps_count + 1,
                    "thought": "LLM failed to follow strict formatting tags. Returning raw output.",
                    "action": None,
                    "args": None,
                    "observation": None,
                    "final_answer": final_answer,
                    "usage": response["usage"],
                    "latency_ms": response["latency_ms"]
                })
                break
                
            steps_count += 1
            
        if not final_answer:
            final_answer = "Agent exceeded maximum reasoning steps without producing a final answer."
        else:
            final_answer = sanitize_gearvn_links(final_answer, self.verified_links)
            
        logger.log_event("AGENT_END", {"steps": steps_count, "final_answer": final_answer})
        return {
            "answer": final_answer,
            "steps": self.steps
        }

    def _collect_verified_links(self, observation: str) -> None:
        try:
            payload = json.loads(observation)
        except json.JSONDecodeError:
            return
        for link in collect_verified_links_from_json(payload):
            self.verified_links.add(link.rstrip("/"))

    def _execute_tool(self, tool_name: str, args_str: str) -> str:
        """
        Helper method to execute tools by name. Parses string arguments safely using ast.literal_eval.
        """
        for tool in self.tools:
            if tool['name'] == tool_name:
                try:
                    # Parse arguments safely (handling tuples, strings, numbers, etc.)
                    if args_str.strip() == "":
                        return tool['func']()
                        
                    parsed_args = ast.literal_eval(f"({args_str})")
                    if not isinstance(parsed_args, tuple):
                        args = [parsed_args]
                    else:
                        args = list(parsed_args)
                        
                    return tool['func'](*args)
                except Exception as e:
                    return f"Error executing tool {tool_name} with arguments ({args_str}): {str(e)}"
                    
        return f"Tool {tool_name} not found."
