from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, send_file, make_response
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import sqlite3
from datetime import datetime, timedelta
import json
import csv
import io
import os
import random

# Fix for flask-login compatibility with newer Werkzeug
try:
    from werkzeug.urls import url_decode
except ImportError:
    from werkzeug.datastructures import MultiDict
    from werkzeug.http import parse_options_header
    import urllib.parse
    
    def url_decode(query_string, charset='utf-8', decode_keys=False, decode_values=False):
        """Backward compatibility for old flask-login"""
        if isinstance(query_string, bytes):
            query_string = query_string.decode(charset)
        
        result = {}
        for item in query_string.split('&'):
            if not item:
                continue
            key, value = item.split('=', 1) if '=' in item else (item, '')
            key = urllib.parse.unquote(key, charset)
            value = urllib.parse.unquote(value, charset)
            result[key] = value
        
        return MultiDict(result)

# ========== KHỞI TẠO APP ==========
app = Flask(__name__)
app.secret_key = 'classguard-secret-key-' + os.urandom(16).hex()

# ========== DATABASE ==========
def init_db():
    conn = sqlite3.connect('classguard.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    
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
    
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                      ('admin', 'admin123', 'admin'))
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                      ('user', 'user123', 'viewer'))
    
    conn.commit()
    return conn

db_conn = init_db()

# ========== FLASK-LOGIN ==========
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

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

# ========== ROUTES CƠ BẢN ==========
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        cursor = db_conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user_data = cursor.fetchone()
        
        if user_data and user_data[2] == password:
            user = User(user_data[0], user_data[1], user_data[2], user_data[3])
            login_user(user)
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

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 1")
    latest_data = cursor.fetchone()
    
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
            'temperature': round(data[0], 1),
            'humidity': round(data[1], 1),
            'air_quality': int(data[2]),
            'light': int(data[3]),
            'sound': round(data[4], 1),
            'timestamp': data[5],
            'status': 'real'
        })
    else:
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
    hours = request.args.get('hours', 24, type=int)
    
    cursor = db_conn.cursor()
    cursor.execute(f'''
        SELECT strftime('%H:%M', timestamp) as time,
               temperature, humidity, air_quality, light, sound
        FROM sensor_data 
        WHERE timestamp > datetime('now', '-{hours} hours')
        ORDER BY timestamp
        LIMIT 50
    ''')
    
    data = cursor.fetchall()
    
    if data and len(data) > 0:
        timestamps = [row[0] for row in data]
        temperatures = [round(row[1], 1) for row in data]
        humidities = [round(row[2], 1) for row in data]
        air_quality = [int(row[3]) for row in data]
        light = [int(row[4]) for row in data]
        sound = [round(row[5], 1) for row in data]
    else:
        timestamps = ['08:00', '10:00', '12:00', '14:00', '16:00']
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

# ========== XUẤT CSV ==========
@app.route('/export/csv')
@login_required
def export_csv():
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 1000")
    data = cursor.fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Thời gian', 'Nhiệt độ (°C)', 'Độ ẩm (%)', 
                     'Chất lượng KK (ppm)', 'Ánh sáng (lux)', 'Âm thanh (dB)'])
    
    for row in data:
        writer.writerow([
            row[1],
            f"{row[2]:.1f}",
            f"{row[3]:.1f}",
            f"{int(row[4])}",
            f"{int(row[5])}",
            f"{row[6]:.1f}"
        ])
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = \
        f'attachment; filename=classguard_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    return response

# ========== XUẤT TXT THAY CHO PDF ==========
@app.route('/export/report')
@login_required
def export_report():
    """Xuất báo cáo dạng TXT (thay cho PDF)"""
    cursor = db_conn.cursor()
    cursor.execute('''
        SELECT timestamp, temperature, humidity, air_quality, light, sound
        FROM sensor_data 
        WHERE timestamp > datetime('now', '-24 hours')
        ORDER BY timestamp
    ''')
    data = cursor.fetchall()
    
    if not data:
        return "Không có dữ liệu", 404
    
    # Tạo báo cáo TXT
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("BÁO CÁO GIÁM SÁT LỚP HỌC - CLASSGUARD")
    report_lines.append("=" * 60)
    report_lines.append(f"Thời gian báo cáo: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    report_lines.append(f"Người xuất báo cáo: {current_user.username}")
    report_lines.append(f"Số lượng mẫu: {len(data)}")
    report_lines.append("=" * 60)
    report_lines.append("")
    
    # Thống kê
    cursor.execute('''
        SELECT 
            AVG(temperature), MIN(temperature), MAX(temperature),
            AVG(humidity), MIN(humidity), MAX(humidity)
        FROM sensor_data 
        WHERE timestamp > datetime('now', '-24 hours')
    ''')
    stats = cursor.fetchone()
    
    if stats[0]:
        report_lines.append("THỐNG KÊ TỔNG QUAN:")
        report_lines.append(f"  Nhiệt độ: {stats[0]:.1f}°C (Min: {stats[1]:.1f}°C, Max: {stats[2]:.1f}°C)")
        report_lines.append(f"  Độ ẩm: {stats[3]:.1f}% (Min: {stats[4]:.1f}%, Max: {stats[5]:.1f}%)")
        report_lines.append("")
    
    # Dữ liệu mẫu
    report_lines.append("DỮ LIỆU MẪU (10 bản ghi gần nhất):")
    report_lines.append("-" * 60)
    report_lines.append("Thời gian    | Nhiệt độ | Độ ẩm | Chất lượng KK | Ánh sáng | Âm thanh")
    report_lines.append("-" * 60)
    
    for row in data[:10]:
        report_lines.append(
            f"{datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S').strftime('%H:%M'):12} | "
            f"{row[1]:7.1f}°C | "
            f"{row[2]:5.1f}% | "
            f"{int(row[3]):12} | "
            f"{int(row[4]):7} | "
            f"{row[5]:6.1f} dB"
        )
    
    report_lines.append("")
    report_lines.append("=" * 60)
    report_lines.append("Hệ thống CLASSGUARD - Dự án KHKT THCS")
    report_lines.append("Báo cáo được tạo tự động")
    
    # Trả về file TXT
    report_content = "\n".join(report_lines)
    response = make_response(report_content)
    response.headers['Content-Type'] = 'text/plain; charset=utf-8'
    response.headers['Content-Disposition'] = \
        f'attachment; filename=classguard_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    return response

# ========== ĐÁNH GIÁ LỚP HỌC ==========
def evaluate_classroom(data):
    if not data:
        return {'score': 0, 'rating': 'Chưa có dữ liệu', 'feedback': [], 'color': 'secondary'}
    
    temp, humidity, air, light, sound = data[2:7]
    score = 0
    feedback = []
    
    if 23 <= temp <= 27:
        score += 20
        feedback.append("🌡 Nhiệt độ lý tưởng")
    elif 20 <= temp < 23 or 27 < temp <= 30:
        score += 10
        feedback.append("🌡 Nhiệt độ chấp nhận được")
    else:
        feedback.append("🌡 Nhiệt độ không phù hợp")
    
    if 40 <= humidity <= 70:
        score += 20
        feedback.append("💧 Độ ẩm tốt")
    else:
        feedback.append("💧 Độ ẩm cần điều chỉnh")
    
    if air < 200:
        score += 20
        feedback.append("💨 Không khí trong lành")
    elif 200 <= air < 400:
        score += 10
        feedback.append("💨 Không khí bình thường")
    else:
        feedback.append("💨 Cần thông gió")
    
    if 300 <= light <= 500:
        score += 20
        feedback.append("💡 Ánh sáng tốt")
    else:
        feedback.append("💡 Ánh sáng cần điều chỉnh")
    
    if sound < 60:
        score += 20
        feedback.append("🔇 Môi trường yên tĩnh")
    elif 60 <= sound < 70:
        score += 10
        feedback.append("🔊 Âm thanh chấp nhận được")
    else:
        feedback.append("🔊 Ồn ào, khó tập trung")
    
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
    return jsonify(device_status)

# ========== HEALTH ==========
@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'time': datetime.now().isoformat()})

# ========== TẠO DỮ LIỆU MẪU ==========
def create_sample_data():
    cursor = db_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM sensor_data")
    count = cursor.fetchone()[0]
    
    if count < 50:
        base_time = datetime.now()
        for i in range(100):
            timestamp = (base_time - timedelta(minutes=i*15)).strftime('%Y-%m-%d %H:%M:%S')
            temp = 25 + random.uniform(-2, 2)
            hum = 60 + random.uniform(-10, 10)
            air = 100 + random.uniform(0, 100)
            light = 400 + random.uniform(-50, 50)
            sound = 50 + random.uniform(-10, 20)
            
            cursor.execute('''
                INSERT INTO sensor_data (timestamp, temperature, humidity, air_quality, light, sound)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (timestamp, temp, hum, air, light, sound))
        
        db_conn.commit()

# Khởi tạo dữ liệu
create_sample_data()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

