from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os

# Khởi tạo app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'test-secret-key-123'

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User đơn giản (chưa dùng database)
class User(UserMixin):
    def __init__(self, id, username, password, role):
        self.id = id
        self.username = username
        self.password = password
        self.role = role

# User mẫu
users = {
    'admin': User(1, 'admin', 'admin123', 'admin'),
    'user': User(2, 'user', 'user123', 'viewer')
}

@login_manager.user_loader
def load_user(user_id):
    for user in users.values():
        if user.id == int(user_id):
            return user
    return None

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = users.get(username)
        if user and user.password == password:
            login_user(user)
            flash(f'Đăng nhập thành công! Chào {username}', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Sai tên đăng nhập hoặc mật khẩu', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Đã đăng xuất', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', 
                         username=current_user.username,
                         role=current_user.role)

@app.route('/health')
def health():
    return 'OK'

if __name__ == '__main__':
    app.run(debug=True)
