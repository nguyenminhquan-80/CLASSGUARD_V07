# CLASSGUARD - Hệ Thống Giám Sát Môi Trường Lớp Học Thông Minh

## Giới Thiệu Dự Án
Dự án "CLASSGUARD" là một hệ thống giám sát môi trường lớp học tự động sử dụng các cảm biến (nhiệt độ, độ ẩm, chất lượng không khí, ánh sáng, âm thanh) kết hợp với ESP32 và giao diện web để đánh giá tiết học.

## Tính Năng Chính
- 📊 Giám sát thời gian thực các thông số môi trường
- 📈 Hiển thị dữ liệu qua biểu đồ trực quan
- 🔔 Cảnh báo tự động và điều khiển từ xa
- 👨‍💻 Phân quyền người dùng (Admin/Viewer)
- 📱 Truy cập mọi lúc, mọi nơi qua web

## Công Nghệ Sử Dụng
- **Phần cứng:** ESP32-C3, cảm biến MQ135, DHT22, BH1750, INMP441
- **Backend:** Python Flask
- **Frontend:** HTML, CSS, JavaScript, Chart.js
- **Deployment:** Render.com
- **Database:** SQLite

## Cài Đặt & Sử Dụng
1. Clone repository: `git clone https://github.com/[username]/CLASSGUARD_V07.git`
2. Cài đặt thư viện: `pip install -r requirements.txt`
3. Chạy server: `python app.py`
4. Truy cập: `http://localhost:5000`

## Tác Giả
Nguyễn Minh Quân - tHCS Đông Hồ
