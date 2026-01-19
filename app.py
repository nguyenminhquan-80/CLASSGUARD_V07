from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, send_file, make_response
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import sqlite3
from datetime import datetime, timedelta
import json
import csv
import io
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import matplotlib
matplotlib.use('Agg')  # Không hiển thị GUI
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import base64

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

# ========== DASHBOARD CHÍNH ==========
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
               AVG(temperature) as temp,
               AVG(humidity) as hum,
               AVG(air_quality) as air,
               AVG(light) as light,
               AVG(sound) as sound
        FROM sensor_data 
        WHERE timestamp > datetime('now', '-{hours} hours')
        GROUP BY strftime('%Y-%m-%d %H', timestamp)
        ORDER BY timestamp
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

# ========== XUẤT PDF CHUYÊN NGHIỆP ==========
@app.route('/export/pdf')
@login_required
def export_pdf():
    """Xuất báo cáo PDF chuyên nghiệp"""
    try:
        # Lấy dữ liệu 24h gần nhất
        cursor = db_conn.cursor()
        cursor.execute('''
            SELECT timestamp, temperature, humidity, air_quality, light, sound
            FROM sensor_data 
            WHERE timestamp > datetime('now', '-24 hours')
            ORDER BY timestamp
        ''')
        data = cursor.fetchall()
        
        if not data:
            return "Không có dữ liệu để xuất", 404
        
        # Tạo buffer PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, 
                               topMargin=1*cm, bottomMargin=1*cm,
                               leftMargin=1.5*cm, rightMargin=1.5*cm)
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Tiêu đề chính
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2c3e50'),
            alignment=1,  # Center
            spaceAfter=20
        )
        elements.append(Paragraph("BÁO CÁO GIÁM SÁT MÔI TRƯỜNG LỚP HỌC", title_style))
        elements.append(Paragraph("Hệ thống CLASSGUARD", styles['Heading3']))
        elements.append(Spacer(1, 20))
        
        # Thông tin báo cáo
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.gray
        )
        
        info_text = f"""
        <b>Thời gian báo cáo:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}<br/>
        <b>Số lượng mẫu:</b> {len(data)} điểm dữ liệu<br/>
        <b>Người xuất báo cáo:</b> {current_user.username}<br/>
        <b>Vai trò:</b> {current_user.role}
        """
        elements.append(Paragraph(info_text, info_style))
        elements.append(Spacer(1, 30))
        
        # Tạo biểu đồ
        try:
            # Chuẩn bị dữ liệu cho biểu đồ
            timestamps = [datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S') for row in data[:50]]
            temps = [row[1] for row in data[:50]]
            hums = [row[2] for row in data[:50]]
            
            # Tạo biểu đồ nhiệt độ - độ ẩm
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
            
            # Biểu đồ nhiệt độ
            ax1.plot(timestamps, temps, color='#e74c3c', linewidth=2, marker='o', markersize=3)
            ax1.set_title('Diễn biến Nhiệt độ', fontsize=12, fontweight='bold')
            ax1.set_ylabel('Nhiệt độ (°C)', fontsize=10)
            ax1.grid(True, alpha=0.3)
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax1.fill_between(timestamps, temps, alpha=0.3, color='#e74c3c')
            
            # Biểu đồ độ ẩm
            ax2.plot(timestamps, hums, color='#3498db', linewidth=2, marker='s', markersize=3)
            ax2.set_title('Diễn biến Độ ẩm', fontsize=12, fontweight='bold')
            ax2.set_ylabel('Độ ẩm (%)', fontsize=10)
            ax2.set_xlabel('Thời gian', fontsize=10)
            ax2.grid(True, alpha=0.3)
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax2.fill_between(timestamps, hums, alpha=0.3, color='#3498db')
            
            plt.tight_layout()
            
            # Lưu biểu đồ vào buffer
            chart_buffer = io.BytesIO()
            plt.savefig(chart_buffer, format='png', dpi=150, bbox_inches='tight')
            plt.close()
            chart_buffer.seek(0)
            
            # Chuyển sang base64 để nhúng vào PDF
            chart_data = base64.b64encode(chart_buffer.getvalue()).decode()
            
            # Thêm biểu đồ vào PDF
            elements.append(Paragraph("<b>BIỂU ĐỒ PHÂN TÍCH DỮ LIỆU</b>", styles['Heading2']))
            elements.append(Spacer(1, 10))
            
            # Lưu biểu đồ ra file tạm và nhúng
            temp_chart_path = '/tmp/chart_temp.png'
            with open(temp_chart_path, 'wb') as f:
                f.write(chart_buffer.getvalue())
            
            chart_img = Image(temp_chart_path, width=15*cm, height=10*cm)
            elements.append(chart_img)
            elements.append(Spacer(1, 20))
            
        except Exception as e:
            print(f"Lỗi tạo biểu đồ: {e}")
        
        # Bảng dữ liệu mẫu
        elements.append(Paragraph("<b>DỮ LIỆU MẪU (10 bản ghi gần nhất)</b>", styles['Heading2']))
        elements.append(Spacer(1, 10))
        
        # Lấy 10 bản ghi gần nhất
        cursor.execute('''
            SELECT timestamp, temperature, humidity, air_quality, light, sound
            FROM sensor_data 
            ORDER BY timestamp DESC LIMIT 10
        ''')
        sample_data = cursor.fetchall()
        
        # Tạo bảng
        table_data = [['Thời gian', 'Nhiệt độ (°C)', 'Độ ẩm (%)', 'Chất lượng KK', 'Ánh sáng (lux)', 'Âm thanh (dB)']]
        
        for row in sample_data:
            table_data.append([
                datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S').strftime('%H:%M'),
                f"{row[1]:.1f}",
                f"{row[2]:.1f}",
                f"{int(row[3])}",
                f"{int(row[4])}",
                f"{row[5]:.1f}"
            ])
        
        table = Table(table_data, colWidths=[3*cm, 2.5*cm, 2.5*cm, 3*cm, 2.5*cm, 2.5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 30))
        
        # Tóm tắt thống kê
        elements.append(Paragraph("<b>THỐNG KÊ TỔNG QUAN</b>", styles['Heading2']))
        
        cursor.execute('''
            SELECT 
                AVG(temperature), MIN(temperature), MAX(temperature),
                AVG(humidity), MIN(humidity), MAX(humidity),
                AVG(air_quality), MIN(air_quality), MAX(air_quality)
            FROM sensor_data 
            WHERE timestamp > datetime('now', '-24 hours')
        ''')
        stats = cursor.fetchone()
        
        stats_text = f"""
        <b>Nhiệt độ:</b> Trung bình {stats[0]:.1f}°C (Min: {stats[1]:.1f}°C, Max: {stats[2]:.1f}°C)<br/>
        <b>Độ ẩm:</b> Trung bình {stats[3]:.1f}% (Min: {stats[4]:.1f}%, Max: {stats[5]:.1f}%)<br/>
        <b>Chất lượng không khí:</b> Trung bình {int(stats[6])} ppm (Min: {int(stats[7])}, Max: {int(stats[8])})<br/>
        <b>Đánh giá tổng thể:</b> {get_overall_evaluation(stats)}
        """
        
        elements.append(Paragraph(stats_text, styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Chân trang
        footer_text = """
        <i>Báo cáo được tạo tự động bởi hệ thống CLASSGUARD.<br/>
        Đây là dự án Khoa học Kỹ thuật THCS - Hệ thống giám sát môi trường lớp học thông minh.<br/>
        Mọi thông tin chi tiết xin liên hệ: classguard.project@gmail.com</i>
        """
        elements.append(Paragraph(footer_text, info_style))
        
        # Xây dựng PDF
        doc.build(elements)
        
        buffer.seek(0)
        
        # Trả về file PDF
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = \
            f'attachment; filename=classguard_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        
        return response
        
    except Exception as e:
        print(f"Lỗi tạo PDF: {e}")
        return jsonify({'error': str(e)}), 500

def get_overall_evaluation(stats):
    """Đánh giá tổng thể từ thống kê"""
    temp_avg, temp_min, temp_max = stats[0], stats[1], stats[2]
    hum_avg = stats[3]
    air_avg = stats[6]
    
    score = 0
    if 23 <= temp_avg <= 27:
        score += 1
    if 40 <= hum_avg <= 70:
        score += 1
    if air_avg < 200:
        score += 1
    
    if score == 3:
        return "Xuất sắc - Môi trường học tập lý tưởng"
    elif score == 2:
        return "Tốt - Môi trường học tập tốt"
    elif score == 1:
        return "Trung bình - Cần cải thiện một số yếu tố"
    else:
        return "Cần cải thiện - Môi trường chưa tối ưu"

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

# ========== THÊM DỮ LIỆU MẪU ==========
@app.route('/api/add-sample-data', methods=['POST'])
@login_required
def add_sample_data():
    """API thêm dữ liệu mẫu (cho demo)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Không có quyền'}), 403
    
    import random
    cursor = db_conn.cursor()
    
    for i in range(10):
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
    return jsonify({'status': 'success', 'message': 'Đã thêm 10 bản ghi mẫu'})

# ========== HEALTH ==========
@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'time': datetime.now().isoformat()})

if __name__ == '__main__':
    # Thêm dữ liệu mẫu ban đầu
    cursor = db_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM sensor_data")
    if cursor.fetchone()[0] < 50:
        import random
        for i in range(100):
            temp = 25 + random.uniform(-2, 2)
            hum = 60 + random.uniform(-10, 10)
            air = 100 + random.uniform(0, 100)
            light = 400 + random.uniform(-50, 50)
            sound = 50 + random.uniform(-10, 20)
            
            cursor.execute('''
                INSERT INTO sensor_data (timestamp, temperature, humidity, air_quality, light, sound)
                VALUES (datetime('now', ?), ?, ?, ?, ?, ?)
            ''', (f'-{i*15} minutes', temp, hum, air, light, sound))
        db_conn.commit()
    
    app.run(host='0.0.0.0', port=5000, debug=False)
