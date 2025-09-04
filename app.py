import os
from datetime import datetime
from dotenv import load_dotenv # <-- ADD THIS IMPORT
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt

load_dotenv() # <-- ADD THIS LINE TO LOAD THE .ENV FILE

# --- APP SETUP ---
app = Flask(__name__)
# Load the secret database URL from our .env file
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SECRET_KEY'] = 'a_super_secret_key_change_this_for_production'

# --- INITIALIZE EXTENSIONS ---
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- DATABASE MODELS (Our Data Blueprints) ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    # Relationships: Connects a User to their lists and events
    lists = db.relationship('ShoppingList', backref='owner', lazy=True, cascade="all, delete-orphan")
    events = db.relationship('Event', backref='owner', lazy=True, cascade="all, delete-orphan")

class ShoppingList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    items = db.relationship('Item', backref='list', lazy=True, cascade="all, delete-orphan")

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False)
    list_id = db.Column(db.Integer, db.ForeignKey('shopping_list.id'), nullable=False)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# --- USER LOADER ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- AUTHENTICATION ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists.', 'warning')
            return redirect(url_for('register'))
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- LIST ROUTES ---
@app.route('/')
@login_required
def home():
    user_lists = ShoppingList.query.filter_by(owner=current_user).all()
    return render_template('index.html', lists=user_lists)

@app.route('/create_list', methods=['POST'])
@login_required
def create_list():
    new_list_name = request.form.get('new_list_name')
    if new_list_name:
        new_list = ShoppingList(name=new_list_name, owner=current_user)
        db.session.add(new_list)
        db.session.commit()
    return redirect(url_for('home'))

@app.route('/delete_list', methods=['POST'])
@login_required
def delete_list():
    list_id = request.form.get('list_to_delete')
    list_to_delete = ShoppingList.query.get(list_id)
    if list_to_delete and list_to_delete.owner == current_user:
        db.session.delete(list_to_delete)
        db.session.commit()
    return redirect(url_for('home'))

@app.route('/add', methods=['POST'])
@login_required
def add_item():
    list_id = request.form.get('list_id')
    item_text = request.form.get('item')
    target_list = ShoppingList.query.get(list_id)
    if target_list and item_text and target_list.owner == current_user:
        new_item = Item(text=item_text, list_id=target_list.id)
        db.session.add(new_item)
        db.session.commit()
    return redirect(url_for('home'))

@app.route('/delete', methods=['POST'])
@login_required
def delete_item():
    item_id = request.form.get('item_to_delete')
    item_to_delete = Item.query.get(item_id)
    if item_to_delete and item_to_delete.list.owner == current_user:
        db.session.delete(item_to_delete)
        db.session.commit()
    return redirect(url_for('home'))

@app.route('/toggle', methods=['POST'])
@login_required
def toggle_done():
    item_id = request.form.get('item_to_toggle')
    item_to_toggle = Item.query.get(item_id)
    if item_to_toggle and item_to_toggle.list.owner == current_user:
        item_to_toggle.done = not item_to_toggle.done
        db.session.commit()
    return redirect(url_for('home'))

# --- CALENDAR ROUTES ---
@app.route('/calendar')
@login_required
def calendar():
    user_events = Event.query.filter_by(owner=current_user).order_by(Event.date, Event.time).all()
    return render_template('calendar.html', events=user_events)

@app.route('/add_event', methods=['POST'])
@login_required
def add_event():
    title = request.form.get('title')
    date_str = request.form.get('date')
    time_str = request.form.get('time')
    if title and date_str and time_str:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        time_obj = datetime.strptime(time_str, '%H:%M').time()
        new_event = Event(title=title, date=date_obj, time=time_obj, owner=current_user)
        db.session.add(new_event)
        db.session.commit()
    return redirect(url_for('calendar'))

@app.route('/delete_event', methods=['POST'])
@login_required
def delete_event():
    event_id = request.form.get('event_id')
    event_to_delete = Event.query.get(event_id)
    if event_to_delete and event_to_delete.owner == current_user:
        db.session.delete(event_to_delete)
        db.session.commit()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)