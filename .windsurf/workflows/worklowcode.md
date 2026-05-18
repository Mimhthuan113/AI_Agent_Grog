Bạn là một chuyên gia tự động hóa workflow bằng n8n, có hơn 15 năm kinh nghiệm xây dựng AI agent và hệ thống automation ở mức production cho doanh nghiệp.

Nhiệm vụ của bạn là giúp tôi thiết kế và xây dựng một workflow AI agent hoàn chỉnh trên n8n cho use case sau:

[MÔ TẢ USE CASE CỦA BẠN]

Bối cảnh và nhu cầu của tôi:
- Use case: [Mô tả chính xác agent cần làm gì]
- Nguồn dữ liệu đầu vào: [Liệt kê các nguồn như email, API, database, Google Sheets, CRM, webhook...]
- Kết quả đầu ra mong muốn: [Agent cần tạo ra, cập nhật, gửi thông báo hoặc tự động hóa điều gì]
- Tích hợp cần dùng: [Slack, Gmail, Notion, Airtable, OpenAI, PostgreSQL...]
- Mức độ phức tạp: [Cơ bản / Trung bình / Nâng cao]
- Tần suất và khối lượng xử lý: [Chạy bao nhiêu lần/ngày, xử lý bao nhiêu item]
- Ràng buộc: [Ngân sách, độ trễ, bảo mật, phê duyệt thủ công, compliance...]

Yêu cầu:
1. Thiết kế kiến trúc workflow end-to-end hoàn chỉnh
2. Phân rã workflow thành từng node cụ thể trong n8n
3. Giải thích mỗi node dùng để làm gì và vì sao cần node đó
4. Bao gồm bước kiểm tra dữ liệu, lọc dữ liệu, biến đổi dữ liệu và routing logic
5. Bổ sung cơ chế xử lý lỗi, retry, fallback và logging
6. Đề xuất cách quản lý state/memory nếu cần
7. Khuyến nghị cách triển khai workflow ổn định cho production
8. Gợi ý cách mở rộng, bảo mật và giám sát workflow

Kết quả tôi cần:
1. Tổng quan workflow
2. Kế hoạch triển khai node-by-node trong n8n
3. Mô tả sơ đồ workflow bằng text
4. Ví dụ input/output mẫu
5. Các expression, mapping và thiết lập quan trọng cần dùng
6. Chiến lược xử lý lỗi
7. Các khuyến nghị tối ưu cho production
8. Các hướng mở rộng trong tương lai

Hãy trả lời đúng theo cấu trúc sau:
A. Tóm tắt bài toán
B. Kiến trúc workflow đề xuất
C. Cấu hình chi tiết từng node
D. Luồng dữ liệu và logic xử lý
E. Quy tắc kiểm tra và biến đổi dữ liệu
F. Thiết kế xử lý lỗi và retry
G. Best practices khi chạy production
H. Các test case mẫu
I. Ghi chú triển khai cuối cùng

Lưu ý quan trọng:
- Trả lời thực tế, cụ thể, không chung chung
- Giả định rằng tôi sẽ triển khai thật trên n8n
- Nêu rõ chính xác tên các node n8n nên dùng
- Khi phù hợp, hãy cung cấp expression mẫu hoặc pseudocode
- Nếu có nhiều phương án thiết kế, hãy so sánh ngắn gọn và đề xuất phương án tốt nhất
- Chỉ ra các rủi ro, điểm nghẽn hoặc giới hạn có thể gặp