"""
Kiểm tra câu hỏi có thuộc phạm vi tư vấn build PC chơi game / GearVN hay không.
"""
import re
from typing import Optional

OFF_TOPIC_REPLY = """Xin lỗi, mình là **G-BOT** — chỉ hỗ trợ tư vấn **build PC chơi game** và sản phẩm trên [GearVN](https://gearvn.com).

Mình có thể giúp bạn:
- Chọn PC / linh kiện theo **ngân sách**
- Tra **cấu hình game** (link Steam hoặc tên game)
- Gợi ý **CPU, VGA, RAM, SSD** phù hợp trên GearVN

Ví dụ: *"PC 30 triệu chơi CS2"* hoặc gửi link Steam game bạn muốn chơi."""

SCOPE_RULES_PROMPT = """
PHẠM VI HỖ TRỢ (BẮT BUỘC):
- CHỈ trả lời câu hỏi về: build PC chơi game, cấu hình theo game, ngân sách PC, linh kiện (CPU/VGA/RAM/SSD/mainboard/nguồn/case/màn hình), PC/laptop gaming, sản phẩm GearVN.
- Có thể phân tích link Steam / tên game để đề xuất cấu hình.

NGOÀI PHẠM VI — TỪ CHỐI LỊCH SỰ, KHÔNG GỌI CÔNG CỤ:
- Thời tiết, tin tức, chính trị, sức khỏe, tình cảm, du lịch, ẩm thực, học tập không liên quan IT
- Lập trình / bài tập / công việc không liên quan PC gaming
- Mua bán điện thoại, tivi, đồ gia dụng (trừ khi hỏi về PC gaming)
- Yêu cầu viết code, dịch văn, làm bài hộ, tư vấn pháp lý/tài chính

Khi câu hỏi ngoài phạm vi, trả lời ngắn bằng tiếng Việt:
"Xin lỗi, mình chỉ tư vấn build PC chơi game và sản phẩm GearVN. Bạn có thể hỏi về ngân sách, tên game hoặc link Steam."
"""

GREETING_PATTERN = re.compile(
    r"^(xin\s*chào|chào|hello|hi|hey|chao)(\s|!|$)",
    re.IGNORECASE,
)

STEAM_STORE_URL_RE = re.compile(
    r"https?://(?:store\.)?steampowered\.com/app/\d+",
    re.IGNORECASE,
)

GEARVN_URL_RE = re.compile(
    r"https?://(?:www\.)?gearvn\.com/",
    re.IGNORECASE,
)

BUDGET_PATTERNS = (
    re.compile(r"\d+\s*tri[ệe]u", re.IGNORECASE),
    re.compile(r"\d+\s*tr\b", re.IGNORECASE),
    re.compile(r"\d+\s*củ", re.IGNORECASE),
    re.compile(r"\d+\s*cu\b", re.IGNORECASE),
    re.compile(r"ngân sách\s*[\d,.]+", re.IGNORECASE),
    re.compile(r"ngan sach\s*[\d,.]+", re.IGNORECASE),
    re.compile(r"(?:dưới|duoi|tầm|tam|khoảng|khoang|tối đa|toi da|max)\s*[\d,.]+\s*(?:tri[ệe]u|tr\b)?", re.IGNORECASE),
    re.compile(r"[\d,.]+\s*(?:-\s*[\d,.]+)?\s*tri[ệe]u", re.IGNORECASE),
    re.compile(r"\d{2,3}\s*m(?:\s|\.|$)", re.IGNORECASE),  # 30m, 50m (triệu)
)

PC_ADVICE_SIGNALS = (
    "build", "ráp", "rap", "lắp máy", "lap may", "mua pc", "tư vấn", "tu van",
    "gợi ý", "goi y", "đề xuất", "de xuat", "cần pc", "can pc", "nên mua", "nen mua",
    "chơi game", "choi game", "pc gaming", "cấu hình pc", "cau hinh pc",
)

GAME_HINTS = (
    "counter-strike", "cs2", "cs 2", "elden ring", "cyberpunk", "valorant",
    "gta", "pubg", "dota", "lol", "league of legends", "genshin", "fortnite",
    "minecraft", "red dead", "witcher", "baldur",
)

IN_SCOPE_KEYWORDS = (
    "pc", "máy tính", "may tinh", "build", "cấu hình", "cau hinh", "game", "steam",
    "vga", "gpu", "cpu", "ram", "mainboard", "main", "ssd", "hdd", "ổ cứng", "o cung",
    "nguồn", "nguon", "psu", "case", "vỏ", "vo", "màn hình", "man hinh", "monitor",
    "laptop", "linh kiện", "linh kien", "gearvn", "rtx", "gtx", "rx ", "ryzen", "intel",
    "chơi", "choi", "fps", "setting", "4k", "1440", "1080", "ngân sách", "ngan sach",
    "triệu", "trieu", "lắp máy", "lap may", "ráp máy", "rap may", "tư vấn pc", "tu van pc",
    "counter-strike", "elden", "cyberpunk", "valorant", "lol", "dota", "pubg", "genshin",
)

OFF_TOPIC_KEYWORDS = (
    "thời tiết", "thoi tiet", "nấu ăn", "nau an", "chính trị", "chinh tri",
    "bóng đá", "bong da", "ca sĩ", "ca si", "phim ", "du lịch", "du lich",
    "y tế", "y te", "bệnh", "benh", "tình yêu", "tinh yeu", "hẹn hò", "hen ho",
    "bitcoin", "crypto", "chứng khoán", "chung khoan", "làm bài", "lam bai",
    "viết văn", "viet van", "dịch ", "translate", "python code", "javascript",
    "toán học", "toan hoc", "văn học", "van hoc", "điện thoại iphone", "tivi samsung",
)


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def is_steam_store_url(message: str) -> bool:
    """True nếu tin nhắn chứa link Steam Store hợp lệ."""
    return bool(STEAM_STORE_URL_RE.search(message or ""))


def extract_steam_store_url(message: str) -> Optional[str]:
    match = STEAM_STORE_URL_RE.search(message or "")
    return match.group(0) if match else None


def is_primarily_steam_link(message: str) -> bool:
    """True khi tin nhắn gần như chỉ là link Steam (không kèm ngân sách / câu hỏi dài)."""
    if not is_steam_store_url(message):
        return False
    remainder = STEAM_STORE_URL_RE.sub("", message or "").strip(" .,;:-\n\t")
    return len(remainder) < 40


def is_gearvn_url(message: str) -> bool:
    return bool(GEARVN_URL_RE.search(message or ""))


def _has_in_scope_signal(text: str) -> bool:
    if is_steam_store_url(text) or "steamcommunity.com" in text:
        return True
    if is_gearvn_url(text) or "gearvn.com" in text:
        return True
    if has_budget_mentioned(text):
        return True
    return any(kw in text for kw in IN_SCOPE_KEYWORDS)


def _is_clearly_off_topic(text: str) -> bool:
    if any(kw in text for kw in OFF_TOPIC_KEYWORDS):
        return not _has_in_scope_signal(text)
    return False


def is_on_topic(message: str) -> bool:
    """True nếu câu hỏi thuộc phạm vi PC gaming / GearVN."""
    raw = (message or "").strip()
    if not raw:
        return False

    # Link Steam / GearVN luôn thuộc phạm vi (kể cả chỉ gửi URL)
    if is_steam_store_url(raw) or is_gearvn_url(raw):
        return True

    text = _normalize(raw)

    if GREETING_PATTERN.match(text) and len(text) < 40:
        return True

    if _is_clearly_off_topic(text):
        return False

    if _has_in_scope_signal(text):
        return True

    # Câu ngắn không rõ — để LLM xử lý với prompt phạm vi
    if len(text) < 80:
        return True

    return False


def off_topic_response() -> str:
    return OFF_TOPIC_REPLY


def has_budget_mentioned(message: str) -> bool:
    """True nếu tin nhắn có ngân sách / mức giá (triệu, tr, củ, khoảng X triệu...)."""
    text = _normalize(message)
    return any(p.search(text) for p in BUDGET_PATTERNS)


def _wants_pc_recommendation(text: str) -> bool:
    if is_steam_store_url(text) or "steamcommunity.com" in text:
        return True
    if "pc" in text or "máy tính" in text or "may tinh" in text:
        return True
    if any(k in text for k in PC_ADVICE_SIGNALS):
        return True
    if any(g in text for g in GAME_HINTS):
        return True
    if re.search(r"\bchơi\b|\bchoi\b", text) and "game" in text:
        return True
    return False


def should_ask_for_budget(message: str) -> bool:
    """
    True khi user cần tư vấn PC/game nhưng chưa nêu ngân sách.
    """
    text = _normalize(message)
    if not text or has_budget_mentioned(message):
        return False
    if GREETING_PATTERN.match(text) and len(text) < 50:
        return False
    # Link Steam: để agent crawl cấu hình game trước, hỏi ngân sách sau
    if is_steam_store_url(message):
        return False
    # Chỉ hỏi component cụ thể, không cần ngân sách build
    if re.search(r"\b(tìm|tim|search)\b", text) and any(
        k in text for k in ("vga", "cpu", "ram", "ssd", "mainboard", "nguồn", "psu")
    ):
        if "pc" not in text and not any(k in text for k in ("build", "ráp", "rap", "lắp")):
            return False
    return _wants_pc_recommendation(text)


def _detect_game_hint(message: str) -> str:
    text = _normalize(message)
    if "steampowered.com" in text:
        return "game trong link Steam bạn gửi"
    for game in GAME_HINTS:
        if game in text:
            return game.title()
    if re.search(r"chơi\s+([a-z0-9\s]{2,40})", text):
        match = re.search(r"chơi\s+([a-z0-9\s]{2,40})", text)
        if match:
            return match.group(1).strip().title()
    return ""


def ask_budget_response(message: str) -> str:
    game = _detect_game_hint(message)
    if game:
        return (
            f"Để tư vấn PC chơi **{game}** trên GearVN, bạn cho mình biết **ngân sách dự kiến** nhé?\n\n"
            "Ví dụ:\n"
            "- *15–20 triệu* (esports / game nhẹ)\n"
            "- *25–35 triệu* (AAA 1080p–1440p)\n"
            "- *40–50 triệu+* (high-end / tương lai)\n\n"
            "Bạn có thể trả lời: `30 triệu` hoặc `khoảng 25–30 triệu`."
        )
    return (
        "Để gợi ý **PC chơi game** phù hợp trên GearVN, bạn cho mình biết **ngân sách dự kiến** (triệu VND) nhé?\n\n"
        "Ví dụ: *20 triệu*, *30 triệu*, hoặc *25–35 triệu*.\n\n"
        "Sau đó mình sẽ đề xuất cấu hình và link sản phẩm cụ thể."
    )
