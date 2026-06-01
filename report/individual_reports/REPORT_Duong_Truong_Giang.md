# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Dương Trường Giang
- **Student ID**: 2A202600990
- **Date**: 01/06/2026

---

## I. Technical Contribution (15 Points)

### Sản phẩm làm được gì?

Em xây **G-BOT** — chatbot tư vấn PC chơi game trên website GearVN. Khách có thể:

- Gửi **link Steam** của game → bot đọc cấu hình tối thiểu / khuyến nghị.
- Nói **ngân sách** (ví dụ: *30 triệu*) → bot gợi ý PC có sẵn trên GearVN kèm **giá và link mua thật**.
- Hỏi **tên game + ngân sách** → bot so sánh “game cần gì” với “máy nào trong tầm tiền”.
- Chỉ hỏi linh kiện (VGA, RAM…) → bot tìm sản phẩm phù hợp trên shop.

Giao diện tiếng Việt, có hai chế độ: **Chatbot** (trả lời nhanh, một lần) và **ReAct Agent** (suy nghĩ từng bước, gọi “công cụ” lấy dữ liệu thật rồi mới tư vấn).

### Em đóng góp cụ thể

| Phần việc | Ý nghĩa thực tế |
| :--- | :--- |
| Lấy cấu hình từ Steam | Khách không cần tự mở trang Steam, copy CPU/RAM/VGA |
| Gắn catalog GearVN | Giá và link sản phẩm lấy từ shop, không “đoán” |
| Quy tắc phạm vi (guardrail) | Bot từ chối lịch sự câu ngoài PC gaming (thời tiết, làm bài…) |
| Hỏi ngân sách khi thiếu | Tránh gợi ý PC sai tầm giá |
| Giao diện web đơn giản | Khách chat như Zalo/Messenger, xem được bot đang “nghĩ” bước nào |

### Luồng tư vấn (dễ hình dung)

1. Khách nhắn tin → hệ thống kiểm tra có đúng chủ đề PC/game không.
2. Nếu chỉ gửi link Steam → bot **đọc cấu hình game ngay** (không cần AI), rồi hỏi ngân sách.
3. Nếu đã có game + ngân sách → **Agent** lần lượt: tra game → tìm PC trên GearVN → tổng hợp lời khuyên.
4. Câu trả lời cuối chỉ dùng link sản phẩm đã lấy từ shop (hạn chế link sai / 404).

### Công cụ agent hỗ trợ (bản đơn giản)

| Công cụ | Khách hưởng lợi gì |
| :--- | :--- |
| Đọc link Steam | Biết game nặng hay nhẹ, cần RAM/VGA thế nào |
| Tìm theo tên game | Không bắt buộc phải có link |
| PC theo ngân sách | 2–3 bộ máy có sẵn, đúng túi tiền |
| Tìm linh kiện | Tự ráp hoặc nâng cấp từng phần |

---

## II. Debugging Case Study (10 Points)

### Case 1: Gửi link Steam mà bot vẫn “từ chối”

- **Triệu chứng**: Khách dán link SCUM, bot trả lời cố định: *“Mình chỉ hỗ trợ build PC…”* — trong khi chính bot cũng ghi là hỗ trợ link Steam.
- **Cảm nhận người dùng**: Bot “không hiểu” hoặc “hỏng”, mất niềm tin ngay lượt đầu.
- **Nguyên nhân (đã tìm ra)**: Lỗi cấu hình server — mọi tin nhắn đều đi vào hàm trả lời từ chối, **không** vào logic chat thật. Không phải do AI “ngu”.
- **Cách xử lý**: Sửa đúng điểm nhận tin nhắn API; thêm luồng: **chỉ link Steam** thì đọc cấu hình trước, hỏi ngân sách sau.
- **Bài học**: Nên test bằng **một link Steam đơn giản** sau mỗi lần deploy; nếu trả lời giống hệt mọi câu → nghi lỗi hệ thống trước, nghi AI sau.

### Case 2: Bot báo “quá nhiều request” (429)

- **Triệu chứng**: Sau vài lần thử, bot báo giới hạn API MiMo.
- **Cảm nhận người dùng**: Chờ lâu hoặc không dùng được dù câu hỏi hợp lệ.
- **Nguyên nhân**: Gói API có giới hạn số lần gọi/phút; test nhiều + Agent gọi AI nhiều vòng làm hết quota nhanh.
- **Cách xử lý**: Link Steam chỉ crawl (miễn phí hơn); thông báo lỗi rõ “đợi vài phút”; hạn chế bấm gửi liên tục khi demo.
- **Bài học**: Tính năng **không cần AI** (đọc Steam) nên tách riêng — vẫn có giá trị khi AI tạm lỗi.

### Case 3: Hỏi “Counter-Strike 2” nhưng bot bỏ qua cấu hình game

- **Triệu chứng**: Bot nhảy thẳng sang gợi ý PC 30 triệu, ít nhắc cấu hình CS2.
- **Nguyên nhân**: Tên game trên Steam đôi khi khó khớp (CS2 / Counter-Strike 2); bot chọn đường tắt “tìm PC theo tiền”.
- **Cách xử lý**: Dạy bot trong prompt: tìm tên không được → thử link Steam chuẩn (app 730). Lần chạy sau: tra game → đọc Steam → mới gợi ý PC — kết quả đầy đủ hơn.
- **Bài học**: Cần **vài câu mẫu** tên game khó (CS2, PUBG…) để kiểm tra trước khi giao cho khách.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

### 1. Reasoning — “Suy nghĩ” có giúp khách không?

**Chatbot** giống nhân viên trả lời ngay một lần — nhanh nhưng dễ **đoán giá, đoán link** nếu không tra kho.

**ReAct Agent** giống nhân viên nói: *“Để em xem cấu hình game trước… em tìm PC trong tầm 30 triệu…”* — khách thấy từng bước trên màn hình, dễ tin hơn khi cuối cùng có bảng so sánh 2–3 PC với giá GearVN.

**Ý tưởng thực tế**: Trên shop, nên hiển thị 2–3 dòng “Đang kiểm tra game… Đang lọc PC theo ngân sách…” thay vì chỉ hiện loading chung — giảm cảm giác bot “bịa”.

### 2. Reliability — Khi nào nên dùng mode nào?

| Tình huống khách | Nên dùng | Vì sao |
| :--- | :--- | :--- |
| “CS2 cần RAM bao nhiêu?” | Chatbot | Một câu, không cần tra shop |
| “30 triệu chơi Elden Ring, gợi ý PC GearVN” | Agent | Cần game + giá + link thật |
| Chỉ gửi link Steam | Đọc Steam trực tiếp | Nhanh, không tốn AI |
| Khách gõ liên tục khi demo | Chatbot hoặc tắt Agent | Agent chậm và tốn quota |

**Khi Agent tệ hơn Chatbot**: Câu ngắn, khẩn cấp; mạng/API chậm; khách chỉ cần ý tưởng sơ bộ, chưa cần mua ngay.

**Khi Agent tốt hơn rõ rệt**: Cần **nhiều nguồn** (Steam + catalog + ngân sách) trong một câu trả lời — ví dụ Cyberpunk: cấu hình game + bảng linh kiện ~20 triệu + link từng món.

### 3. Observation — Phản hồi từ “thế giới thật”

Mỗi bước agent nhận **kết quả thật** (giá PC, cấu hình Steam), không chỉ “trí nhớ” AI:

- Biết game cần 16GB RAM → không gợi ý PC 8GB.
- Biết shop có PC 28,9 triệu → không nói 25 triệu bừa.
- Tìm game lỗi → đổi cách tra (link Steam) thay vì bịa.

**Ý tưởng thực tế cho GearVN**: Cuối mỗi tư vấn, thêm nút *“Xem PC đề xuất”* / *“Chat với nhân viên”* — bot mở đường, người chốt đơn.

---

## IV. Future Improvements (5 Points)

*Hướng cải thiện gắn với trải nghiệm khách và vận hành shop — không đi sâu stack kỹ thuật.*

### Trải nghiệm khách hàng

- **Nhớ cuộc chat ngắn**: Khách đã gửi link SCUM + 30 triệu thì lượt sau không hỏi lại từ đầu.
- **Gợi ý câu mẫu** trên UI: *“PC 25–30 triệu chơi Valorant”*, *“Gửi link Steam game”*.
- **So sánh 2 PC cạnh nhau** (giá, VGA, “dư / thiếu so với game”) — dễ quyết định hơn đoạn văn dài.

### Niềm tin & an toàn

- Chỉ link **gearvn.com** và **steampowered.com**; cảnh báo nếu bot sắp trả lời ngoài phạm vi PC.
- Ghi chú *“Giá cập nhật lúc …, vui lòng kiểm tra trên web”* — tránh khiếu nại sai giá.

### Vận hành & chi phí

- Giờ cao điểm: ưu tiên câu có link Steam (ít tốn AI).
- Giới hạn số lượt chat/phút mỗi IP khi demo công khai.
- Báo cáo đơn giản cho team: *hôm nay bao nhiêu % câu có ngân sách, game nào được hỏi nhiều*.

### Mở rộng sản phẩm (ý tưởng kinh doanh)

- Gợi ý thêm **màn hình 144Hz** khi khách build PC esports (CS2, Valorant).
- Combo **PC + màn hình + tai nghe** trong cùng ngân sách.
- Tích hợp **khuyến mãi / trả góp** từ GearVN vào câu trả lời (nếu API shop có).

### Đo lường thành công

- Khách có **click link sản phẩm** sau tư vấn không?
- Tỷ lệ câu trả lời có **đủ: game + ngân sách + ≥1 link**?
- Khảo sát 1 câu sau chat: *“Bot có giúp bạn chọn được PC không?”* (có / chưa / cần nhân viên)

---

> Báo cáo nộp: `REPORT_Duong_Truong_Giang.md` trong `report/individual_reports/`.
