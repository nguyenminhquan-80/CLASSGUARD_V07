from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import json
import csv
import io

# ========== KHỞI TẠO APP ==========
app = Flask(__name__)
app.config['SECRET_KEY'] = 'classguard-secret-key-2024-change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///classguard.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ========== DATABASE ==========
db = SQLAlchemy(app)

# Model User
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='viewer')  # 'admin' hoặc 'viewer'

# Model Sensor Data
class SensorData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    temperature = db.Column(db.Float)
    humidity = db.Column(db.Float)
    air_quality = db.Column(db.Float)  # từ MQ135
    light = db.Column(db.Float)        # từ BH1750
    sound = db.Column(db.Float)        # từ INMP441

# Tạo database
with app.app_context():
    db.create_all()
    # Tạo user mẫu nếu chưa có
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', password='admin123', role='admin')
        viewer_user = User(username='user', password='user123', role='viewer')
        db.session.add(admin_user)
        db.session.add(viewer_user)
        db.session.commit()

# ========== FLASK-LOGIN ==========
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Vui lòng đăng nhập để truy cập trang này.'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ========== ROUTES ==========
@app.route('/')
def index():
    """Trang chủ - chuyển hướng đến login hoặc dashboard"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Trang đăng nhập"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password:
            login_user(user, remember=remember)
            flash(f'Chào mừng {username}! Đăng nhập thành công.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Tên đăng nhập hoặc mật khẩu không đúng.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Đăng xuất"""
    logout_user()
    flash('Bạn đã đăng xuất thành công.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Trang dashboard chính"""
    # Lấy dữ liệu mới nhất
    latest_data = SensorData.query.order_by(SensorData.timestamp.desc()).first()
    
    # Tính đánh giá tiết học
    evaluation = "Chưa có đủ dữ liệu"
    if latest_data:
        evaluation = evaluate_classroom(latest_data)
    
    return render_template('dashboard.html',
                         username=current_user.username,
                         role=current_user.role,
                         latest_data=latest_data,
                         evaluation=evaluation)

@app.route('/api/sensor-data', methods=['GET', 'POST'])
def handle_sensor_data():
    """API nhận và trả về dữ liệu cảm biến"""
    if request.method == 'POST':
        # Nhận dữ liệu từ ESP32
        try:
            data = request.json
            new_record = SensorData(
                temperature=data.get('temperature', 0),
                humidity=data.get('humidity', 0),
                air_quality=data.get('air_quality', 0),
                light=data.get('light', 0),
                sound=data.get('sound', 0)
            )
            db.session.add(new_record)
            db.session.commit()
            return jsonify({'status': 'success', 'message': 'Dữ liệu đã được lưu'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
    
    # GET: Trả về dữ liệu mới nhất
    latest = SensorData.query.order_by(SensorData.timestamp.desc()).first()
    if latest:
        return jsonify({
            'temperature': latest.temperature,
            'humidity': latest.humidity,
            'air_quality': latest.air_quality,
            'light': latest.light,
            'sound': latest.sound,
            'timestamp': latest.timestamp.isoformat()
        })
    return jsonify({'message': 'Chưa có dữ liệu'})

@app.route('/api/historical-data')
@login_required
def get_historical_data():
    """API trả về dữ liệu lịch sử cho biểu đồ"""
    hours = request.args.get('hours', default=24, type=int)
    time_threshold = datetime.utcnow() - timedelta(hours=hours)
    
    data_points = SensorData.query.filter(
        SensorData.timestamp >= time_threshold
    ).order_by(SensorData.timestamp).all()
    
    result = {
        'timestamps': [d.timestamp.isoformat() for d in data_points],
        'temperature': [d.temperature for d in data_points],
        'humidity': [d.humidity for d in data_points],
        'air_quality': [d.air_quality for d in data_points],
        'light': [d.light for d in data_points],
        'sound': [d.sound for d in data_points]
    }
    
    return jsonify(result)

# ========== ĐÁNH GIÁ LỚP HỌC ==========
def evaluate_classroom(data):
    """Đánh giá chất lượng môi trường lớp học"""
    score = 0
    feedback = []
    
    # Nhiệt độ lý tưởng: 23-27°C
    if 23 <= data.temperature <= 27:
        score += 20
        feedback.append("Nhiệt độ lý tưởng")
    elif 20 <= data.temperature < 23 or 27 < data.temperature <= 30:
        score += 10
        feedback.append("Nhiệt độ chấp nhận được")
    else:
        feedback.append("Nhiệt độ không phù hợp")
    
    # Độ ẩm lý tưởng: 40-70%
    if 40 <= data.humidity <= 70:
        score += 20
        feedback.append("Độ ẩm tốt")
    else:
        feedback.append("Độ ẩm cần điều chỉnh")
    
    # Chất lượng không khí (MQ135)
    if data.air_quality < 200:
        score += 20
        feedback.append("Không khí trong lành")
    elif 200 <= data.air_quality < 400:
        score += 10
        feedback.append("Không khí bình thường")
    else:
        feedback.append("Cần thông gió")
    
    # Ánh sáng (lux)
    if 300 <= data.light <= 500:
        score += 20
        feedback.append("Ánh sáng tốt")
    else:
        feedback.append("Ánh sáng cần điều chỉnh")
    
    # Âm thanh (dB)
    if data.sound < 60:
        score += 20
        feedback.append("Môi trường yên tĩnh")
    elif 60 <= data.sound < 70:
        score += 10
        feedback.append("Âm thanh chấp nhận được")
    else:
        feedback.append("Ồn ào, khó tập trung")
    
    # Xếp loại
    if score >= 80:
        rating = "Xuất sắc"
    elif score >= 60:
        rating = "Tốt"
    elif score >= 40:
        rating = "Trung bình"
    else:
        rating = "Cần cải thiện"
    
    return {
        'score': score,
        'rating': rating,
        'feedback': feedback,
        'timestamp': datetime.utcnow().isoformat()
    }

# ========== ĐIỀU KHIỂN THIẾT BỊ ==========
device_states = {
    'fan': False,
    'light': False,
    'alert': False
}

@app.route('/api/control', methods=['POST'])
@login_required
def control_device():
    """API điều khiển thiết bị (chỉ admin)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Không có quyền thực hiện'}), 403
    
    data = request.json
    device = data.get('device')
    state = data.get('state')
    
    if device in device_states:
        device_states[device] = state
        # Ghi log hành động
        print(f"Admin {current_user.username} {'bật' if state else 'tắt'} {device}")
        return jsonify({'status': 'success', 'device': device, 'state': state})
    
    return jsonify({'error': 'Thiết bị không tồn tại'}), 404

@app.route('/api/device-status')
@login_required
def get_device_status():
    """API lấy trạng thái thiết bị"""
    return jsonify(device_states)

# ========== XUẤT DỮ LIỆU ==========
@app.route('/export/csv')
@login_required
def export_csv():
    """Xuất dữ liệu dạng CSV"""
    data_points = SensorData.query.order_by(SensorData.timestamp.desc()).limit(1000).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Thời gian', 'Nhiệt độ (°C)', 'Độ ẩm (%)', 'Chất lượng KK', 'Ánh sáng (lux)', 'Âm thanh (dB)'])
    
    for data in data_points:
        writer.writerow([
            data.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            data.temperature,
            data.humidity,
            data.air_quality,
            data.light,
            data.sound
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'classguard_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

# ========== HEALTH CHECK ==========
@app.route('/health')
def health():
    """Health check cho Render"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'database': 'connected' if db else 'disconnected'
    })

# ========== FALLBACK ROUTE ==========
@app.route('/api/data')
def api_data_fallback():
    """Route cũ để test"""
    return jsonify({
        'status': 'success',
        'message': 'CLASSGUARD API đang hoạt động',
        'version': '2.0',
        'features': ['Đăng nhập', 'Dashboard', 'API cảm biến', 'Điều khiển thiết bị']
    })

# ========== CHẠY ỨNG DỤNG ==========
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
