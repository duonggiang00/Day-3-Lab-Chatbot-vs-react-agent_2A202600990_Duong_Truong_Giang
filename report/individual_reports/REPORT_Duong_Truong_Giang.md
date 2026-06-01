# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Dương Trường Giang
- **Student ID**: 2A202600990
- **Date**: 01/06/2026

---

## I. Technical Contribution (15 Points)

Dự án được refactor từ demo e-commerce sang **G-BOT** — trợ lý tư vấn PC chơi game cho [GearVN](https://gearvn.com/), hỗ trợ cả chế độ **Chatbot** (LLM trực tiếp) và **ReAct Agent** (Thought → Action → Observation).

### Modules Implemented

| Module | Vai trò |
| :--- | :--- |
| `src/tools/gearvn_tools.py` | Crawl cấu hình Steam, tìm sản phẩm/PC qua Shopify JSON API GearVN, sanitize link |
| `src/guardrails/topic_guard.py` | Guardrail phạm vi (PC gaming), nhận diện link Steam/ngân sách |
| `src/agent/agent.py` | ReAct loop tiếng Việt, prompt tư vấn PC, quy tắc không bịa link |
| `src/server.py` | FastAPI `/api/chat`, routing chatbot/agent, fast-path crawl Steam |
| `src/core/provider_factory.py`, `openai_provider.py` | Tích hợp MiMo API (`tp-*` + Token Plan SGP) |
| `src/static/` (`index.html`, `app.js`, `style.css`) | UI G-BOT tiếng Việt, hiển thị reasoning steps |

### Code Highlights

**1. Crawl cấu hình Steam** — parse `.game_area_sys_req` từ trang Store:

```242:283:src/tools/gearvn_tools.py
def crawl_steam_requirements(steam_url: str) -> str:
    """
    Crawl cấu hình tối thiểu/khuyến nghị từ trang Steam Store.
    """
    # ... fetch HTML, parse minimum/recommended specs ...
    return json.dumps(
        {
            "game_name": game_name,
            "steam_url": url,
            "minimum": specs["minimum"],
            "recommended": specs["recommended"] or specs["minimum"],
        },
        ensure_ascii=False,
    )
```

**2. Fast-path trên server** — link Steam thuần crawl không cần LLM (tránh 429 MiMo):

```98:118:src/server.py
    if is_primarily_steam_link(user_message):
        steam_url = extract_steam_store_url(user_message) or user_message
        t0 = time.time()
        crawled = crawl_steam_requirements(steam_url)
        # ... trả về format_steam_crawl_reply + step crawl_steam_requirements
```

**3. ReAct prompt** — buộc agent gọi tool trước khi `Final Answer`, không bịa URL GearVN:

```54:63:src/agent/agent.py
Bạn PHẢI tuân thủ quy trình ReAct. KHÔNG trả lời cuối cùng nếu chưa gọi công cụ lấy dữ liệu thực.
QUY TẮC LINK (BẮT BUỘC):
- CHỈ được dùng trường "link" từ JSON Observation do hệ thống trả về.
- TUYỆT ĐỐI KHÔNG tự bịa URL, handle, tên sản phẩm hoặc giá.
```

### Documentation — Tương tác với ReAct loop

1. **User** gửi tin nhắn → `server.py` chạy `topic_guard` (on-topic, hỏi ngân sách, hoặc fast-path Steam).
2. **ReActAgent.run()** gọi LLM với system prompt + lịch sử `Thought/Action/Observation`.
3. Parser trích `Action: tool_name(args)` → thực thi hàm trong `GEARVN_TOOLS` → **Observation** (JSON) append vào prompt vòng sau.
4. Khi LLM xuất `Final Answer:` → `sanitize_gearvn_links()` loại link sai / dấu câu thừa → trả UI.

**Inventory công cụ agent:**

| Tool | Input | Use case |
| :--- | :--- | :--- |
| `crawl_steam_requirements` | URL Steam | Lấy cấu hình tối thiểu/khuyến nghị |
| `lookup_game_requirements` | Tên game | Tìm game trên Steam search rồi crawl |
| `get_gearvn_pc_by_budget` | `budget_vnd` (số) | PC có sẵn theo collection ngân sách GearVN |
| `search_gearvn_products` | query, max_price | Tìm linh kiện theo từ khóa |
| `search_gearvn_by_category` | category, max_price | VGA/CPU/RAM/... |
| `get_gearvn_product_detail` | URL sản phẩm | Chi tiết một SKU |

**LLM:** Primary **MiMo** (`mimo-v2.5-pro`, key `tp-*`, base URL Token Plan SGP). Đã thử **Gemini** nhưng gặp quota 429 free tier.

---

## II. Debugging Case Study (10 Points)

### Case 1: Mọi tin nhắn đều trả guardrail “G-BOT chỉ hỗ trợ…” (kể cả link Steam)

- **Problem Description**: Gửi `https://store.steampowered.com/app/513710/SCUM/` luôn nhận câu từ chối cố định, `steps: []`, `total_tokens: 0` — không crawl Steam, không gọi agent.
- **Log Source**: Response API có `latency_ms: 0`, không có `AGENT_START` / `LLM_RESPONSE` cho request đó; guard logic local (`is_on_topic` → `True`) nhưng API vẫn off-topic.
- **Diagnosis**: Trong `server.py`, decorator `@app.post("/api/chat")` gắn nhầm vào `_off_topic_payload()` thay vì `chat_endpoint()`. Mọi POST `/api/chat` chỉ trả `off_topic_response()` — **lỗi routing FastAPI**, không phải model hay prompt.
- **Solution**: Chuyển `@app.post("/api/chat")` sang `async def chat_endpoint(...)`. Thêm `is_primarily_steam_link()` để crawl Steam trực tiếp khi user chỉ gửi URL.

### Case 2: Agent chậm / lỗi 429 MiMo sau khi sửa routing

- **Problem Description**: Sau khi route đúng, agent chạy nhưng đôi lúc HTTP 429: `Too many requests`.
- **Log Source** (`logs/2026-06-01.log`):

```json
{"timestamp": "2026-06-01T10:22:09.903289", "event": "AGENT_START", "data": {"input": "https://store.steampowered.com/app/513710/SCUM/", "model": "mimo-v2.5-pro"}}
```

(kèm exception 429 khi gọi `provider.generate` trong test trực tiếp `chat_endpoint`)

- **Diagnosis**: Key MiMo Token Plan bị **rate limit** do test lặp nhiều lần; bước agent luôn cần LLM.
- **Solution**: Fast-path `crawl_steam_requirements` không qua LLM; xử lý 429 rõ ràng trong `server.py`; khuyên user đợi hoặc chỉ gửi link Steam.

### Case 3: `lookup_game_requirements("Counter-Strike 2")` thất bại → agent bỏ qua cấu hình Steam

- **Log Source**:

```json
{"event": "LLM_RESPONSE", "data": {"text": "Thought: Công cụ lookup không tìm thấy \"Counter-Strike 2\"... Action: get_gearvn_pc_by_budget(30000000)"}}
```

- **Diagnosis**: Tên game trên Steam search không khớp chuỗi tìm kiếm; agent chuyển sang PC theo ngân sách mà **không** gọi `crawl_steam_requirements` (dù CS2 có app id 730).
- **Solution**: Cập nhật prompt: nếu `lookup` fail → thử `crawl_steam_requirements` với URL Steam chuẩn (`/app/730/`). Log cho thấy lần chạy sau agent đã dùng đúng chuỗi: `lookup` → `crawl_steam` → `get_gearvn_pc_by_budget` (3 steps, thành công).

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

### 1. Reasoning — Vai trò khối `Thought`

Với **Chatbot**, model trả lời một lần dựa trên kiến thức nội tại → dễ **bịa giá/link** GearVN hoặc cấu hình game lỗi thời.

Với **ReAct Agent**, khối `Thought` buộc model **lập kế hoạch từng bước** (ví dụ: “tra CS2 trước → so sánh với ngân sách 30 triệu → gọi `get_gearvn_pc_by_budget`”). Log `2026-06-01T09:41:21` cho thấy một response chứa cả chuỗi Thought/Action/Observation hợp lệ trước `Final Answer` có bảng so sánh PC thật từ JSON tool.

`Thought` giúp **debug** (đọc log biết agent định làm gì) và **giảm nhảy cóc** sang câu trả lời cuối khi chưa có dữ liệu.

### 2. Reliability — Khi nào Agent kém hơn Chatbot?

| Tình huống | Chatbot | Agent |
| :--- | :--- | :--- |
| Câu hỏi đơn giản (“CS2 cần RAM bao nhiêu?”) | Nhanh, đủ dùng | Chậm hơn (2–4 lần gọi LLM + HTTP tool) |
| Rate limit API (429) | Một lần fail | Fail sau vài step, tốn token hơn |
| Tool/search lỗi tên game | Có thể đoán đúng từ training | Có thể **bỏ qua** bước crawl, chỉ dùng `get_gearvn_pc_by_budget` |
| Chỉ cần crawl Steam | Không có tool | Agent overkill; **server fast-path** tốt hơn cả hai |

Agent **tốt hơn** khi cần **đa bước có dữ liệu thật**: Steam + ngân sách + link sản phẩm (ví dụ Cyberpunk: `crawl_steam` → nhiều `search_gearvn_products` → bảng linh kiện ~20 triệu trong log `09:49:12`).

### 3. Observation — Ảnh hưởng đến bước tiếp theo

Observation (JSON từ GearVN/Steam) là **ground truth** cho vòng LLM sau:

- Sau `crawl_steam_requirements`, agent thấy RAM/GPU thật → chọn `get_gearvn_pc_by_budget` hoặc `search_gearvn_by_category("vga", ...)`.
- Khi Observation báo lỗi lookup CS2, agent (đôi khi) chuyển strategy — log cho thấy lần thành công dùng thêm `crawl_steam` app 730.
- Prompt “chỉ dùng link từ Observation” kết hợp `sanitize_gearvn_links` giảm link 404 do model tự ghép handle sai.

---

## IV. Future Improvements (5 Points)

- **Scalability**: Hàng đợi async cho tool (Steam crawl + GearVN API); cache Shopify `products.json` theo TTL; tách worker crawl khỏi API FastAPI.
- **Safety**: Supervisor LLM kiểm tra `Action` trước khi execute; giới hạn `max_steps` theo chi phí; validate tham số tool (budget > 0, URL whitelist `steampowered.com` / `gearvn.com`).
- **Performance**: Embedding + vector DB khi số tool > 10; giữ fast-path deterministic cho Steam-only; retry/backoff khi MiMo 429; fallback provider (OpenAI/Gemini) có circuit breaker.
- **Reliability**: Khi `lookup_game_requirements` fail → auto-retry với alias (CS2 → app 730); verify link GearVN bất đồng bộ thay vì tin LLM 100%.
- **UX**: Session memory (game + budget đã hỏi); hiển thị rõ “đang crawl Steam” vs “đang gọi AI” trên UI.

---

> Báo cáo nộp: `REPORT_Duong_Truong_Giang.md` trong `report/individual_reports/`.
