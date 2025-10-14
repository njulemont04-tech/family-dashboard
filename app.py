# --- START: PRODUCTION WEBSOCKET CONFIGURATION ---
# This MUST be the first thing to run, before any other imports,
# to ensure that the standard library is patched for green concurrency.
import eventlet

eventlet.monkey_patch()
# --- END: PRODUCTION WEBSOCKET CONFIGURATION ---

import os
import cloudinary
import cloudinary.uploader
import bleach
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
    render_template_string,
)
from flask import json
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
from functools import wraps

# --- START: NEW WEBSOCKET IMPORTS ---
from flask_socketio import SocketIO, emit, join_room

# --- END: NEW WEBSOCKET IMPORTS ---


load_dotenv()

# --- APP SETUP ---
app = Flask(__name__)
# --- CORRECTED DATABASE CONFIGURATION ---
db_url = os.environ.get("DATABASE_URL")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url

# Engine options to configure connection pooling
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,  # Checks if a connection is alive before using it
    "pool_recycle": 300,  # Recycles connections after 300 seconds (5 minutes)
    "pool_size": 5,  # Number of connections to keep open in the pool
    "max_overflow": 2,  # Allows for a temporary overflow of connections
}
# --- END OF CORRECTION ---
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

# --- START: REPLACE ALL EXISTING MODELS WITH THIS NEW STRUCTURE ---

# Association table for User <-> Family membership
family_members = db.Table(
    "family_members",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("family_id", db.Integer, db.ForeignKey("family.id"), primary_key=True),
)


# New Family model
class Family(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # The user who created the family is the owner
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # Relationships
    members = db.relationship(
        "User",
        secondary=family_members,
        lazy="subquery",
        backref=db.backref("families", lazy=True),
    )
    shopping_lists = db.relationship(
        "ShoppingList", backref="family", lazy=True, cascade="all, delete-orphan"
    )
    events = db.relationship(
        "Event", backref="family", lazy=True, cascade="all, delete-orphan"
    )
    meals = db.relationship(
        "Meal", backref="family", lazy=True, cascade="all, delete-orphan"
    )
    notes = db.relationship(
        "Note", backref="family", lazy=True, cascade="all, delete-orphan"
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
    # The 'families' backref is created by the Family.members relationship
    # This relationship tracks which families this user owns
    owned_families = db.relationship("Family", backref="owner", lazy=True)


# The old list_members table is no longer needed


class ShoppingList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # CHANGED: Now links to a family, not a user
    family_id = db.Column(db.Integer, db.ForeignKey("family.id"), nullable=False)
    items = db.relationship(
        "Item", backref="list", lazy=True, cascade="all, delete-orphan"
    )


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    list_id = db.Column(db.Integer, db.ForeignKey("shopping_list.id"), nullable=False)
    # We still track who added an item
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    author = db.relationship("User", backref="items")


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # CHANGED: Now links to a family
    family_id = db.Column(db.Integer, db.ForeignKey("family.id"), nullable=False)
    # We still want to know who created the event
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    author = db.relationship("User", backref="events")


class Meal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(20), nullable=False)
    meal_type = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    # CHANGED: Now links to a family
    family_id = db.Column(db.Integer, db.ForeignKey("family.id"), nullable=False)
    # We can still track who last updated this meal slot
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    author = db.relationship("User", backref="meals")


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # CHANGED: Now links to a family
    family_id = db.Column(db.Integer, db.ForeignKey("family.id"), nullable=False)
    # The original author is still very important here
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    author = db.relationship("User", backref="notes")
    is_pinned = db.Column(db.Boolean, default=False, nullable=False)


# --- END OF MODEL REPLACEMENT ---


# --- START: ADD THE NEW VAULTENTRY MODEL HERE ---
class VaultEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Foreign keys
    family_id = db.Column(db.Integer, db.ForeignKey("family.id"), nullable=False)
    author_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False
    )  # Track who created/edited it

    # Relationships
    family = db.relationship("Family", backref="vault_entries")
    author = db.relationship("User", backref="vault_entries")

    def __repr__(self):
        return f"<VaultEntry {self.title}>"


# --- END: ADD THE NEW VAULTENTRY MODEL ---

# --- START: ADD THE NEW CHORE MODELS HERE ---


class Chore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(300), nullable=True)
    points = db.Column(db.Integer, nullable=False, default=5)
    # This determines how the rotation works. For now, we'll focus on 'Weekly'.
    frequency = db.Column(db.String(50), nullable=False, default="Weekly")
    family_id = db.Column(db.Integer, db.ForeignKey("family.id"), nullable=False)

    # Relationship to its assignments
    assignments = db.relationship(
        "ChoreAssignment", backref="chore", lazy=True, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Chore {self.name}>"


class ChoreAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # The start date of the week this assignment is for (e.g., a Monday)
    week_of = db.Column(db.Date, nullable=False)
    is_complete = db.Column(db.Boolean, default=False, nullable=False)

    # Foreign keys
    chore_id = db.Column(db.Integer, db.ForeignKey("chore.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    family_id = db.Column(
        db.Integer, db.ForeignKey("family.id"), nullable=False
    )  # For easier querying

    # Relationships
    user = db.relationship("User", backref="chore_assignments")

    def __repr__(self):
        return f"<ChoreAssignment {self.chore.name} for {self.user.username} on {self.week_of}>"


# --- END OF NEW CHORE MODELS ---


# --- USER LOADER ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- START: ADD THIS NEW DECORATOR ---
def family_required(f):
    """
    Ensures a user has selected a family and is a member of it.
    This decorator must be placed AFTER @login_required.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        family_id = session.get("current_family_id")
        if not family_id:
            flash("Please select a space to continue.", "info")
            return redirect(url_for("families"))

        family = Family.query.get(family_id)
        if not family or current_user not in family.members:
            session.pop("current_family_id", None)  # Clear invalid session data
            flash(
                "You are not a member of the selected space, or it no longer exists.",
                "warning",
            )
            return redirect(url_for("families"))

        # If all checks pass, inject the 'current_family' object into the route
        return f(current_family=family, *args, **kwargs)

    return decorated_function


# --- END: ADD THIS NEW DECORATOR ---


# ADD THIS NEW FUNCTION TO APP.PY


@app.context_processor
def inject_today_date():
    """Injects the current day of the month into all templates."""
    from datetime import date

    today = date.today()
    return dict(current_day=today.day)


@app.route("/login", methods=["GET", "POST"])
def login():
    # This first redirect handles users who are already logged in
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            # This second redirect handles users who just successfully logged in
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password", "danger")
            return render_template("login.html", username=username)

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


# --- ADD THESE NEW FAMILY MANAGEMENT ROUTES ---


@app.route("/families")
@login_required
def families():
    """Page to view all families and create a new one."""
    return render_template("families.html")  # We will create this file next


@app.route("/families/create", methods=["POST"])
@login_required
def create_family():
    """Process the form for creating a new family."""
    family_name = request.form.get("family_name")
    if family_name:
        # Create the new family
        new_family = Family(name=family_name, owner=current_user)
        # The creator automatically becomes a member
        new_family.members.append(current_user)
        db.session.add(new_family)
        db.session.commit()
        # Automatically select the new family as the active one
        session["current_family_id"] = new_family.id
        flash(f'Successfully created and selected family "{family_name}"!', "success")
        return redirect(url_for("dashboard"))
    else:
        flash("Family name cannot be empty.", "danger")
        return redirect(url_for("families"))


@app.route("/families/select/<int:family_id>")
@login_required
def select_family(family_id):
    """Selects a family to be the active one in the session."""
    family = Family.query.get(family_id)
    # Security check: make sure the user is actually a member of this family
    if family and current_user in family.members:
        session["current_family_id"] = family.id
        return redirect(url_for("dashboard"))
    else:
        flash("You are not a member of that family.", "danger")
        return redirect(url_for("families"))


# --- CORE APP ROUTES (Home, Lists, etc.) ---
@app.route("/dashboard")
@login_required
def dashboard():
    # --- START: ADD NEW CHORE CLEANUP LOGIC ---
    # This logic runs periodically when any user visits the dashboard.

    # Define the retention period (e.g., 4 weeks = 28 days)
    RETENTION_DAYS = 28
    cleanup_cutoff_date = date.today() - timedelta(days=RETENTION_DAYS)

    # Find and delete old chore assignments for THIS family only.
    # We only delete assignments from BEFORE the start of the retention period's week.
    start_of_cleanup_week = cleanup_cutoff_date - timedelta(
        days=cleanup_cutoff_date.weekday()
    )

    current_family_id_for_cleanup = session.get("current_family_id")
    if current_family_id_for_cleanup:
        ChoreAssignment.query.filter(
            ChoreAssignment.family_id == current_family_id_for_cleanup,
            ChoreAssignment.week_of < start_of_cleanup_week,
        ).delete(synchronize_session=False)
        db.session.commit()
    # --- END: NEW CHORE CLEANUP LOGIC ---
    # Check if a family is selected in the session
    current_family_id = session.get("current_family_id")

    if not current_family_id:
        # If the user is not part of ANY family space...
        if not current_user.families:
            # Special logic for YOU, the first user (or any admin)
            # The new, secure way to check for the admin user
            if current_user.username == os.environ.get("ADMIN_USERNAME"):
                flash(
                    "Welcome! To get started, please create a private space for your household.",
                    "info",
                )
                return redirect(url_for("families"))
            else:
                # This is the message for all other new users
                return render_template("waiting.html")
        else:
            # If they are part of one or more families, but haven't selected one
            return redirect(url_for("families"))

    # A family is selected, so fetch its data
    current_family = Family.query.get(current_family_id)
    if not current_family or current_user not in current_family.members:
        # If the family doesn't exist or user is not a member, clear the session and redirect
        session.pop("current_family_id", None)
        flash("The family you had selected is no longer available.", "warning")
        return redirect(url_for("families"))

    # The dashboard will now focus only on lists.
    # The family object itself contains the lists via its relationship.
    return render_template("dashboard.html", current_family=current_family)


# ADD THIS NEW FUNCTION TO APP.PY


@app.route("/api/inviteable_users")
@login_required
def get_inviteable_users():
    """API endpoint to get a fresh list of users who can be invited."""
    current_family_id = session.get("current_family_id")
    if not current_family_id:
        return jsonify({"error": "No family selected"}), 400

    current_family = Family.query.get(current_family_id)

    existing_member_ids = [member.id for member in current_family.members]

    users = (
        User.query.filter(
            User.id != current_user.id, User.id.notin_(existing_member_ids)
        )
        .order_by(User.username)
        .all()
    )

    user_list = [{"username": user.username} for user in users]

    return jsonify(user_list)


# --- REPLACE ALL OLD LIST ROUTES (/create_list, /delete_list, /add, /delete, /toggle, /share) WITH THESE ---


@app.route("/")
@login_required
@family_required
def home(current_family):
    return render_template("home.html", current_family=current_family)


@app.route("/invite_user", methods=["POST"])
@login_required
def invite_user():
    family_id = session.get("current_family_id")
    username_to_invite = request.form.get("username")
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    def json_response(success, message):
        return jsonify({"success": success, "message": message})

    family = Family.query.get(family_id)
    user_to_invite = User.query.filter_by(username=username_to_invite).first()

    if not family or current_user not in family.members:
        return redirect(url_for("families"))  # Should not happen, but good practice

    if not user_to_invite:
        message = f'User "{username_to_invite}" not found.'
        if is_ajax:
            return json_response(False, message)
        flash(message, "danger")
    elif user_to_invite in family.members:
        message = f'User "{username_to_invite}" is already a member of this family.'
        if is_ajax:
            return json_response(False, message)
        flash(message, "info")
    else:
        family.members.append(user_to_invite)
        db.session.commit()
        message = f'Successfully invited "{username_to_invite}" to the family!'
        if is_ajax:
            return json_response(True, message)
        flash(message, "success")

    return redirect(url_for("home"))


@app.route("/create_list", methods=["POST"])
@login_required
def create_list():
    family_id = session.get("current_family_id")
    family = Family.query.get(family_id)

    if not family or current_user not in family.members:
        return jsonify({"success": False, "message": "Permission denied."}), 403

    new_list_name = request.form.get("new_list_name")
    if new_list_name:
        new_list = ShoppingList(name=new_list_name, family_id=family.id)
        db.session.add(new_list)
        db.session.commit()

        # --- START: THE FIX ---
        # Render the new summary card template instead of the old one
        new_card_html = render_template_string(
            '{% include "list_summary_card.html" %}',
            list=new_list,
            current_family=family,
            current_user=current_user,
        )

        # --- START: THE FIX ---
        # Render the new summary card template, ensuring current_user is in the context
        new_card_html = render_template_string(
            '{% include "list_summary_card.html" %}',
            list=new_list,
            current_family=family,
            current_user=current_user,
        )

        # Emit the new card HTML to ALL users in the family's room
        socketio.emit(
            "list_added",
            {"card_html": new_card_html, "list_id": new_list.id},
            room=f"family_room_{family.id}",
        )

        # The AJAX form submission itself doesn't need to return HTML anymore,
        # because the user who submitted it will ALSO receive the socket event.
        # We just need to confirm success.
        return jsonify({"success": True})
        # --- END: THE FIX ---

    return jsonify({"success": False, "message": "List name cannot be empty."}), 400


# --- Find and REPLACE this entire function in app.py ---


@app.route("/delete_list", methods=["POST"])
@login_required
def delete_list():
    list_id = request.form.get("list_to_delete")
    list_to_delete = ShoppingList.query.get(list_id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # Security check: User must be the owner of the family the list belongs to
    if list_to_delete and list_to_delete.family.owner == current_user:
        family_id = list_to_delete.family.id  # Get the family_id before deleting
        db.session.delete(list_to_delete)
        db.session.commit()

        # Broadcast the deletion to everyone in the family's room
        socketio.emit(
            "list_deleted", {"list_id": int(list_id)}, room=f"family_room_{family_id}"
        )

        if is_ajax:
            return jsonify({"success": True})
        # The redirect is now just a fallback for non-JS submissions
        return redirect(url_for("dashboard"))

    # Handle errors
    if is_ajax:
        return jsonify({"success": False, "message": "Permission denied."}), 403
    else:
        flash("You do not have permission to delete this list.", "danger")
        return redirect(url_for("dashboard"))


@app.route("/add_item", methods=["POST"])
@login_required
def add_item():
    list_id = request.form.get("list_id")
    item_text = request.form.get("item")
    target_list = ShoppingList.query.get(list_id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # Security check: User must be a member of the family that owns the list
    if target_list and item_text and current_user in target_list.family.members:
        new_item = Item(
            text=item_text, list_id=target_list.id, author_id=current_user.id
        )
        db.session.add(new_item)
        db.session.commit()

        item_data = {
            "id": new_item.id,
            "text": new_item.text,
            "done": new_item.done,
            "author": {"username": new_item.author.username},
            "raw_timestamp": new_item.created_at.isoformat(),
        }
        socketio.emit(
            "item_added",
            {"list_id": target_list.id, "item": item_data},
            room=f"list_{target_list.id}",
        )

        # --- START: ADD THIS NEW BLOCK ---
        # This sends a separate, simple notification to the whole family.
        socketio.emit(
            "new_activity",
            {"feature": "dashboard", "timestamp": new_item.created_at.isoformat()},
            room=f"family_room_{target_list.family.id}",
        )
        # --- END: ADD THIS NEW BLOCK ---

        if is_ajax:
            return jsonify({"success": True, "item": item_data})

    return redirect(url_for("home"))


@app.route("/delete_item", methods=["POST"])
@login_required
def delete_item():
    item_id = request.form.get("item_to_delete")
    item_to_delete = Item.query.get(item_id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # Security check: User must be a member of the family
    if item_to_delete and current_user in item_to_delete.list.family.members:
        list_id = item_to_delete.list.id
        db.session.delete(item_to_delete)
        db.session.commit()

        socketio.emit(
            "item_deleted",
            {"list_id": list_id, "item_id": item_id},
            room=f"list_{list_id}",
        )

        if is_ajax:
            return jsonify({"success": True})

    return redirect(url_for("home"))


# In app.py


@app.route("/edit_item", methods=["POST"])
@login_required
def edit_item():
    item_id = request.form.get("item_id")
    new_text = request.form.get(
        "new_text", ""
    ).strip()  # Use .strip() to remove whitespace
    item_to_edit = Item.query.get(item_id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # Security check: User must be a member of the family that owns the list
    if item_to_edit and new_text and current_user in item_to_edit.list.family.members:
        item_to_edit.text = new_text
        db.session.commit()

        # Broadcast the change to everyone in the list's room
        socketio.emit(
            "item_edited",
            {
                "list_id": item_to_edit.list.id,
                "item_id": item_to_edit.id,
                "new_text": item_to_edit.text,
            },
            room=f"list_{item_to_edit.list.id}",
        )

        if is_ajax:
            return jsonify({"success": True, "new_text": item_to_edit.text})

    # Handle error case for AJAX
    if is_ajax:
        return (
            jsonify(
                {"success": False, "message": "Permission denied or invalid data."}
            ),
            400,
        )

    return redirect(url_for("home"))


def get_notifications_context(current_family):
    """
    Checks for new activity in different features and returns a context dictionary.
    This is a placeholder for a more robust notification system later.
    For now, it indicates that we should check notifications on the frontend.
    """
    return {"check_notifications": True}


# --- REFACTOR: CALENDAR ROUTES ---


# --- WITH THIS:
@app.route("/calendar")
@login_required
@family_required
def calendar(current_family):
    notifications_context = get_notifications_context(current_family)
    return render_template(
        "calendar.html", current_family=current_family, **notifications_context
    )


@app.route("/add_event", methods=["POST"])
@login_required
@family_required
def add_event(current_family):

    title = request.form.get("title")
    date_str = request.form.get("date")
    time_str = request.form.get("time")
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if title and date_str and time_str:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        time_obj = datetime.strptime(time_str, "%H:%M").time()

        # Create event tied to the family and the author
        new_event = Event(
            title=title,
            date=date_obj,
            time=time_obj,
            family_id=current_family.id,
            author_id=current_user.id,
        )
        db.session.add(new_event)
        db.session.commit()

        event_data = {
            "id": new_event.id,
            "title": new_event.title,
            "date": new_event.date.strftime("%Y-%m-%d"),
            "time": new_event.time.strftime("%H:%M"),
            "formatted_date": new_event.date.strftime("%a, %b %d"),
            "formatted_time": new_event.time.strftime("%I:%M %p"),
            "author": {
                "username": new_event.author.username,
                "id": new_event.author.id,
            },
            "raw_timestamp": new_event.created_at.isoformat(),
        }
        socketio.emit(
            "event_added",
            {"event": event_data},
            room=f"family_room_{current_family.id}",
        )

        # In the add_event route, after the existing socketio.emit("event_added",...)
        socketio.emit(
            "new_activity",
            {"feature": "calendar", "timestamp": new_event.created_at.isoformat()},
            room=f"family_room_{current_family.id}",
        )

        if is_ajax:
            return jsonify({"success": True, "event": event_data})

    return redirect(url_for("calendar"))


@app.route("/delete_event", methods=["POST"])
@login_required
def delete_event():
    event_id = request.form.get("event_id")
    event_to_delete = Event.query.get(event_id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # Security check: User must be a member of the family that owns the event
    if event_to_delete and current_user in event_to_delete.family.members:
        family_id = event_to_delete.family.id
        db.session.delete(event_to_delete)
        db.session.commit()

        socketio.emit(
            "event_deleted",
            {"event_id": int(event_id)},
            room=f"family_room_{family_id}",
        )

        if is_ajax:
            return jsonify({"success": True})

    return redirect(url_for("calendar"))


# --- REFACTOR: MEAL PLANNER ROUTES ---


@app.route("/meal_planner")
@login_required
@family_required
def meal_planner(current_family):
    family_meals = Meal.query.filter_by(
        family_id=current_family.id, meal_type="Dinner"
    ).all()
    meal_plan_for_template = {meal.day: meal for meal in family_meals}

    meal_plan_for_json = {
        meal.day: {
            "id": meal.id,
            "description": meal.description,
            "notes": meal.notes or "",
            "notes_html": bleach.linkify(meal.notes or ""),
        }
        for meal in family_meals
    }

    # --- START: THE NEW DATE LOGIC ---
    days_of_week = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]

    today = date.today()
    # Calculate the date of the most recent Monday
    start_of_week = today - timedelta(days=today.weekday())

    # Create a new data structure that includes the day name AND its date
    week_schedule = []
    for i, day_name in enumerate(days_of_week):
        current_date = start_of_week + timedelta(days=i)
        week_schedule.append({"name": day_name, "date": current_date})
    # --- END: THE NEW DATE LOGIC ---

    return render_template(
        "meal_planner.html",
        current_family=current_family,
        meal_plan=meal_plan_for_template,
        meal_plan_json=json.dumps(meal_plan_for_json),
        week_schedule=week_schedule,  # Pass the new schedule instead of days_of_week
    )


@app.route("/delete_meal", methods=["POST"])
@login_required
def delete_meal():
    meal_id = request.form.get("meal_id")
    meal_to_delete = Meal.query.get(meal_id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # --- START: NEW PERMISSION CHECK ---
    # A user can delete a meal if:
    # 1. The meal exists AND
    # 2. They are the author of the meal OR they are the owner of the family
    can_delete = meal_to_delete and (
        meal_to_delete.author_id == current_user.id
        or meal_to_delete.family.owner_id == current_user.id
    )

    if can_delete:
        # --- END: NEW PERMISSION CHECK ---
        family_id = meal_to_delete.family.id
        meal_data = {"day": meal_to_delete.day, "meal_type": meal_to_delete.meal_type}

        db.session.delete(meal_to_delete)
        db.session.commit()

        socketio.emit("meal_deleted", meal_data, room=f"family_room_{family_id}")

        if is_ajax:
            return jsonify({"success": True})

    # If the user does not have permission, and it's an AJAX request, send an error
    elif is_ajax:
        return jsonify({"success": False, "message": "Permission denied."}), 403

    return redirect(url_for("meal_planner"))


# --- REFACTOR: BULLETIN BOARD ROUTES ---


# In app.py


@app.route("/bulletin_board")
@login_required
@family_required
def bulletin_board(current_family):
    # The check is now handled by the decorator.

    # --- START: NEW AUTO-DELETION LOGIC ---
    # Define the cutoff for notes to be deleted (e.g., 30 days old)
    cutoff_date = datetime.utcnow() - timedelta(days=30)

    # Find and delete old, unpinned notes for THIS family only
    Note.query.filter(
        Note.family_id == current_family.id,
        Note.timestamp < cutoff_date,
        Note.is_pinned == False,
    ).delete(
        synchronize_session=False
    )  # Use False for bulk deletes

    db.session.commit()
    # --- END: NEW AUTO-DELETION LOGIC ---

    # --- START: NEW PINNED NOTES QUERY ---
    pinned_notes = (
        Note.query.filter_by(family_id=current_family.id, is_pinned=True)
        .order_by(Note.timestamp.desc())
        .all()
    )
    # --- END: NEW PINNED NOTES QUERY ---

    notifications_context = get_notifications_context(current_family)
    return render_template(
        "bulletin_board.html",
        current_family=current_family,
        current_user_id=current_user.id,
        pinned_notes=pinned_notes,  # Pass the pinned notes to the template
        **notifications_context,
    )


@app.route("/add_note", methods=["POST"])
@login_required
@family_required
def add_note(current_family):

    content = request.form.get("content")
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if content:
        # Create note tied to family and author
        new_note = Note(
            content=content, author_id=current_user.id, family_id=current_family.id
        )
        db.session.add(new_note)
        db.session.commit()

        note_data = {
            "id": new_note.id,
            "content": new_note.content,
            "author": new_note.author.username,
            "timestamp": new_note.timestamp.strftime("%b %d, %Y at %I:%M %p"),
            "author_id": new_note.author.id,
            "raw_timestamp": new_note.timestamp.isoformat(),  # ISO format is standard for JS
        }
        # Broadcast only to members of this family's room
        socketio.emit(
            "note_added", {"note": note_data}, room=f"family_room_{current_family.id}"
        )

        # In the add_note route, after the existing socketio.emit("note_added",...)
        socketio.emit(
            "new_activity",
            {"feature": "bulletin_board", "timestamp": new_note.timestamp.isoformat()},
            room=f"family_room_{current_family.id}",
        )

        if is_ajax:
            return jsonify({"success": True, "note": note_data})

    return redirect(url_for("bulletin_board"))


@app.route("/delete_note", methods=["POST"])
@login_required
def delete_note():
    note_id = request.form.get("note_id")
    note_to_delete = Note.query.get(note_id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # Security: Only the author can delete their note
    if note_to_delete and note_to_delete.author_id == current_user.id:
        family_id = note_to_delete.family_id
        db.session.delete(note_to_delete)
        db.session.commit()

        # Broadcast deletion to the family room
        socketio.emit(
            "note_deleted", {"note_id": note_id}, room=f"family_room_{family_id}"
        )

        if is_ajax:
            return jsonify({"success": True})

    return redirect(url_for("bulletin_board"))


# In app.py


# In app.py


@app.route("/pin_note", methods=["POST"])
@login_required
def pin_note():
    note_id = request.form.get("note_id")
    note_to_pin = Note.query.get(note_id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if note_to_pin and current_user in note_to_pin.family.members:
        note_to_pin.is_pinned = not note_to_pin.is_pinned
        db.session.commit()

        # --- START OF FIX: BROADCAST THE CHANGE ---
        socketio.emit(
            "note_pinned",
            {
                "note_id": note_to_pin.id,
                "is_pinned": note_to_pin.is_pinned,
            },
            room=f"family_room_{note_to_pin.family_id}",
        )
        # --- END OF FIX ---

        if is_ajax:
            return jsonify({"success": True, "is_pinned": note_to_pin.is_pinned})

    return redirect(url_for("bulletin_board"))


@app.route("/profile")
@login_required
@family_required
def profile(current_family):
    # Data for the "Household Members" card (for everyone)
    current_members = current_family.members

    # Data for the "Invite Member" modal (for the admin)
    inviteable_users = []
    if current_user.id == current_family.owner_id:
        existing_member_ids = [member.id for member in current_family.members]
        inviteable_users = (
            User.query.filter(
                User.id != current_user.id, User.id.notin_(existing_member_ids)
            )
            .order_by(User.username)
            .all()
        )

    return render_template(
        "profile.html",
        current_family=current_family,
        current_members=current_members,
        inviteable_users=inviteable_users,
    )


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


# In app.py, add this new route after the upload_avatar route.


@app.route("/profile/change_password", methods=["POST"])
@login_required
def change_password():
    old_password = request.form.get("old_password")
    new_password = request.form.get("new_password")

    # Check if the old password is correct
    if not bcrypt.check_password_hash(current_user.password_hash, old_password):
        flash("Incorrect old password. Please try again.", "danger")
        return redirect(url_for("profile"))

    # Hash the new password and update the user
    hashed_password = bcrypt.generate_password_hash(new_password).decode("utf-8")
    current_user.password_hash = hashed_password
    db.session.commit()

    flash("Your password has been updated successfully!", "success")
    return redirect(url_for("profile"))


# --- START: NEW FAMILY VAULT ROUTES ---
@app.route("/vault")
@login_required
@family_required
def vault(current_family):
    # Only family members can see the vault.
    # We will group entries by category for easier viewing.
    entries = (
        VaultEntry.query.filter_by(family_id=current_family.id)
        .order_by(VaultEntry.category, VaultEntry.title)
        .all()
    )

    entries_by_category = {}
    for entry in entries:
        if entry.category not in entries_by_category:
            entries_by_category[entry.category] = []
        entries_by_category[entry.category].append(entry)

    # Get a list of unique categories to potentially use in the UI
    categories = sorted(entries_by_category.keys())

    return render_template(
        "vault.html",
        current_family=current_family,
        entries_by_category=entries_by_category,
        categories=categories,
    )


@app.route("/vault/add", methods=["POST"])
@login_required
@family_required
def add_vault_entry(current_family):
    # (Validation remains the same)
    if current_user.id != current_family.owner_id:
        return jsonify({"success": False, "message": "Permission denied."}), 403
    # ... form data retrieval ...
    if not all(
        [
            request.form.get("category"),
            request.form.get("title"),
            request.form.get("content"),
        ]
    ):
        return jsonify({"success": False, "message": "All fields are required."}), 400

    new_entry = VaultEntry(
        category=request.form.get("category").strip(),
        title=request.form.get("title").strip(),
        content=request.form.get("content").strip(),
        family_id=current_family.id,
        author_id=current_user.id,
    )
    db.session.add(new_entry)
    db.session.commit()

    # --- START OF FIX ---
    # Pass all necessary context to the render_template calls
    entry_html = render_template(
        "_vault_entry.html",
        entry=new_entry,
        current_user=current_user,
        current_family=current_family,
    )
    edit_modal_html = render_template(
        "_edit_vault_modal.html", entry=new_entry, categories=[]
    )
    # --- END OF FIX ---

    return jsonify(
        {
            "success": True,
            "message": "New vault entry added successfully!",
            "entry": {"id": new_entry.id, "category": new_entry.category},
            "entry_html": entry_html,
            "edit_modal_html": edit_modal_html,
        }
    )


@app.route("/vault/edit/<int:entry_id>", methods=["POST"])
@login_required
@family_required
def edit_vault_entry(current_family, entry_id):
    # (Validation remains the same)
    entry = VaultEntry.query.get_or_404(entry_id)
    # ... security checks ...

    original_category = entry.category
    entry.category = request.form.get("category", entry.category).strip()
    entry.title = request.form.get("title", entry.title).strip()
    entry.content = request.form.get("content", entry.content).strip()
    entry.author_id = current_user.id
    db.session.commit()

    # --- START OF FIX ---
    entry_html = render_template(
        "_vault_entry.html",
        entry=entry,
        current_user=current_user,
        current_family=current_family,
    )
    # --- END OF FIX ---

    return jsonify(
        {
            "success": True,
            "message": "Vault entry updated successfully!",
            "entry": {
                "id": entry.id,
                "category": entry.category,
                "original_category": original_category,
            },
            "entry_html": entry_html,
        }
    )


@app.route("/vault/delete", methods=["POST"])
@login_required
@family_required
def delete_vault_entry(current_family):
    # Security: Only the family owner (admin) can delete.
    if current_user.id != current_family.owner_id:
        # For AJAX, return a JSON error
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": False, "message": "Permission denied."}), 403
        flash("You do not have permission to delete this entry.", "danger")
        return redirect(url_for("vault"))

    entry_id = request.form.get("entry_id")
    entry = VaultEntry.query.get_or_404(entry_id)

    # Ensure the entry belongs to the correct family
    if entry.family_id == current_family.id:
        db.session.delete(entry)
        db.session.commit()
        # --- START OF CHANGE ---
        # REMOVE the flash() call for AJAX requests
        # flash("Vault entry deleted.", "info")

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            # ADD a message to the JSON response
            return jsonify({"success": True, "message": "Vault entry deleted."})
        # --- END OF CHANGE ---

    return redirect(url_for("vault"))


# --- END: NEW FAMILY VAULT ROUTES ---

# --- START: NEW CHORE VIEWING & INTERACTION ROUTES ---


# ... inside app.py, after the chore_list() function ...


@app.route("/api/chore_history/<string:start_date_str>")
@login_required
@family_required
def api_chore_history(current_family, start_date_str):
    # This API is for admins only
    if current_family.owner_id != current_user.id:
        return jsonify({"success": False, "error": "Permission denied"}), 403

    try:
        target_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"success": False, "error": "Invalid date format"}), 400

    start_of_week = target_date - timedelta(days=target_date.weekday())

    # --- START OF FIX ---
    # Define the missing date objects that the template needs
    prev_week_date = start_of_week - timedelta(days=7)
    next_week_date = start_of_week + timedelta(days=7)

    # Define the missing date for comparison
    today = date.today()
    start_of_current_week = today - timedelta(days=today.weekday())
    # --- END OF FIX ---

    assignments = (
        ChoreAssignment.query.filter(
            ChoreAssignment.family_id == current_family.id,
            ChoreAssignment.week_of == start_of_week,
        )
        .order_by(ChoreAssignment.user_id)
        .all()
    )

    assignments_by_user = {}
    for member in current_family.members:
        assignments_by_user[member] = []
    for assignment in assignments:
        if assignment.user in assignments_by_user:
            assignments_by_user[assignment.user].append(assignment)

    sorted_assignments = sorted(
        assignments_by_user.items(), key=lambda item: item[0].username
    )

    # Render both the grid AND the nav partials to HTML strings
    grid_html = render_template(
        "chore_history_grid.html", sorted_assignments=sorted_assignments
    )

    nav_html = render_template(
        "chore_history_nav.html",
        prev_week_date=prev_week_date,
        next_week_date=next_week_date,
        show_next_week=(next_week_date < start_of_current_week),
    )

    return jsonify(
        {
            "success": True,
            "grid_html": grid_html,
            "nav_html": nav_html,  # Add the new nav HTML to the response
            "week_display": start_of_week.strftime("%B %d, %Y"),
        }
    )


# --- END: NEW CHORE VIEWING & INTERACTION ROUTES ---

# --- START: NEW CHORE MANAGEMENT ROUTES ---


# REPLACE the existing /chores function with this one
@app.route("/chores")
@app.route("/chore_history/<string:start_date_str>")
@login_required
@family_required
def chores(current_family, start_date_str=None):
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())

    weekly_assignments = ChoreAssignment.query.filter(
        ChoreAssignment.family_id == current_family.id,
        ChoreAssignment.week_of == start_of_week,
    ).all()

    assignments_by_user = {}
    for member in current_family.members:
        assignments_by_user[member] = []
    for assignment in weekly_assignments:
        if assignment.user in assignments_by_user:
            assignments_by_user[assignment.user].append(assignment)

    # --- START: NEW PROGRESS CALCULATION LOGIC ---
    assignments_with_progress = []
    family_total_points = 0
    family_completed_points = 0

    for member, assignments in assignments_by_user.items():
        total_points = sum(a.chore.points for a in assignments)
        completed_points = sum(a.chore.points for a in assignments if a.is_complete)

        family_total_points += total_points
        family_completed_points += completed_points

        assignments_with_progress.append(
            {
                "member": member,
                "assignments": assignments,
                "progress": {
                    "total": total_points,
                    "completed": completed_points,
                    "percentage": (
                        int((completed_points / total_points * 100))
                        if total_points > 0
                        else 0
                    ),
                },
            }
        )

    # Sort the list by member username for consistent order
    assignments_with_progress.sort(key=lambda x: x["member"].username)
    # --- END: NEW PROGRESS CALCULATION LOGIC ---

    # --- Admin-Specific Data (unchanged from before) ---
    (
        family_chores,
        sorted_assignments_history,
        prev_week_date,
        next_week_date,
        show_next_week,
        history_start_of_week,
    ) = (None,) * 6

    if current_family.owner_id == current_user.id:
        family_chores = (
            Chore.query.filter_by(family_id=current_family.id)
            .order_by(Chore.name)
            .all()
        )
        target_date = (
            today - timedelta(days=today.weekday() + 7)
            if not start_date_str
            else datetime.strptime(start_date_str, "%Y-%m-%d").date()
        )
        history_start_of_week = target_date - timedelta(days=target_date.weekday())
        prev_week_date = history_start_of_week - timedelta(days=7)
        next_week_date = history_start_of_week + timedelta(days=7)
        history_assignments_query = (
            ChoreAssignment.query.filter(
                ChoreAssignment.family_id == current_family.id,
                ChoreAssignment.week_of == history_start_of_week,
            )
            .order_by(ChoreAssignment.user_id)
            .all()
        )
        history_assignments_by_user = {}
        for member in current_family.members:
            history_assignments_by_user[member] = []
        for assignment in history_assignments_query:
            if assignment.user in history_assignments_by_user:
                history_assignments_by_user[assignment.user].append(assignment)
        sorted_assignments_history = sorted(
            history_assignments_by_user.items(), key=lambda item: item[0].username
        )
        start_of_current_week = today - timedelta(days=today.weekday())
        show_next_week = next_week_date < start_of_current_week

    active_tab = "history" if start_date_str else "this-week"

    return render_template(
        "chores.html",
        current_family=current_family,
        assignments_with_progress=assignments_with_progress,  # Pass new data structure
        family_progress={  # Pass family totals
            "total": family_total_points,
            "completed": family_completed_points,
            "percentage": (
                int((family_completed_points / family_total_points * 100))
                if family_total_points > 0
                else 0
            ),
        },
        week_start_date=start_of_week,
        active_tab=active_tab,
        chores=family_chores,
        sorted_assignments_history=sorted_assignments_history,
        history_week_start_date=history_start_of_week,
        prev_week_date=prev_week_date,
        next_week_date=next_week_date,
        show_next_week=show_next_week,
    )


@app.route("/chores/add", methods=["POST"])
@login_required
@family_required
def add_chore(current_family):
    # ... (this function remains unchanged) ...
    if current_family.owner_id != current_user.id:
        return jsonify({"success": False, "message": "Permission denied."}), 403

    chore_name = request.form.get("chore_name")
    chore_points_str = request.form.get("chore_points")
    try:
        chore_points = int(chore_points_str)
    except (ValueError, TypeError):
        chore_points = 5

    if not chore_name:
        return (
            jsonify({"success": False, "message": "Chore name cannot be empty."}),
            400,
        )

    new_chore = Chore(name=chore_name, points=chore_points, family_id=current_family.id)
    db.session.add(new_chore)
    db.session.commit()

    return jsonify(
        {
            "success": True,
            "message": "Chore added successfully!",
            "chore": {
                "id": new_chore.id,
                "name": new_chore.name,
                "points": new_chore.points,
            },
        }
    )


@app.route("/chores/delete", methods=["POST"])
@login_required
@family_required
def delete_chore(current_family):
    # Security check: Only the owner can delete chores
    if current_family.owner_id != current_user.id:
        return jsonify({"success": False, "message": "Permission denied."}), 403

    chore_id = request.form.get("chore_id")
    chore_to_delete = Chore.query.get(chore_id)

    if chore_to_delete and chore_to_delete.family_id == current_family.id:
        db.session.delete(chore_to_delete)
        db.session.commit()
        return jsonify({"success": True, "message": "Chore deleted."})
    else:
        return jsonify({"success": False, "message": "Chore not found."}), 404


# ... inside app.py, after the delete_chore function ...


@app.route("/chores/generate", methods=["POST"])
@login_required
@family_required
def generate_chores(current_family):
    # Security check
    if current_family.owner_id != current_user.id:
        return jsonify({"success": False, "message": "Permission denied."}), 403

    # 1. Calculate the start of the current week (Monday)
    today = date.today()
    # weekday() returns 0 for Monday, 6 for Sunday.
    # Subtract current weekday from today to get back to Monday.
    start_of_week = today - timedelta(days=today.weekday())

    # 2. Check if assignments already exist for this week
    existing = ChoreAssignment.query.filter_by(
        family_id=current_family.id, week_of=start_of_week
    ).first()
    if existing:
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Chores have already been generated for the week of {start_of_week.strftime('%b %d')}.",
                }
            ),
            400,
        )

    # 3. Fetch necessary data
    chores = Chore.query.filter_by(family_id=current_family.id).all()
    members = current_family.members

    if not chores:
        return (
            jsonify(
                {"success": False, "message": "Chore bank is empty. Add chores first."}
            ),
            400,
        )
    if not members:
        # Should be impossible as owner is a member, but good to check
        return jsonify({"success": False, "message": "No members in family."}), 400

    # 4. The Distribution Algorithm (Simple Round-Robin)
    # We loop through chores and assign to members sequentially.
    new_assignments = []
    num_members = len(members)

    for i, chore in enumerate(chores):
        # Use modulo operator % to cycle through members
        assigned_member = members[i % num_members]

        assignment = ChoreAssignment(
            week_of=start_of_week,
            chore_id=chore.id,
            user_id=assigned_member.id,
            family_id=current_family.id,
        )
        new_assignments.append(assignment)

    # 5. Save to Database
    try:
        db.session.add_all(new_assignments)
        db.session.commit()
        count = len(new_assignments)
        # (Optional) In the future, we could emit a socket event here to notify everyone
        return jsonify(
            {
                "success": True,
                "message": f"Successfully assigned {count} chores for the week of {start_of_week.strftime('%b %d')}!",
            }
        )
    except Exception as e:
        db.session.rollback()
        print(f"Error generating chores: {e}")
        return (
            jsonify(
                {"success": False, "message": "Database error while generating chores."}
            ),
            500,
        )


@app.route("/list/<int:list_id>")
@login_required
@family_required
def view_list(current_family, list_id):
    list_to_view = ShoppingList.query.filter_by(
        id=list_id, family_id=current_family.id
    ).first_or_404()

    # --- START: THE FIX ---
    # Manually convert the list of Item objects into a list of dictionaries
    items_for_js = [
        {"id": item.id, "text": item.text, "done": item.done}
        for item in list_to_view.items
    ]

    # The template for displaying items on initial load still needs the sorted objects
    sorted_items_for_template = sorted(list_to_view.items, key=lambda x: x.done)

    return render_template(
        "view_list.html",
        current_family=current_family,
        list=list_to_view,
        items=sorted_items_for_template,  # For the initial HTML render
        initial_items_json=items_for_js,  # For the JavaScript window object
    )
    # --- END: THE FIX ---


# --- END: NEW CHORE MANAGEMENT ROUTES ---


# --- END: NEW CHORE MANAGEMENT ROUTES ---


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


@socketio.on("join_family_room")
def on_join_family_room(data):
    """A client wants to join a room to receive updates for a specific family."""
    family_id = data.get("family_id")
    if family_id:
        room = f"family_room_{family_id}"
        join_room(room)
        print(f"Client {request.sid} joined family room {room}")


@socketio.on("toggle_done")
def handle_toggle_done(data):
    if not current_user.is_authenticated:
        return  # Security: Ignore if user is not logged in

    item_id = data.get("item_to_toggle")
    item_to_toggle = Item.query.get(item_id)

    # Security check: User must be a member of the family that owns the item
    if item_to_toggle and current_user in item_to_toggle.list.family.members:
        # Perform the actual database update
        item_to_toggle.done = not item_to_toggle.done
        db.session.commit()

        # Broadcast the confirmed status back to ALL clients in the room
        # This ensures everyone's UI is in sync with the database
        emit(
            "item_toggled",
            {
                "list_id": item_to_toggle.list.id,
                "item_id": item_to_toggle.id,
                "done_status": item_to_toggle.done,
            },
            room=f"list_{item_to_toggle.list.id}",
        )


@socketio.on("toggle_chore")
def handle_toggle_chore(data):
    # This event handler is automatically login-protected
    # because SocketIO integrates with Flask-Login's session.
    if not current_user.is_authenticated:
        return  # Do nothing if user is not logged in

    assignment_id = data.get("assignment_id")
    assignment = ChoreAssignment.query.get(assignment_id)

    # Perform security and validation checks
    if not assignment:
        print(
            f"User {current_user.username} tried to toggle non-existent assignment {assignment_id}"
        )
        return

    # Ensure the user belongs to the same family as the assignment
    current_family_id = session.get("current_family_id")
    if not current_family_id or assignment.family_id != current_family_id:
        print(
            f"Permission denied for user {current_user.username} on assignment {assignment_id}"
        )
        return

    # User can toggle their own chores, or an Admin can toggle anyone's in the family
    family = Family.query.get(current_family_id)
    is_admin = family.owner_id == current_user.id
    is_own_chore = assignment.user_id == current_user.id

    if not (is_admin or is_own_chore):
        print(
            f"Permission denied for user {current_user.username} on assignment {assignment_id}"
        )
        return

    # Update the database
    assignment.is_complete = not assignment.is_complete
    db.session.commit()

    # Broadcast the change back to everyone, now with the correct SID
    emit(
        "chore_toggled",
        {
            "assignment_id": assignment.id,
            "is_complete": assignment.is_complete,
            "sid": request.sid,  # This now works correctly!
        },
        room=f"family_room_{assignment.family_id}",
    )


@socketio.on("save_meal")
def handle_save_meal(data):
    if not current_user.is_authenticated:
        return

    day = data.get("day")
    description = data.get("description", "").strip()
    notes = data.get("notes", "").strip()  # Get raw notes text
    current_family_id = session.get("current_family_id")
    meal_type = "Dinner"

    if not all([day, description, current_family_id]):
        return  # Ignore incomplete requests

    family = Family.query.get(current_family_id)
    if not family or current_user not in family.members:
        return  # Security check

    existing_meal = Meal.query.filter_by(
        family_id=current_family_id, day=day, meal_type=meal_type
    ).first()

    if existing_meal:
        existing_meal.description = description
        existing_meal.notes = notes  # Save the raw notes
        existing_meal.author_id = current_user.id
        meal_to_process = existing_meal
    else:
        new_meal = Meal(
            day=day,
            meal_type=meal_type,
            description=description,
            notes=notes,  # Save the raw notes
            family_id=current_family_id,
            author_id=current_user.id,
        )
        db.session.add(new_meal)
        meal_to_process = new_meal

    db.session.commit()

    # Prepare data to send back to clients
    meal_data = {
        "id": meal_to_process.id,
        "description": meal_to_process.description,
        "notes": meal_to_process.notes or "",  # Send raw notes for editing
        "notes_html": bleach.linkify(
            meal_to_process.notes or ""
        ),  # Send processed HTML for display
        "day": meal_to_process.day,
    }

    # Broadcast the update to everyone in the room
    emit(
        "meal_updated",
        {"meal": meal_data, "sid": request.sid},
        room=f"family_room_{current_family_id}",
    )

    # Return the data to the original sender's callback function
    return meal_data


# --- END: NEW SOCKETIO EVENT HANDLERS ---

# --- ADD THIS ERROR HANDLER at the end of app.py ---


@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status code explicitly
    return render_template("404.html"), 404


if __name__ == "__main__":
    # This block is now ONLY for LOCAL development.
    # It will not be executed when deployed on Render.
    print("Starting Flask app in local debug mode...")
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
