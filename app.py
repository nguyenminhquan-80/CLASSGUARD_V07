# app.py - Phiên bản tối giản để TEST
from flask import Flask, render_template, jsonify

app = Flask(__name__)
app.secret_key = 'classguard-secret-key-2024' # Thay bằng chuỗi bí mật phức tạp của bạn

# Route trang chủ đơn giản
@app.route('/')
def home():
    return "<h1>CLASSGUARD Server Đang Hoạt Động!</h1><p>Kết nối thành công tới Render.</p>"

# Route API test trả về dữ liệu mẫu
@app.route('/api/data')
def api_data():
    # Dữ liệu giả lập để test biểu đồ
    sample_data = {
        "temperature": 28.5,
        "humidity": 65,
        "air_quality": 120,
        "light": 450,
        "sound": 55
    }
    return jsonify(sample_data)

if __name__ == '__main__':
    app.run(debug=True)