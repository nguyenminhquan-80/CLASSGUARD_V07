from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import sqlite3
import json
from datetime import datetime, timedelta
import os

# ========== KHỞI TẠO APP ==========
app = Flask(__name__)
app.secret_key = 'classguard-secret-key-' + os.urandom(16).hex()

# ========== DATABASE ĐƠN GIẢN (SQLite) ==========
def init_db():
    """Khởi tạo database"""
    conn = sqlite3.connect('classguard.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Tạo bảng users nếu chưa có
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    
    # Tạo bảng sensor_data
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            temperature REAL,
            humidity REAL,
            air_quality REAL,
            light REAL,
            sound REAL
        )
    ''')
    
    # Thêm user mẫu nếu chưa có
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                      ('admin', 'admin123', 'admin'))
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                      ('user', 'user123', 'viewer'))
    
    conn.commit()
    return conn

# Khởi tạo database ngay khi import
db_conn = init_db()

# ========== FLASK-LOGIN ==========
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Vui lòng đăng nhập'
login_manager.login_message_category = 'info'

class User(UserMixin):
    def __init__(self, id, username, password, role):
        self.id = id
        self.username = username
        self.password = password
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()
    if user_data:
        return User(user_data[0], user_data[1], user_data[2], user_data[3])
    return None

# ========== TRANG ĐĂNG NHẬP CHUYÊN NGHIỆP ==========
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Trang đăng nhập không hiển thị tài khoản mẫu"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        cursor = db_conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user_data = cursor.fetchone()
        
        if user_data and user_data[2] == password:  # user_data[2] là password
            user = User(user_data[0], user_data[1], user_data[2], user_data[3])
            login_user(user, remember=remember)
            flash('✅ Đăng nhập thành công!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('❌ Tên đăng nhập hoặc mật khẩu không đúng', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('👋 Đã đăng xuất thành công', 'info')
    return redirect(url_for('login'))

# ========== DASHBOARD CHÍNH ==========
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard chính với tất cả chức năng"""
    # Lấy dữ liệu mới nhất
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 1")
    latest_data = cursor.fetchone()
    
    # Đánh giá
    evaluation = evaluate_classroom(latest_data) if latest_data else None
    
    return render_template('dashboard.html',
                         username=current_user.username,
                         role=current_user.role,
                         latest_data=latest_data,
                         evaluation=evaluation)

# ========== API DỮ LIỆU ==========
@app.route('/api/current-data')
@login_required
def get_current_data():
    """API trả về dữ liệu hiện tại"""
    cursor = db_conn.cursor()
    cursor.execute('''
        SELECT temperature, humidity, air_quality, light, sound, 
               strftime('%Y-%m-%d %H:%M:%S', timestamp) 
        FROM sensor_data 
        ORDER BY timestamp DESC LIMIT 1
    ''')
    data = cursor.fetchone()
    
    if data:
        return jsonify({
            'temperature': data[0],
            'humidity': data[1],
            'air_quality': data[2],
            'light': data[3],
            'sound': data[4],
            'timestamp': data[5],
            'status': 'success'
        })
    else:
        # Dữ liệu mẫu cho demo
        return jsonify({
            'temperature': 26.5,
            'humidity': 65.2,
            'air_quality': 145,
            'light': 420,
            'sound': 48.3,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'demo'
        })

@app.route('/api/historical-data')
@login_required
def get_historical_data():
    """API dữ liệu lịch sử cho biểu đồ"""
    hours = request.args.get('hours', 24, type=int)
    
    cursor = db_conn.cursor()
    cursor.execute(f'''
        SELECT strftime('%H:%M', timestamp), temperature, humidity, air_quality, light, sound
        FROM sensor_data 
        WHERE timestamp > datetime('now', '-{hours} hours')
        ORDER BY timestamp
    ''')
    
    data = cursor.fetchall()
    
    if data:
        timestamps = [row[0] for row in data]
        temperatures = [row[1] for row in data]
        humidities = [row[2] for row in data]
        air_quality = [row[3] for row in data]
        light = [row[4] for row in data]
        sound = [row[5] for row in data]
    else:
        # Dữ liệu mẫu
        timestamps = ['10:00', '11:00', '12:00', '13:00', '14:00']
        temperatures = [26.0, 26.5, 27.0, 26.8, 26.3]
        humidities = [60, 62, 65, 63, 61]
        air_quality = [120, 135, 145, 130, 125]
        light = [400, 420, 410, 430, 425]
        sound = [45, 48, 50, 47, 46]
    
    return jsonify({
        'timestamps': timestamps,
        'temperature': temperatures,
        'humidity': humidities,
        'air_quality': air_quality,
        'light': light,
        'sound': sound
    })

@app.route('/api/save-data', methods=['POST'])
def save_sensor_data():
    """API nhận dữ liệu từ ESP32"""
    try:
        data = request.json
        cursor = db_conn.cursor()
        cursor.execute('''
            INSERT INTO sensor_data (temperature, humidity, air_quality, light, sound)
            VALUES (?, ?, ?, ?, ?)
        ''', (data.get('temp', 0), data.get('humidity', 0), 
              data.get('air', 0), data.get('light', 0), data.get('sound', 0)))
        db_conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

# ========== ĐÁNH GIÁ LỚP HỌC ==========
def evaluate_classroom(data):
    """Đánh giá chất lượng lớp học"""
    if not data:
        return {'score': 0, 'rating': 'Chưa có dữ liệu', 'feedback': []}
    
    temp, humidity, air, light, sound = data[2:7]
    score = 0
    feedback = []
    
    # Nhiệt độ (23-27°C lý tưởng)
    if 23 <= temp <= 27:
        score += 20
        feedback.append("🌡 Nhiệt độ lý tưởng")
    elif 20 <= temp < 23 or 27 < temp <= 30:
        score += 10
        feedback.append("🌡 Nhiệt độ chấp nhận được")
    else:
        feedback.append("🌡 Nhiệt độ không phù hợp")
    
    # Độ ẩm (40-70% lý tưởng)
    if 40 <= humidity <= 70:
        score += 20
        feedback.append("💧 Độ ẩm tốt")
    else:
        feedback.append("💧 Độ ẩm cần điều chỉnh")
    
    # Chất lượng không khí
    if air < 200:
        score += 20
        feedback.append("💨 Không khí trong lành")
    elif 200 <= air < 400:
        score += 10
        feedback.append("💨 Không khí bình thường")
    else:
        feedback.append("💨 Cần thông gió")
    
    # Ánh sáng (300-500 lux)
    if 300 <= light <= 500:
        score += 20
        feedback.append("💡 Ánh sáng tốt")
    else:
        feedback.append("💡 Ánh sáng cần điều chỉnh")
    
    # Âm thanh (<60 dB tốt)
    if sound < 60:
        score += 20
        feedback.append("🔇 Môi trường yên tĩnh")
    elif 60 <= sound < 70:
        score += 10
        feedback.append("🔊 Âm thanh chấp nhận được")
    else:
        feedback.append("🔊 Ồn ào, khó tập trung")
    
    # Xếp loại
    if score >= 80:
        rating = "🏆 Xuất sắc"
        color = "success"
    elif score >= 60:
        rating = "✅ Tốt"
        color = "primary"
    elif score >= 40:
        rating = "⚠️ Trung bình"
        color = "warning"
    else:
        rating = "❌ Cần cải thiện"
        color = "danger"
    
    return {
        'score': score,
        'rating': rating,
        'color': color,
        'feedback': feedback
    }

# ========== ĐIỀU KHIỂN THIẾT BỊ ==========
device_status = {'fan': False, 'light': True, 'alert': False}

@app.route('/api/control', methods=['POST'])
@login_required
def control_device():
    """Điều khiển thiết bị"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Không có quyền'}), 403
    
    data = request.json
    device = data.get('device')
    state = data.get('state')
    
    if device in device_status:
        device_status[device] = state
        return jsonify({
            'status': 'success',
            'device': device,
            'state': state,
            'message': f'Đã {"bật" if state else "tắt"} {device}'
        })
    
    return jsonify({'error': 'Thiết bị không tồn tại'}), 400

@app.route('/api/devices')
@login_required
def get_devices():
    """Lấy trạng thái thiết bị"""
    return jsonify(device_status)

# ========== DỮ LIỆU & BÁO CÁO ==========
@app.route('/data')
@login_required
def data_page():
    """Trang xem dữ liệu"""
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 100")
    records = cursor.fetchall()
    return render_template('data.html', records=records, username=current_user.username)

@app.route('/export/csv')
@login_required
def export_csv():
    """Xuất CSV"""
    import csv
    from io import StringIO
    
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC")
    data = cursor.fetchall()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Thời gian', 'Nhiệt độ (°C)', 'Độ ẩm (%)', 
                     'Chất lượng KK', 'Ánh sáng (lux)', 'Âm thanh (dB)'])
    
    for row in data:
        writer.writerow([row[1], row[2], row[3], row[4], row[5], row[6]])
    
    from flask import make_response
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=classguard_{datetime.now().strftime("%Y%m%d")}.csv'
    return response

# ========== HEALTH CHECK ==========
@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'time': datetime.now().isoformat()})

# ========== ERROR HANDLERS ==========
@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', error='404 - Trang không tồn tại'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', error='500 - Lỗi máy chủ'), 500

# ========== CHẠY APP ==========
if __name__ == '__main__':
    # Thêm dữ liệu mẫu nếu database trống
    cursor = db_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM sensor_data")
    if cursor.fetchone()[0] == 0:
        # Thêm dữ liệu mẫu
        import random
        for i in range(100):
            temp = 25 + random.uniform(-2, 2)
            hum = 60 + random.uniform(-10, 10)
            air = 100 + random.uniform(0, 100)
            light = 400 + random.uniform(-50, 50)
            sound = 50 + random.uniform(-10, 20)
            cursor.execute('''
                INSERT INTO sensor_data (temperature, humidity, air_quality, light, sound)
                VALUES (?, ?, ?, ?, ?)
            ''', (temp, hum, air, light, sound))
        db_conn.commit()
    
    app.run(host='0.0.0.0', port=5000, debug=False)
