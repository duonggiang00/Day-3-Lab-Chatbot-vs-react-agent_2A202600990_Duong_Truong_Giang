"""
Công cụ tư vấn PC cho GearVN - crawl Steam requirements và tìm sản phẩm trên gearvn.com
"""
import json
import re
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

GEARVN_BASE = "https://gearvn.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}

PC_BUDGET_COLLECTIONS = [
    (0, 30_000_000, "pc-gvn-duoi-30-trieu", "PC GVN dưới 30 triệu"),
    (30_000_000, 50_000_000, "pc-gvn-duoi-50-trieu", "PC GVN từ 30 - 50 triệu"),
    (50_000_000, 70_000_000, "pc-gvn-tu-50-70-trieu", "PC GVN từ 50 - 70 triệu"),
    (70_000_000, 100_000_000, "pc-gvn-tu-70-100-trieu", "PC GVN từ 70 - 100 triệu"),
    (100_000_000, 200_000_000, "pc-gvn-tu-100-200-trieu", "PC GVN từ 100 - 200 triệu"),
    (200_000_000, float("inf"), "pc-gvn-tren-200-trieu", "PC GVN trên 200 triệu"),
]

COMPONENT_TYPES = {
    "vga": ["VGA", "Card màn hình", "Card đồ họa"],
    "cpu": ["CPU", "Vi xử lý"],
    "ram": ["RAM", "Bộ nhớ"],
    "mainboard": ["Mainboard", "Bo mạch chủ"],
    "ssd": ["SSD", "Ổ cứng", "HDD"],
    "psu": ["Nguồn", "PSU"],
    "case": ["Case", "Vỏ máy"],
    "monitor": ["Màn hình"],
    "laptop": ["Laptop"],
}

_product_cache: Dict[str, Any] = {"products": [], "fetched_at": 0.0}
_handle_valid_cache: Dict[str, bool] = {}
CACHE_TTL_SECONDS = 3600

GEARVN_PRODUCT_URL_RE = re.compile(
    r"https?://(?:www\.)?gearvn\.com/products/([a-z0-9\-]+)/?",
    re.IGNORECASE,
)
TRAILING_URL_PUNCT = ".,;:!?)]}\"'"


def _format_price(price_str: str) -> str:
    try:
        amount = int(float(price_str))
        return f"{amount:,}₫".replace(",", ".")
    except (ValueError, TypeError):
        return str(price_str)


def _strip_trailing_url_punctuation(url: str) -> str:
    cleaned = url.strip()
    while cleaned and cleaned[-1] in TRAILING_URL_PUNCT:
        cleaned = cleaned[:-1]
    return cleaned


def _is_valid_product_handle(handle: str) -> bool:
    if not handle:
        return False
    if handle in _handle_valid_cache:
        return _handle_valid_cache[handle]
    data = _fetch_json(f"{GEARVN_BASE}/products/{handle}.json")
    ok = bool(data and data.get("product"))
    _handle_valid_cache[handle] = ok
    return ok


def _product_to_dict(product: dict) -> Optional[dict]:
    handle = (product.get("handle") or "").strip()
    if not handle:
        return None
    link = f"{GEARVN_BASE}/products/{handle}"

    variant = product.get("variants", [{}])[0]
    price_raw = variant.get("price", "0")
    compare = variant.get("compare_at_price")
    return {
        "name": product.get("title", ""),
        "handle": handle,
        "price": _format_price(price_raw),
        "price_vnd": int(float(price_raw)) if price_raw else 0,
        "compare_price": _format_price(compare) if compare else None,
        "link": link,
        "type": product.get("product_type", ""),
        "available": product.get("available", True),
        "vendor": product.get("vendor", ""),
    }


def collect_verified_links_from_json(payload: Any) -> List[str]:
    """Trích mọi link sản phẩm đã xác minh từ JSON observation."""
    links: List[str] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            link = obj.get("link")
            if isinstance(link, str) and "gearvn.com/products/" in link:
                links.append(link.split("?")[0].rstrip("/"))
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(payload)
    return links


def sanitize_gearvn_links(text: str, verified_urls: Optional[set] = None) -> str:
    """
    Sửa hoặc thay thế link sản phẩm GearVN không tồn tại trong câu trả lời.
    """
    verified = {u.rstrip("/") for u in (verified_urls or set())}

    def fix_product_url(url: str) -> str:
        url = _strip_trailing_url_punctuation(url)
        match = GEARVN_PRODUCT_URL_RE.search(url)
        if not match:
            return url
        handle = match.group(1)
        canonical = f"{GEARVN_BASE}/products/{handle}"
        if canonical in verified:
            return canonical
        if _is_valid_product_handle(handle):
            return canonical
        query = requests.utils.quote(handle.replace("-", " "))
        return f"{GEARVN_BASE}/search?q={query}"

    def fix_markdown_link(match: re.Match) -> str:
        label, url = match.group(1), _strip_trailing_url_punctuation(match.group(2))
        return f"[{label}]({fix_product_url(url)})"

    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+gearvn\.com/products/[^)\s]+)\)",
        fix_markdown_link,
        text,
    )
    return GEARVN_PRODUCT_URL_RE.sub(lambda m: fix_product_url(m.group(0)), text)


def _fetch_json(url: str, timeout: int = 20) -> Optional[dict]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        return {"error": str(exc)}


def _load_all_products(force_refresh: bool = False) -> List[dict]:
    now = time.time()
    if (
        not force_refresh
        and _product_cache["products"]
        and (now - _product_cache["fetched_at"]) < CACHE_TTL_SECONDS
    ):
        return _product_cache["products"]

    all_products: List[dict] = []
    page = 1
    while page <= 8:
        url = f"{GEARVN_BASE}/collections/all/products.json?limit=250&page={page}"
        data = _fetch_json(url)
        if not data or "error" in data:
            break
        batch = data.get("products", [])
        if not batch:
            break
        all_products.extend(batch)
        page += 1

    _product_cache["products"] = all_products
    _product_cache["fetched_at"] = now
    return all_products


def _parse_sysreq_section(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    result: dict = {"minimum": {}, "recommended": {}}

    sys_req = (
        soup.select_one(".game_area_sys_req")
        or soup.select_one("#game_area_sys_req")
        or soup.select_one(".game_area_sys_req_full")
    )
    if not sys_req:
        return result

    def _extract_specs(block) -> dict:
        specs = {}
        for li in block.select("li"):
            text = li.get_text(" ", strip=True)
            if ":" in text:
                key, val = text.split(":", 1)
                specs[key.strip()] = val.strip()
            elif text:
                specs[f"spec_{len(specs)}"] = text
        if not specs:
            raw = block.get_text("\n", strip=True)
            for line in raw.split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    specs[key.strip()] = val.strip()
        return specs

    blocks = sys_req.select(".sysreq_contents")
    if not blocks:
        blocks = sys_req.select(".game_area_sys_req_full, .sysreq_tab")

    if blocks:
        for block in blocks:
            label_el = block.select_one(".sysreq_header, h2, .sysreq_tab")
            label = (label_el.get_text(strip=True) if label_el else block.get("data-os", "")).lower()
            specs = _extract_specs(block)
            if not specs:
                continue
            if "minimum" in label or "tối thiểu" in label:
                result["minimum"] = specs
            elif "recommended" in label or "khuyến nghị" in label:
                result["recommended"] = specs
            elif not result["minimum"]:
                result["minimum"] = specs
            elif not result["recommended"]:
                result["recommended"] = specs
    else:
        result["minimum"] = _extract_specs(sys_req)

    return result


def crawl_steam_requirements(steam_url: str) -> str:
    """
    Crawl cấu hình tối thiểu/khuyến nghị từ trang Steam Store.
    """
    url = steam_url.strip()
    if not url.startswith("http"):
        url = f"https://store.steampowered.com/app/{url}/"

    app_match = re.search(r"/app/(\d+)", url)
    if not app_match:
        return json.dumps({"error": "URL Steam không hợp lệ. Ví dụ: https://store.steampowered.com/app/730/"}, ensure_ascii=False)

    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as exc:
        return json.dumps({"error": f"Không thể truy cập Steam: {exc}"}, ensure_ascii=False)

    soup = BeautifulSoup(resp.text, "lxml")
    title_el = soup.select_one(".apphub_AppName")
    game_name = title_el.get_text(strip=True) if title_el else f"App {app_match.group(1)}"

    specs = _parse_sysreq_section(resp.text)
    if not specs["minimum"] and not specs["recommended"]:
        return json.dumps(
            {
                "game_name": game_name,
                "steam_url": url,
                "error": "Không tìm thấy cấu hình hệ thống trên trang Steam.",
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "game_name": game_name,
            "steam_url": url,
            "minimum": specs["minimum"],
            "recommended": specs["recommended"] or specs["minimum"],
        },
        ensure_ascii=False,
    )


def format_steam_crawl_reply(crawl_json: str) -> str:
    """Chuyển JSON từ crawl_steam_requirements thành câu trả lời tiếng Việt."""
    try:
        data = json.loads(crawl_json)
    except json.JSONDecodeError:
        return "Không đọc được dữ liệu cấu hình từ Steam. Bạn thử gửi lại link nhé."

    if data.get("error") and not data.get("minimum"):
        return f"**Lỗi:** {data['error']}"

    game = data.get("game_name", "Game")
    steam_url = data.get("steam_url", "")
    lines = [f"### Cấu hình **{game}** (Steam)", ""]
    if steam_url:
        lines.append(f"Link: {steam_url}")
        lines.append("")

    minimum = data.get("minimum") or {}
    recommended = data.get("recommended") or {}

    if minimum:
        lines.append("**Tối thiểu:**")
        for key, val in minimum.items():
            lines.append(f"- **{key}:** {val}")
        lines.append("")

    if recommended and recommended != minimum:
        lines.append("**Khuyến nghị:**")
        for key, val in recommended.items():
            lines.append(f"- **{key}:** {val}")
        lines.append("")

    lines.append(
        "Để gợi ý **PC / linh kiện trên GearVN** phù hợp, bạn cho mình **ngân sách dự kiến** nhé "
        "(ví dụ: *25–30 triệu*, *40 triệu*)."
    )
    return "\n".join(lines)


def lookup_game_requirements(game_name: str) -> str:
    """
    Tra cứu cấu hình game theo tên (dùng Steam search).
    """
    query = game_name.strip()
    if not query:
        return json.dumps({"error": "Tên game không được để trống."}, ensure_ascii=False)

    search_url = f"https://store.steampowered.com/search/?term={requests.utils.quote(query)}&category1=998"
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as exc:
        return json.dumps({"error": f"Lỗi tìm kiếm Steam: {exc}"}, ensure_ascii=False)

    soup = BeautifulSoup(resp.text, "lxml")
    first_result = soup.select_one("#search_result_list a.search_result_row")
    if not first_result:
        return json.dumps(
            {"error": f"Không tìm thấy game '{query}' trên Steam."},
            ensure_ascii=False,
        )

    steam_url = first_result.get("href", "").split("?")[0]
    return crawl_steam_requirements(steam_url)


def search_gearvn_products(query: str, max_price: Optional[int] = None, limit: int = 8) -> str:
    """
    Tìm kiếm linh kiện/sản phẩm trên GearVN theo từ khóa.
    max_price: giá tối đa VND (ví dụ 15000000 = 15 triệu).
    """
    keyword = query.strip().lower()
    if not keyword:
        return json.dumps({"error": "Từ khóa tìm kiếm không được để trống."}, ensure_ascii=False)

    products = _load_all_products()
    matches: List[dict] = []

    for product in products:
        title = product.get("title", "").lower()
        body = (product.get("body_html") or "").lower()
        tags_raw = product.get("tags") or []
        if isinstance(tags_raw, str):
            tags = tags_raw.lower()
        elif isinstance(tags_raw, list):
            tags = " ".join(str(t) for t in tags_raw).lower()
        else:
            tags = str(tags_raw).lower()
        ptype = (product.get("product_type") or "").lower()

        if keyword not in title and keyword not in body and keyword not in tags and keyword not in ptype:
            continue

        item = _product_to_dict(product)
        if not item:
            continue
        if max_price and item["price_vnd"] > max_price:
            continue
        if not item["available"]:
            continue
        matches.append(item)

    matches.sort(key=lambda x: x["price_vnd"])
    results = matches[:limit]

    if not results:
        return json.dumps(
            {
                "query": query,
                "count": 0,
                "message": f"Không tìm thấy sản phẩm '{query}' trên GearVN.",
                "products": [],
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {"query": query, "count": len(results), "products": results},
        ensure_ascii=False,
    )


def get_gearvn_pc_by_budget(budget_vnd: int, limit: int = 5) -> str:
    """
    Lấy danh sách PC có sẵn trên GearVN phù hợp với ngân sách (VND).
    """
    try:
        budget = int(budget_vnd)
    except (ValueError, TypeError):
        return json.dumps({"error": "Ngân sách phải là số nguyên VND."}, ensure_ascii=False)

    if budget <= 0:
        return json.dumps({"error": "Ngân sách phải lớn hơn 0."}, ensure_ascii=False)

    collection_handle = PC_BUDGET_COLLECTIONS[0][2]
    collection_label = PC_BUDGET_COLLECTIONS[0][3]
    for low, high, handle, label in PC_BUDGET_COLLECTIONS:
        if low <= budget < high:
            collection_handle = handle
            collection_label = label
            break

    url = f"{GEARVN_BASE}/collections/{collection_handle}/products.json?limit=20"
    data = _fetch_json(url)
    if not data or "error" in data:
        return json.dumps({"error": "Không thể tải danh sách PC từ GearVN."}, ensure_ascii=False)

    pcs = []
    for product in data.get("products", []):
        item = _product_to_dict(product)
        if not item:
            continue
        if item["price_vnd"] <= budget * 1.1:
            pcs.append(item)

    pcs.sort(key=lambda x: abs(x["price_vnd"] - budget))
    pcs = pcs[:limit]

    return json.dumps(
        {
            "budget_vnd": budget,
            "budget_formatted": _format_price(str(budget)),
            "collection": collection_label,
            "count": len(pcs),
            "pcs": pcs,
        },
        ensure_ascii=False,
    )


def get_gearvn_product_detail(product_url: str) -> str:
    """
    Lấy chi tiết sản phẩm GearVN từ URL hoặc handle.
    """
    raw = product_url.strip()
    handle = raw
    if "gearvn.com" in raw:
        match = re.search(r"/products/([^/?#]+)", raw)
        if match:
            handle = match.group(1)
    handle = handle.strip("/")

    url = f"{GEARVN_BASE}/products/{handle}.json"
    data = _fetch_json(url)
    if not data or "error" in data:
        return json.dumps({"error": f"Không tìm thấy sản phẩm: {product_url}"}, ensure_ascii=False)

    product = data.get("product", {})
    if not product:
        return json.dumps({"error": f"Không tìm thấy sản phẩm: {product_url}"}, ensure_ascii=False)

    item = _product_to_dict(product)
    if not item:
        return json.dumps({"error": f"Sản phẩm không tồn tại hoặc đã ngừng bán: {product_url}"}, ensure_ascii=False)

    body = BeautifulSoup(product.get("body_html") or "", "lxml").get_text("\n", strip=True)
    item["description"] = body[:1500] if body else ""
    item["images"] = [img.get("src", "") for img in product.get("images", [])[:3]]

    return json.dumps(item, ensure_ascii=False)


def search_gearvn_by_category(category: str, max_price: Optional[int] = None, limit: int = 6) -> str:
    """
    Tìm linh kiện theo loại: vga, cpu, ram, mainboard, ssd, psu, case, monitor, laptop.
    """
    cat = category.strip().lower()
    type_keywords = COMPONENT_TYPES.get(cat)
    if not type_keywords:
        valid = ", ".join(COMPONENT_TYPES.keys())
        return json.dumps({"error": f"Loại không hợp lệ. Chọn một trong: {valid}"}, ensure_ascii=False)

    products = _load_all_products()
    matches: List[dict] = []

    for product in products:
        ptype = product.get("product_type", "")
        title = product.get("title", "")
        if not any(kw.lower() in ptype.lower() or kw.lower() in title.lower() for kw in type_keywords):
            continue
        item = _product_to_dict(product)
        if not item:
            continue
        if max_price and item["price_vnd"] > max_price:
            continue
        if not item["available"]:
            continue
        matches.append(item)

    matches.sort(key=lambda x: x["price_vnd"])
    results = matches[:limit]

    return json.dumps(
        {"category": category, "count": len(results), "products": results},
        ensure_ascii=False,
    )


GEARVN_TOOLS = [
    {
        "name": "crawl_steam_requirements",
        "description": (
            'crawl_steam_requirements(steam_url: str) -> JSON cấu hình tối thiểu/khuyến nghị từ link Steam. '
            'Ví dụ: crawl_steam_requirements("https://store.steampowered.com/app/730/")'
        ),
        "func": crawl_steam_requirements,
    },
    {
        "name": "lookup_game_requirements",
        "description": (
            'lookup_game_requirements(game_name: str) -> JSON cấu hình game theo tên. '
            'Ví dụ: lookup_game_requirements("Cyberpunk 2077")'
        ),
        "func": lookup_game_requirements,
    },
    {
        "name": "search_gearvn_products",
        "description": (
            'search_gearvn_products(query: str, max_price: int = None) -> JSON danh sách sản phẩm GearVN. '
            'max_price là giá tối đa VND. Ví dụ: search_gearvn_products("RTX 4060", 12000000)'
        ),
        "func": search_gearvn_products,
    },
    {
        "name": "get_gearvn_pc_by_budget",
        "description": (
            "get_gearvn_pc_by_budget(budget_vnd: int) -> JSON PC có sẵn phù hợp ngân sách VND. "
            "Ví dụ: get_gearvn_pc_by_budget(30000000)"
        ),
        "func": get_gearvn_pc_by_budget,
    },
    {
        "name": "get_gearvn_product_detail",
        "description": (
            'get_gearvn_product_detail(product_url: str) -> JSON chi tiết sản phẩm. '
            'Ví dụ: get_gearvn_product_detail("https://gearvn.com/products/pc-gvn-intel-i5-12400f")'
        ),
        "func": get_gearvn_product_detail,
    },
    {
        "name": "search_gearvn_by_category",
        "description": (
            'search_gearvn_by_category(category: str, max_price: int = None) -> JSON linh kiện theo loại '
            '(vga, cpu, ram, mainboard, ssd, psu, case, monitor, laptop). '
            'Ví dụ: search_gearvn_by_category("vga", 10000000)'
        ),
        "func": search_gearvn_by_category,
    },
]
