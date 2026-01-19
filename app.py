from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import os

# ========== KHỞI TẠO APP ==========
app = Flask(__name__)
app.config['SECRET_KEY'] = 'classguard-secret-key-2024-change-this'  # THAY ĐỔI!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///classguard.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ========== DATABASE ==========
db = SQLAlchemy(app)

# Model User cho đăng nhập
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='viewer')  # admin, viewer
    
# Model lưu dữ liệu cảm biến
class SensorData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    temperature = db.Column(db.Float)
    humidity = db.Column(db.Float)
    air_quality = db.Column(db.Float)
    light = db.Column(db.Float)
    sound = db.Column(db.Float)
    
# Tạo database
with app.app_context():
    db.create_all()
    # Tạo user mẫu nếu chưa có
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password='admin123', role='admin')
        viewer = User(username='user', password='user123', role='viewer')
        db.session.add(admin)
        db.session.add(viewer)
        db.session.commit()

# ========== FLASK-LOGIN ==========
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ========== ROUTES CƠ BẢN ==========
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password:
            login_user(user)
            flash('Đăng nhập thành công!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Sai tên đăng nhập hoặc mật khẩu!', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ========== DASHBOARD ==========
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', 
                         username=current_user.username,
                         role=current_user.role)

# ========== API CHO DỮ LIỆU ==========
@app.route('/api/sensor-data', methods=['GET', 'POST'])
@login_required
def sensor_data():
    if request.method == 'POST':
        # Nhận dữ liệu từ ESP32
        data = request.json
        new_data = SensorData(
            temperature=data.get('temp'),
            humidity=data.get('humidity'),
            air_quality=data.get('air'),
            light=data.get('light'),
            sound=data.get('sound')
        )
        db.session.add(new_data)
        db.session.commit()
        return jsonify({"status": "success"})
    
    # GET: Trả về dữ liệu mới nhất
    latest_data = SensorData.query.order_by(SensorData.timestamp.desc()).first()
    if latest_data:
        data = {
            "temperature": latest_data.temperature,
            "humidity": latest_data.humidity,
            "air_quality": latest_data.air_quality,
            "light": latest_data.light,
            "sound": latest_data.sound,
            "timestamp": latest_data.timestamp.isoformat()
        }
        return jsonify(data)
    return jsonify({"message": "No data available"})

@app.route('/api/historical-data')
@login_required
def historical_data():
    # Trả về dữ liệu 24h gần nhất
    from datetime import timedelta
    time_threshold = datetime.utcnow() - timedelta(hours=24)
    data_points = SensorData.query.filter(SensorData.timestamp >= time_threshold).all()
    
    data = {
        "timestamps": [d.timestamp.isoformat() for d in data_points],
        "temperature": [d.temperature for d in data_points],
        "humidity": [d.humidity for d in data_points],
        "air_quality": [d.air_quality for d in data_points],
        "light": [d.light for d in data_points],
        "sound": [d.sound for d in data_points]
    }
    return jsonify(data)

# ========== ĐIỀU KHIỂN THIẾT BỊ ==========
device_states = {
    'fan': False,
    'light': False,
    'alert': False
}

@app.route('/api/control', methods=['POST'])
@login_required
def control_device():
    if current_user.role != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    device = data.get('device')
    state = data.get('state')
    
    if device in device_states:
        device_states[device] = state
        return jsonify({"status": "success", device: state})
    
    return jsonify({"error": "Device not found"}), 404

@app.route('/api/device-status')
@login_required
def device_status():
    return jsonify(device_states)

# ========== HEALTH CHECK ==========
@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})

# ========== CHẠY APP ==========
if __name__ == '__main__':
    app.run(debug=True)
