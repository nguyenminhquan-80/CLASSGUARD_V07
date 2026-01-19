from flask import Flask, jsonify, render_template

# 1. Tạo app Flask - BẮT BUỘC
app = Flask(__name__)
app.secret_key = 'your-secret-key-123'  # Thay bằng key phức tạp của bạn

# 2. Định nghĩa ít nhất 1 route - BẮT BUỘC
@app.route('/')
def home():
    """Trang chủ hiển thị thông báo đơn giản"""
    return jsonify({
        "status": "success",
        "message": "🚀 CLASSGUARD V07 Đang Hoạt Động!",
        "api_endpoints": {
            "home": "/",
            "health": "/health",
            "dashboard": "/dashboard",
            "api_data": "/api/data"
        }
    })

@app.route('/health')
def health_check():
    """Endpoint cho Render health check"""
    return jsonify({"status": "healthy"}), 200

@app.route('/dashboard')
def dashboard():
    """Trang dashboard cơ bản"""
    return render_template('index.html')

@app.route('/api/data')
def api_data():
    """API trả về dữ liệu mẫu cho test"""
    sample_data = {
        "temperature": 28.5,
        "humidity": 65,
        "air_quality": 120,
        "light": 450,
        "sound": 55,
        "timestamp": "2024-01-19 10:30:00"
    }
    return jsonify(sample_data)

# 3. KHÔNG cần if __name__ == '__main__' khi chạy trên Render
# Render sẽ dùng gunicorn để chạy app
