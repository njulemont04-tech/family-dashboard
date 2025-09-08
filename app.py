import os
import cloudinary
import cloudinary.uploader
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_bcrypt import Bcrypt

# --- START: NEW WEBSOCKET IMPORTS ---
from flask_socketio import SocketIO, emit, join_room

# --- END: NEW WEBSOCKET IMPORTS ---


load_dotenv()

# --- APP SETUP ---
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
)

# --- INITIALIZE EXTENSIONS ---
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = "login"
# --- START: NEW WEBSOCKET INITIALIZATION ---
# Add async_mode='eventlet' for production compatibility
socketio = SocketIO(app, async_mode="eventlet")
# --- END: NEW WEBSOCKET INITIALIZATION ---

# --- DATABASE MODELS (Our Data Blueprints) ---

list_members = db.Table(
    "list_members",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column(
        "list_id", db.Integer, db.ForeignKey("shopping_list.id"), primary_key=True
    ),
)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    avatar_url = db.Column(
        db.String(255),
        nullable=False,
        default="https://res.cloudinary.com/demo/image/upload/w_100,h_100,c_thumb,g_face,r_max/face_left.png",
    )
    owned_lists = db.relationship(
        "ShoppingList", backref="owner", lazy=True, cascade="all, delete-orphan"
    )
    events = db.relationship(
        "Event", backref="owner", lazy=True, cascade="all, delete-orphan"
    )
    meals = db.relationship(
        "Meal", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    notes = db.relationship(
        "Note", backref="author", lazy=True, cascade="all, delete-orphan"
    )
    shared_lists = db.relationship(
        "ShoppingList",
        secondary=list_members,
        lazy="subquery",
        backref=db.backref("members", lazy=True),
    )


class ShoppingList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    items = db.relationship(
        "Item", backref="list", lazy=True, cascade="all, delete-orphan"
    )


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False)
    list_id = db.Column(db.Integer, db.ForeignKey("shopping_list.id"), nullable=False)


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class Meal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(20), nullable=False)
    meal_type = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


# --- USER LOADER ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- AUTHENTICATION ROUTES (Unchanged) ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists.", "warning")
            return redirect(url_for("register"))
        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
        new_user = User(username=username, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# --- CORE APP ROUTES (Home, Lists, etc.) ---
@app.route("/")
@login_required
def home():
    owned = current_user.owned_lists
    shared = current_user.shared_lists
    return render_template("index.html", owned_lists=owned, shared_lists=shared)


@app.route("/create_list", methods=["POST"])
@login_required
def create_list():
    new_list_name = request.form.get("new_list_name")
    if new_list_name:
        new_list = ShoppingList(name=new_list_name, owner=current_user)
        new_list.members.append(current_user)
        db.session.add(new_list)
        db.session.commit()
    return redirect(url_for("home"))


@app.route("/delete_list", methods=["POST"])
@login_required
def delete_list():
    list_id = request.form.get("list_to_delete")
    list_to_delete = ShoppingList.query.get(list_id)
    if list_to_delete and list_to_delete.owner == current_user:
        db.session.delete(list_to_delete)
        db.session.commit()
    return redirect(url_for("home"))


@app.route("/add", methods=["POST"])
@login_required
def add_item():
    list_id = request.form.get("list_id")
    item_text = request.form.get("item")
    target_list = ShoppingList.query.get(list_id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if (
        target_list
        and item_text
        and (target_list.owner == current_user or current_user in target_list.members)
    ):
        new_item = Item(text=item_text, list_id=target_list.id)
        db.session.add(new_item)
        db.session.commit()

        # --- START: WEBSOCKET BROADCAST ---
        # After saving, we create a payload of data to send to clients
        item_data = {
            "id": new_item.id,
            "text": new_item.text,
            "done": new_item.done,
        }
        # We emit an 'item_added' event to the specific room for this list
        # Any user on a page with this list will receive this event.
        socketio.emit(
            "item_added",
            {"list_id": target_list.id, "item": item_data},
            room=f"list_{target_list.id}",
        )
        # --- END: WEBSOCKET BROADCAST ---

        if is_ajax:
            return jsonify({"success": True, "item": item_data})

    return redirect(url_for("home"))


@app.route("/delete", methods=["POST"])
@login_required
def delete_item():
    item_id = request.form.get("item_to_delete")
    item_to_delete = Item.query.get(item_id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if item_to_delete and (
        item_to_delete.list.owner == current_user
        or current_user in item_to_delete.list.members
    ):
        list_id = item_to_delete.list.id  # Save list_id before deleting
        db.session.delete(item_to_delete)
        db.session.commit()

        # --- START: WEBSOCKET BROADCAST ---
        socketio.emit(
            "item_deleted",
            {"list_id": list_id, "item_id": item_id},
            room=f"list_{list_id}",
        )
        # --- END: WEBSOCKET BROADCAST ---

        if is_ajax:
            return jsonify({"success": True})

    return redirect(url_for("home"))


@app.route("/toggle", methods=["POST"])
@login_required
def toggle_done():
    item_id = request.form.get("item_to_toggle")
    item_to_toggle = Item.query.get(item_id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if item_to_toggle and (
        item_to_toggle.list.owner == current_user
        or current_user in item_to_toggle.list.members
    ):
        item_to_toggle.done = not item_to_toggle.done
        db.session.commit()

        # --- START: WEBSOCKET BROADCAST ---
        socketio.emit(
            "item_toggled",
            {
                "list_id": item_to_toggle.list.id,
                "item_id": item_to_toggle.id,
                "done_status": item_to_toggle.done,
            },
            room=f"list_{item_to_toggle.list.id}",
        )
        # --- END: WEBSOCKET BROADCAST ---

        if is_ajax:
            return jsonify({"success": True, "done_status": item_to_toggle.done})

    return redirect(url_for("home"))


# --- CALENDAR ROUTES (Unchanged) ---
@app.route("/calendar")
@login_required
def calendar():
    user_events = (
        Event.query.filter_by(owner=current_user).order_by(Event.date, Event.time).all()
    )
    return render_template("calendar.html", events=user_events)


# ... all other routes like add_event, delete_event, share_list, meal_planner, etc. remain exactly the same ...
# I am omitting them here for brevity, but they should remain in your file.
@app.route("/add_event", methods=["POST"])
@login_required
def add_event():
    title = request.form.get("title")
    date_str = request.form.get("date")
    time_str = request.form.get("time")
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if title and date_str and time_str:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        time_obj = datetime.strptime(time_str, "%H:%M").time()
        new_event = Event(title=title, date=date_obj, time=time_obj, owner=current_user)
        db.session.add(new_event)
        db.session.commit()

        if is_ajax:
            return jsonify(
                {
                    "success": True,
                    "event": {
                        "id": new_event.id,
                        "title": new_event.title,
                        "date": new_event.date.strftime("%Y-%m-%d"),
                        "time": new_event.time.strftime("%H:%M"),
                        "formatted_date": new_event.date.strftime("%a, %b %d"),
                        "formatted_time": new_event.time.strftime("%I:%M %p"),
                    },
                }
            )

    return redirect(url_for("calendar"))


@app.route("/delete_event", methods=["POST"])
@login_required
def delete_event():
    event_id = request.form.get("event_id")
    event_to_delete = Event.query.get(event_id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if event_to_delete and event_to_delete.owner == current_user:
        db.session.delete(event_to_delete)
        db.session.commit()
        if is_ajax:
            return jsonify({"success": True})

    return redirect(url_for("calendar"))


@app.route("/share", methods=["POST"])
@login_required
def share_list():
    list_id = request.form.get("list_id")
    share_with_username = request.form.get("username")

    list_to_share = ShoppingList.query.get(list_id)
    user_to_share_with = User.query.filter_by(username=share_with_username).first()

    if not list_to_share:
        flash("List not found.", "danger")
    elif list_to_share.owner != current_user:
        flash("You can only share lists that you own.", "danger")
    elif not user_to_share_with:
        flash(f'User "{share_with_username}" not found.', "danger")
    elif user_to_share_with == current_user:
        flash("You cannot share a list with yourself.", "warning")
    elif user_to_share_with in list_to_share.members:
        flash(f'List is already shared with "{share_with_username}".', "info")
    else:
        list_to_share.members.append(user_to_share_with)
        db.session.commit()
        flash(f'List successfully shared with "{share_with_username}"!', "success")

    return redirect(url_for("home"))


@app.route("/meal_planner")
@login_required
def meal_planner():
    user_meals = Meal.query.filter_by(user=current_user).all()
    meal_plan = {}
    days_of_week = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    meal_types = ["Breakfast", "Lunch", "Dinner"]
    for day in days_of_week:
        meal_plan[day] = {meal_type: None for meal_type in meal_types}
    for meal in user_meals:
        if meal.day in meal_plan and meal.meal_type in meal_plan[meal.day]:
            meal_plan[meal.day][meal.meal_type] = meal
    return render_template(
        "meal_planner.html",
        meal_plan=meal_plan,
        days_of_week=days_of_week,
        meal_types=meal_types,
    )


@app.route("/add_meal", methods=["POST"])
@login_required
def add_meal():
    day = request.form.get("day")
    meal_type = request.form.get("meal_type")
    description = request.form.get("description")
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if day and meal_type and description:
        existing_meal = Meal.query.filter_by(
            user=current_user, day=day, meal_type=meal_type
        ).first()
        if existing_meal:
            existing_meal.description = description
            db.session.commit()
            if is_ajax:
                return jsonify(
                    {
                        "success": True,
                        "action": "updated",
                        "meal": {
                            "id": existing_meal.id,
                            "description": existing_meal.description,
                        },
                    }
                )
        else:
            new_meal = Meal(
                day=day, meal_type=meal_type, description=description, user=current_user
            )
            db.session.add(new_meal)
            db.session.commit()
            if is_ajax:
                return jsonify(
                    {
                        "success": True,
                        "action": "created",
                        "meal": {
                            "id": new_meal.id,
                            "description": new_meal.description,
                        },
                    }
                )
    return redirect(url_for("meal_planner"))


@app.route("/delete_meal", methods=["POST"])
@login_required
def delete_meal():
    meal_id = request.form.get("meal_id")
    meal_to_delete = Meal.query.get(meal_id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if meal_to_delete and meal_to_delete.user == current_user:
        db.session.delete(meal_to_delete)
        db.session.commit()
        if is_ajax:
            return jsonify({"success": True})
    return redirect(url_for("meal_planner"))


@app.route("/bulletin_board")
@login_required
def bulletin_board():
    all_notes = Note.query.order_by(Note.timestamp.desc()).all()
    return render_template("bulletin_board.html", notes=all_notes)


@app.route("/add_note", methods=["POST"])
@login_required
def add_note():
    content = request.form.get("content")
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if content:
        new_note = Note(content=content, author=current_user)
        db.session.add(new_note)
        db.session.commit()

        # --- THIS IS THE PART THAT IS LIKELY MISSING ---
        note_data = {
            "id": new_note.id,
            "content": new_note.content,
            "author": new_note.author.username,
            "timestamp": new_note.timestamp.strftime("%b %d, %Y at %I:%M %p"),
            "author_id": new_note.author.id,
        }
        # Broadcast to everyone.
        socketio.emit("note_added", {"note": note_data})
        # --- END OF MISSING PART ---

        if is_ajax:
            return jsonify({"success": True, "note": note_data})

    return redirect(url_for("bulletin_board"))


@app.route("/delete_note", methods=["POST"])
@login_required
def delete_note():
    note_id = request.form.get("note_id")
    note_to_delete = Note.query.get(note_id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if note_to_delete and note_to_delete.author == current_user:
        db.session.delete(note_to_delete)
        db.session.commit()

        # --- THIS IS THE PART THAT IS LIKELY MISSING ---
        socketio.emit("note_deleted", {"note_id": note_id})
        # --- END OF MISSING PART ---

        if is_ajax:
            return jsonify({"success": True})

    return redirect(url_for("bulletin_board"))


@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html")


@app.route("/profile/upload_avatar", methods=["POST"])
@login_required
def upload_avatar():
    if "avatar" in request.files:
        file_to_upload = request.files["avatar"]
        if file_to_upload.filename != "":
            try:
                upload_result = cloudinary.uploader.upload(
                    file_to_upload,
                    transformation={
                        "width": 150,
                        "height": 150,
                        "crop": "thumb",
                        "gravity": "face",
                    },
                )
                current_user.avatar_url = upload_result["secure_url"]
                db.session.commit()
                flash("Avatar updated successfully!", "success")
            except Exception as e:
                flash(f"Error uploading image: {e}", "danger")
        else:
            flash("No file selected.", "warning")
    return redirect(url_for("profile"))


# --- START: NEW SOCKETIO EVENT HANDLERS ---
@socketio.on("connect")
def handle_connect():
    """A client has connected to the server."""
    print(f"Client connected: {request.sid}")


@socketio.on("disconnect")
def handle_disconnect():
    """A client has disconnected from the server."""
    print(f"Client disconnected: {request.sid}")


@socketio.on("join")
def on_join(data):
    """A client wants to join a room to receive updates for a specific list."""
    list_id = data["list_id"]
    room = f"list_{list_id}"
    join_room(room)
    print(f"Client {request.sid} joined room {room}")


# --- END: NEW SOCKETIO EVENT HANDLERS ---


if __name__ == "__main__":
    # --- CHANGE THIS LINE TO RUN WITH SOCKETIO ---
    socketio.run(app, debug=True)
    # --- DO NOT USE app.run() ANYMORE FOR LOCAL TESTING ---
