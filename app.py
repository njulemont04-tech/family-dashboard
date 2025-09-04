import json
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_super_secret_key_change_this_later' 

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# --- DATA FILES ---
LIST_DATA_FILE = 'shopping_list.json'
USER_DATA_FILE = 'users.json'
CALENDAR_DATA_FILE = 'calendar_data.json'


# --- USER MANAGEMENT (No changes here) ---
class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password = password_hash

    @staticmethod
    def get(user_id):
        users = load_users()
        user_data = users.get(user_id)
        if user_data:
            return User(user_id, user_data['username'], user_data['password_hash'])
        return None

def load_users():
    try:
        with open(USER_DATA_FILE, 'r') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): return {}

def save_users(users):
    with open(USER_DATA_FILE, 'w') as f: json.dump(users, f, indent=4)

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


# --- LIST DATA MANAGEMENT (Now user-specific!) ---
def load_list_data():
    try:
        with open(LIST_DATA_FILE, 'r') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): return {}

def save_list_data(data):
    with open(LIST_DATA_FILE, 'w') as f: json.dump(data, f, indent=4)

def load_calendar_data():
    try:
        with open(CALENDAR_DATA_FILE, 'r') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): return {}

def save_calendar_data(data):
    with open(CALENDAR_DATA_FILE, 'w') as f: json.dump(data, f, indent=4)


# --- AUTHENTICATION ROUTES (No changes here) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('home'))
    if request.method == 'POST':
        username, password = request.form.get('username'), request.form.get('password')
        users = load_users()
        user_to_check = None
        for user_id, user_data in users.items():
            if user_data['username'] == username:
                user_to_check = User.get(user_id)
                break
        if user_to_check and bcrypt.check_password_hash(user_to_check.password, password):
            login_user(user_to_check)
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('home'))
    if request.method == 'POST':
        username, password = request.form.get('username'), request.form.get('password')
        users = load_users()
        if any(u['username'] == username for u in users.values()):
            flash('Username already exists.', 'warning')
            return redirect(url_for('register'))
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user_id = str(len(users) + 1)
        users[new_user_id] = {'username': username, 'password_hash': hashed_password}
        save_users(users)
        
        # Also create an entry for the new user in the list data file
        all_lists = load_list_data()
        all_lists[username] = {}
        save_list_data(all_lists)

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# --- MAIN APPLICATION ROUTES (NOW FULLY USER-AWARE) ---
@app.route('/')
@login_required
def home():
    all_lists = load_list_data()
    user_lists = all_lists.get(current_user.username, {})
    return render_template('index.html', data=user_lists, username=current_user.username)

@app.route('/calendar')
@login_required
def calendar():
    all_events = load_calendar_data()
    user_events = all_events.get(current_user.username, [])
    
    # --- THIS IS THE NEW FORMATTING LOGIC ---
    # We will process the events before sending them to the template
    processed_events = []
    for event in user_events:
        # Create a copy to avoid modifying the original data while looping
        processed_event = event.copy()
        
        # Convert date and time strings into datetime objects
        date_obj = datetime.strptime(event['date'], '%Y-%m-%d')
        time_obj = datetime.strptime(event['time'], '%H:%M')

        # Create new, nicely formatted strings and add them to our new dictionary
        processed_event['formatted_date'] = date_obj.strftime('%a, %b %d') # e.g., "Mon, Oct 28"
        processed_event['formatted_time'] = time_obj.strftime('%I:%M %p') # e.g., "02:30 PM"
        
        processed_events.append(processed_event)

    # Sort the events by date and then by time.
    sorted_events = sorted(processed_events, key=lambda x: (x['date'], x['time']))
    
    return render_template('calendar.html', events=sorted_events)

@app.route('/create_list', methods=['POST'])
@login_required
def create_list():
    all_lists = load_list_data()
    user_lists = all_lists.get(current_user.username, {})
    new_list_name = request.form.get('new_list_name')
    if new_list_name and new_list_name not in user_lists:
        user_lists[new_list_name] = []
        all_lists[current_user.username] = user_lists
        save_list_data(all_lists)
    return redirect(url_for('home'))

@app.route('/add', methods=['POST'])
@login_required
def add_item():
    all_lists = load_list_data()
    user_lists = all_lists.get(current_user.username, {})
    list_name, item_text = request.form.get('list_name'), request.form.get('item')
    if list_name and item_text and list_name in user_lists:
        if not any(item['text'] == item_text for item in user_lists[list_name]):
            user_lists[list_name].append({'text': item_text, 'done': False})
            all_lists[current_user.username] = user_lists
            save_list_data(all_lists)
    return redirect(url_for('home'))

@app.route('/delete', methods=['POST'])
@login_required
def delete_item():
    all_lists = load_list_data()
    user_lists = all_lists.get(current_user.username, {})
    list_name, item_to_delete_text = request.form.get('list_name'), request.form.get('item_to_delete')
    if list_name in user_lists:
        user_lists[list_name] = [item for item in user_lists[list_name] if item['text'] != item_to_delete_text]
        all_lists[current_user.username] = user_lists
        save_list_data(all_lists)
    return redirect(url_for('home'))

@app.route('/toggle', methods=['POST'])
@login_required
def toggle_done():
    all_lists = load_list_data()
    user_lists = all_lists.get(current_user.username, {})
    list_name, item_to_toggle_text = request.form.get('list_name'), request.form.get('item_to_toggle')
    if list_name in user_lists:
        for item in user_lists[list_name]:
            if item['text'] == item_to_toggle_text:
                item['done'] = not item['done']
                break
        all_lists[current_user.username] = user_lists
        save_list_data(all_lists)
    return redirect(url_for('home'))

@app.route('/delete_list', methods=['POST'])
@login_required
def delete_list():
    all_lists = load_list_data()
    user_lists = all_lists.get(current_user.username, {})
    list_to_delete = request.form.get('list_to_delete')
    if list_to_delete in user_lists:
        del user_lists[list_to_delete]
        all_lists[current_user.username] = user_lists
        save_list_data(all_lists)
    return redirect(url_for('home'))

@app.route('/add_event', methods=['POST'])
@login_required
def add_event():
    all_events = load_calendar_data()
    user_events = all_events.get(current_user.username, [])

    # Get the data from the form
    title = request.form.get('title')
    date = request.form.get('date')
    time = request.form.get('time')

    if title and date and time:
        new_event = {'title': title, 'date': date, 'time': time}
        user_events.append(new_event)
        all_events[current_user.username] = user_events
        save_calendar_data(all_events)

    return redirect(url_for('calendar'))

@app.route('/delete_event', methods=['POST'])
@login_required
def delete_event():
    all_events = load_calendar_data()
    user_events = all_events.get(current_user.username, [])

    # Get the unique event data from the form
    event_title = request.form.get('event_title')
    event_date = request.form.get('event_date')
    event_time = request.form.get('event_time')

    # Find and remove the specific event dictionary
    event_to_delete = {'title': event_title, 'date': event_date, 'time': event_time}
    if event_to_delete in user_events:
        user_events.remove(event_to_delete)
        all_events[current_user.username] = user_events
        save_calendar_data(all_events)

    return redirect(url_for('calendar'))

if __name__ == '__main__':
    app.run(debug=True)