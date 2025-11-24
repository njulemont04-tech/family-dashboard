import eventlet

eventlet.monkey_patch()

import os
import cloudinary
import cloudinary.uploader
import bleach
import calendar
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
from sqlalchemy import text
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
from flask_babel import Babel, gettext as _

from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, YEARLY
from dateutil.relativedelta import relativedelta

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
# --- START: NEW, EXPLICIT BABEL CONFIGURATION ---


# --- START: REVISED BABEL CONFIGURATION FOR USER-CONTROLLED LANGUAGE ---


# Define the language selection function first.
def get_locale():
    try:
        # Priority 1: Use the language the user explicitly chose, stored in the session.
        if "language" in session:
            return session["language"]

        # Priority 2: For logged-in users, check if they have a saved preference.
        if current_user.is_authenticated and current_user.language:
            # Also store it in the session for consistency.
            session["language"] = current_user.language
            return current_user.language

        # Priority 3: As a final fallback, default to English.
        return "en"

    except RuntimeError:
        # This handles the case when the code is run from the command line (e.g., flask db).
        return "en"


# Now, initialize the Babel object without the app instance
babel = Babel()

# Set the language config on the app
app.config["LANGUAGES"] = {
    "en": "English",
    "fr": "Français",
    "nl": "Nederlands",  # <-- ADD THIS LINE
}

# FINALLY, initialize Babel with the app AND pass our function directly
babel.init_app(app, locale_selector=get_locale)

# --- END: REVISED BABEL CONFIGURATION ---


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
    language = db.Column(db.String(5), nullable=True)  # <-- ADD THIS LINE
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

    # Timing
    date = db.Column(db.Date, nullable=False)  # The START date of the series or event
    time = db.Column(db.Time, nullable=True)  # Start Time
    end_time = db.Column(db.Time, nullable=True)  # End Time (Duration)
    is_all_day = db.Column(db.Boolean, default=False)

    # Appearance
    category = db.Column(db.String(50), default="general")
    color = db.Column(db.String(20), default="#0d6efd")

    # Recurrence Engine (The Efficient Part)
    # frequency: 'none', 'daily', 'weekly', 'monthly', 'yearly'
    recurrence_type = db.Column(db.String(20), default="none")
    # interval: e.g., 2 means "Every 2 weeks"
    recurrence_interval = db.Column(db.Integer, default=1)
    # end_date: When does the repeating stop? (Null means forever)
    recurrence_end_date = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    family_id = db.Column(db.Integer, db.ForeignKey("family.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    author = db.relationship("User", backref="events")


class Meal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(20), nullable=False)
    meal_type = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    week_of = db.Column(db.Date, nullable=False)
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

    # --- NEW COLUMNS ---
    frequency_days = db.Column(db.Integer, nullable=False, default=7)
    last_generated_date = db.Column(db.Date, nullable=True)
    # -------------------

    family_id = db.Column(db.Integer, db.ForeignKey("family.id"), nullable=False)

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
            flash(_("Please select a space to continue."), "info")
            return redirect(url_for("families"))

        family = Family.query.get(family_id)
        if not family or current_user not in family.members:
            session.pop("current_family_id", None)  # Clear invalid session data
            flash(
                _(
                    "You are not a member of the selected space, or it no longer exists."
                ),
                "warning",
            )
            return redirect(url_for("families"))

        # If all checks pass, inject the 'current_family' object into the route
        return f(current_family=family, *args, **kwargs)

    return decorated_function


# --- END: ADD THIS NEW DECORATOR ---


# ADD THIS NEW FUNCTION TO APP.PY

# --- ADD THIS TO app.py ---


def set_target_blank(attrs, new=False):
    """Helper to force links to open in a new tab"""
    attrs[(None, "target")] = "_blank"
    attrs[(None, "rel")] = "noopener noreferrer"
    return attrs


@app.template_filter("linkify")
def linkify_filter(text):
    """Jinja filter to make links clickable in templates"""
    if not text:
        return ""
    return bleach.linkify(text, callbacks=[set_target_blank])


@app.context_processor
def inject_today_date():
    """Injects the current day of the month into all templates."""
    from datetime import date

    today = date.today()
    return dict(current_day=today.day)


@app.context_processor
def inject_permissions():
    """
    Injects a global 'is_admin' variable into all templates.
    It respects the 'view_as_member' toggle for testing purposes.
    """
    is_admin = False

    # 1. Check if user is logged in and a family is selected
    if current_user.is_authenticated:
        current_family_id = session.get("current_family_id")
        if current_family_id:
            # We query the family here (or get it if you have it cached)
            # Note: Family.query.get might be slightly heavy to do on every request,
            # but for a family app it's totally fine.
            family = Family.query.get(current_family_id)

            if family and family.owner_id == current_user.id:
                # User IS the owner...
                # BUT check if they turned on "View as Member" mode
                if not session.get("view_as_member"):
                    is_admin = True

    return dict(is_admin=is_admin)


@app.route("/toggle_view_mode")
@login_required
def toggle_view_mode():
    """Toggles the session flag to pretend to be a regular member."""
    if session.get("view_as_member"):
        session.pop("view_as_member")
        flash("Exited Member View. You are Admin again.", "info")
    else:
        session["view_as_member"] = True
        flash("Viewing as a regular Member.", "success")

    # Redirect back to the page they were just on
    return redirect(request.referrer or url_for("dashboard"))


# --- START: ADD THIS NEW FUNCTION ---
@app.context_processor
def inject_app_config():
    """Injects the app config into all templates."""
    return dict(app=app)


# --- END: ADD THIS NEW FUNCTION ---


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
            flash(_("Invalid username or password"), "danger")
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
            flash(_("Username already exists."), "warning")
            return redirect(url_for("register"))
        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
        new_user = User(username=username, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash(_("Registration successful! Please log in."), "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/set_language/<lang>")
def set_language(lang=None):
    # Check if the selected language is one of our supported languages
    if lang in app.config["LANGUAGES"]:
        # Store the user's choice in the session
        session["language"] = lang
        # If the user is logged in, also save their preference to their profile
        if current_user.is_authenticated:
            current_user.language = lang
            db.session.commit()
            flash(_("Language updated!"), "success")

    # Always redirect back to the settings page after changing the language.
    return redirect(url_for("settings"))


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
        flash(
            _('Successfully created and selected family "%(name)s"!', name=family_name),
            "success",
        )
        return redirect(url_for("dashboard"))
    else:
        flash(_("Family name cannot be empty."), "danger")
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
        flash(_("You are not a member of that family."), "danger")
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
                    _(
                        "Welcome! To get started, please create a private space for your household."
                    ),
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
        flash(_("The family you had selected is no longer available."), "warning")
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
        # <--- TRANSLATED
        message = _('User "%(username)s" not found.', username=username_to_invite)
        if is_ajax:
            return json_response(False, message)
        flash(message, "danger")
    elif user_to_invite in family.members:
        # <--- TRANSLATED
        message = _(
            'User "%(username)s" is already a member of this family.',
            username=username_to_invite,
        )
        if is_ajax:
            return json_response(False, message)
        flash(message, "info")
    else:
        family.members.append(user_to_invite)
        db.session.commit()
        # <--- TRANSLATED
        message = _(
            'Successfully invited "%(username)s" to the family!',
            username=username_to_invite,
        )
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
        flash(_("You do not have permission to delete this list."), "danger")
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
def calendar_view(current_family):
    # 1. Get View Range (Month)
    try:
        year = int(request.args.get("year", datetime.utcnow().year))
        month = int(request.args.get("month", datetime.utcnow().month))
    except ValueError:
        year = datetime.utcnow().year
        month = datetime.utcnow().month

    cal = calendar.Calendar(firstweekday=0)
    month_calendar = cal.monthdatescalendar(year, month)

    # Calculate the exact start and end of the visible calendar grid
    view_start = month_calendar[0][0]  # e.g., Oct 28th (prev month)
    view_end = month_calendar[-1][-1]  # e.g., Dec 6th (next month)

    # 2. Fetch Events
    # We fetch ALL repeating events (because they might define a rule starting in 2023 that applies now)
    # AND single events that happen in this view.
    raw_events = Event.query.filter(
        Event.family_id == current_family.id,
        db.or_(
            Event.recurrence_type != "none",  # All repeating events
            db.and_(
                Event.date >= view_start, Event.date <= view_end
            ),  # Single events in range
        ),
    ).all()

    events_by_day = {}

    # 3. The Expansion Engine
    for event in raw_events:
        event_instances = []

        if event.recurrence_type == "none":
            # It's a single event, just add it directly
            event_instances.append(event.date)
        else:
            # It's a repeating event. Calculate the dates.

            # Map string frequency to dateutil constants
            freq_map = {
                "daily": DAILY,
                "weekly": WEEKLY,
                "monthly": MONTHLY,
                "yearly": YEARLY,
            }

            if event.recurrence_type in freq_map:
                # Stop calculating either at the event's end date OR the end of the view
                until_date = view_end
                if event.recurrence_end_date and event.recurrence_end_date < view_end:
                    until_date = event.recurrence_end_date

                # Generate the dates
                # Note: We convert date to datetime for rrule, then back to date
                generated_dates = rrule(
                    freq_map[event.recurrence_type],
                    dtstart=datetime.combine(event.date, datetime.min.time()),
                    interval=event.recurrence_interval,
                    until=datetime.combine(until_date, datetime.min.time()),
                )

                # Filter strictly for the view range
                for dt in generated_dates:
                    d = dt.date()
                    if d >= view_start and d <= view_end:
                        event_instances.append(d)

        # 4. Create "Virtual" Event Objects for the Template
        for instance_date in event_instances:
            day_num = instance_date.day
            # We must use the specific date object from the calendar grid to match keys correctly
            # But since your template uses day numbers (1, 2, 3) for the current month,
            # we need to be careful with previous/next month days.

            # For this specific logic, we are grouping by DATE OBJECT if possible,
            # or we stick to your day number logic if it's strictly within the current month.

            # SIMPLIFICATION: Let's group by the actual date string "YYYY-MM-DD"
            # You will need to update calendar.html to match this slightly.

            # For now, let's keep your integer logic for the current month:
            if instance_date.month == month:
                if day_num not in events_by_day:
                    events_by_day[day_num] = []

                # We create a dictionary copy so we can change the date for this specific instance
                # while keeping the original event data (title, color)
                virtual_event = {
                    "id": event.id,
                    "title": event.title,
                    "time": event.time,
                    "end_time": event.end_time,
                    "color": event.color,
                    "is_all_day": event.is_all_day,
                    "author": event.author,
                    "author_id": event.author_id,
                    # Add formatted time for the badge
                    "display_time": event.time.strftime("%H:%M") if event.time else "",
                }
                # If there is an end time, append it
                if event.end_time:
                    virtual_event[
                        "display_time"
                    ] += f" - {event.end_time.strftime('%H:%M')}"
                events_by_day[day_num].append(virtual_event)

    # ... sort events by time ...
    for day_num in events_by_day:
        events_by_day[day_num].sort(key=lambda x: x["display_time"])

    # ... (Rest of your navigation logic: prev_month_date, next_month_date) ...
    current_date = date(year, month, 1)
    _, num_days = calendar.monthrange(year, month)
    prev_month_date = current_date - timedelta(days=1)
    next_month_date = current_date + timedelta(days=num_days)

    return render_template(
        "calendar.html",
        current_family=current_family,
        month_calendar=month_calendar,
        events_by_day=events_by_day,
        current_date=current_date,
        prev_month_date=prev_month_date,
        next_month_date=next_month_date,
        today=date.today(),
    )


@app.route("/add_event", methods=["POST"])
@login_required
@family_required
def add_event(current_family):
    # ... Get basic fields ...
    title = request.form.get("title")
    date_str = request.form.get("date")
    time_str = request.form.get("time")

    # ... Get new fields ...
    is_all_day = request.form.get("is_all_day") == "on"
    color = request.form.get("color", "#0d6efd")

    recurrence_type = request.form.get("recurrence_type", "none")
    recurrence_interval = int(request.form.get("recurrence_interval", 1))
    recurrence_end_str = request.form.get("recurrence_end_date")

    if title and date_str:
        base_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        time_obj = None
        if not is_all_day and time_str:
            time_obj = datetime.strptime(time_str, "%H:%M").time()

        recurrence_end = None
        if recurrence_end_str:
            recurrence_end = datetime.strptime(recurrence_end_str, "%Y-%m-%d").date()

        new_event = Event(
            title=title,
            date=base_date,
            time=time_obj,
            is_all_day=is_all_day,
            color=color,
            recurrence_type=recurrence_type,
            recurrence_interval=recurrence_interval,
            recurrence_end_date=recurrence_end,
            family_id=current_family.id,
            author_id=current_user.id,
        )

        db.session.add(new_event)
        db.session.commit()

        # --- CORRECT INDENTATION: Line up exactly with db.session.commit ---

        socketio.emit("refresh_calendar", {}, room=f"family_room_{current_family.id}")

        socketio.emit(
            "new_activity",
            {"feature": "calendar", "timestamp": datetime.utcnow().isoformat()},
            room=f"family_room_{current_family.id}",
        )

        return jsonify({"success": True})

    # This return is outside the 'if' block (for when validation fails)
    return jsonify({"success": False}), 400


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

    return redirect(url_for("calendar_view"))  # <--- CORRECTED LINE


@app.route("/edit_event/<int:event_id>", methods=["POST"])
@login_required
@family_required
def edit_event(current_family, event_id):
    event_to_edit = Event.query.get_or_404(event_id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # Security check: User must be the author of the event to edit it
    if event_to_edit.author_id != current_user.id:
        if is_ajax:
            return jsonify({"success": False, "message": "Permission denied."}), 403
        flash(_("You do not have permission to edit this event."), "danger")
        return redirect(url_for("calendar_view"))

    # Get data from the form
    title = request.form.get("title")
    time_str = request.form.get("time")

    if title and time_str:
        # Update event in the database
        event_to_edit.title = title
        event_to_edit.time = datetime.strptime(time_str, "%H:%M").time()
        db.session.commit()

        # Prepare data to broadcast
        event_data = {
            "id": event_to_edit.id,
            "title": event_to_edit.title,
            "date": event_to_edit.date.strftime("%Y-%m-%d"),
            "time": event_to_edit.time.strftime("%H:%M"),
            "author": {
                "username": event_to_edit.author.username,
                "id": event_to_edit.author.id,
            },
            # Add formatted time for consistency with view modal
            "formatted_time": event_to_edit.time.strftime("%H:%M"),
        }

        # Emit a new event to notify all clients of the update
        socketio.emit(
            "event_updated",
            {"event": event_data},
            room=f"family_room_{current_family.id}",
        )

        if is_ajax:
            return jsonify({"success": True, "event": event_data})

    return redirect(url_for("calendar_view"))


# --- REFACTOR: MEAL PLANNER ROUTES ---


@app.route("/meal_planner")
@login_required
@family_required
def meal_planner(current_family):
    # Get the desired week offset from the URL, default to 0 (this week)
    try:
        week_offset = int(request.args.get("week_offset", 0))
    except ValueError:
        week_offset = 0

    # Enforce the "one week max" rule
    if week_offset not in [0, 1]:
        week_offset = 0

    today = date.today()
    # Calculate the start of THIS week (the real one)
    start_of_this_week = today - timedelta(days=today.weekday())
    # Calculate the start of the week we actually want to display
    start_of_target_week = start_of_this_week + timedelta(weeks=week_offset)

    # Fetch meals ONLY for the target week
    family_meals = Meal.query.filter_by(
        family_id=current_family.id, week_of=start_of_target_week
    ).all()

    meal_plan_for_template = {meal.day: meal for meal in family_meals}
    meal_plan_for_json = {
        meal.day: {
            "id": meal.id,
            "description": meal.description,
            "notes": meal.notes or "",
            # ADD THIS LINE:
            "notes_html": bleach.linkify(
                meal.notes or "", callbacks=[set_target_blank]
            ),
        }
        for meal in family_meals
    }

    days_of_week = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    week_schedule = []
    for i, day_name in enumerate(days_of_week):
        current_date = start_of_target_week + timedelta(days=i)
        week_schedule.append({"name": day_name, "date": current_date})

    return render_template(
        "meal_planner.html",
        current_family=current_family,
        meal_plan=meal_plan_for_template,
        meal_plan_json=json.dumps(meal_plan_for_json),
        week_schedule=week_schedule,
        today=today,
        week_offset=week_offset,  # Pass the offset for the navigation UI
        start_of_target_week=start_of_target_week,  # Pass the week's date for the modal
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


# In app.py, REPLACE the entire bulletin_board route.


@app.route("/bulletin_board")
@login_required
@family_required
def bulletin_board(current_family):
    # --- START: REVISED LOGIC FOR PINNING ---
    # Auto-deletion logic remains the same
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    Note.query.filter(
        Note.family_id == current_family.id,
        Note.timestamp < cutoff_date,
        Note.is_pinned == False,
    ).delete(synchronize_session=False)
    db.session.commit()

    # Fetch Pinned and Unpinned notes separately
    pinned_notes = (
        Note.query.filter_by(family_id=current_family.id, is_pinned=True)
        .order_by(Note.timestamp.desc())  # Pinned notes are newest first
        .all()
    )

    unpinned_notes = (
        Note.query.filter_by(family_id=current_family.id, is_pinned=False)
        .order_by(Note.timestamp.asc())  # Chat messages are oldest first
        .all()
    )

    return render_template(
        "bulletin_board.html",
        current_family=current_family,
        pinned_notes=pinned_notes,  # Pass pinned notes
        unpinned_notes=unpinned_notes,  # Pass unpinned notes
    )


# --- END: REVISED LOGIC FOR PINNING ---


# --- END: MODIFIED LOGIC ---


@app.route("/internal/render_bulletin_post/<int:note_id>")
@login_required
@family_required
def render_bulletin_post(current_family, note_id):
    """
    Internal route to render a single bulletin post partial.
    Used by JavaScript to get clean HTML for new posts via websockets.
    """
    note = Note.query.get_or_404(note_id)
    # Security check: ensure the note belongs to the user's current family
    if note.family_id != current_family.id:
        return "", 403  # Return forbidden if not authorized

    # We use render_template_string because we are including a partial
    # that needs the full Jinja context (like `current_user`).
    return render_template_string('{% include "_bulletin_post.html" %}', post=note)


# In app.py, ADD THIS ROUTE.
# A good place is right after the 'render_bulletin_post' function.


# In app.py, REPLACE the existing render_pinned_post function with this one.


# In app.py, REPLACE the temporary debug function with this FINAL version.


@app.route("/internal/render_pinned_post/<int:note_id>")
@login_required
@family_required
def render_pinned_post(current_family, note_id):
    """
    Internal route to render a single PINNED post partial.
    Used by JavaScript to get clean HTML for pinned notes.
    """
    note = Note.query.get_or_404(note_id)
    # Security check
    if note.family_id != current_family.id:
        return "", 403

    # --- THE FIX IS LIKELY A TYPO IN THIS FILENAME ---
    # Verify that your file is named EXACTLY "_pinned_post_card.html"
    return render_template_string('{% include "_pinned_post_card.html" %}', post=note)


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
@family_required
def pin_note(current_family):
    note_id = request.form.get("note_id")
    note_to_pin = Note.query.get(note_id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # Basic security check
    if not note_to_pin or note_to_pin.family_id != current_family.id:
        if is_ajax:
            return jsonify({"success": False, "message": "Note not found."}), 404
        return redirect(url_for("bulletin_board"))

    # --- START: NEW GRANULAR PERMISSION LOGIC ---
    is_admin = current_user.id == current_family.owner_id
    is_author = current_user.id == note_to_pin.author_id

    # Determine if the user is trying to PIN or UNPIN
    if note_to_pin.is_pinned:
        # Action is UNPINNING: Allowed if user is the author OR the admin.
        if not (is_author or is_admin):
            if is_ajax:
                return (
                    jsonify(
                        {"success": False, "message": "Permission denied to unpin."}
                    ),
                    403,
                )
            flash(_("You do not have permission to unpin this note."), "danger")
            return redirect(url_for("bulletin_board"))
    else:
        # Action is PINNING: Allowed ONLY if user is the author.
        if not is_author:
            if is_ajax:
                return (
                    jsonify({"success": False, "message": "Permission denied to pin."}),
                    403,
                )
            flash(_("You can only pin your own messages."), "danger")
            return redirect(url_for("bulletin_board"))
    # --- END: NEW GRANULAR PERMISSION LOGIC ---

    # If all checks pass, proceed with the action
    note_to_pin.is_pinned = not note_to_pin.is_pinned
    db.session.commit()

    socketio.emit(
        "note_pinned",
        {
            "note_id": note_to_pin.id,
            "is_pinned": note_to_pin.is_pinned,
        },
        room=f"family_room_{note_to_pin.family_id}",
    )

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
                flash(_("Avatar updated successfully!"), "success")
            except Exception as e:
                flash(_("Error uploading image: %(error)s", error=e), "danger")
        else:
            flash(_("No file selected."), "warning")
    return redirect(url_for("profile"))


# In app.py, add this new route after the upload_avatar route.


@app.route("/profile/change_password", methods=["POST"])
@login_required
def change_password():
    old_password = request.form.get("old_password")
    new_password = request.form.get("new_password")

    # Check if the old password is correct
    if not bcrypt.check_password_hash(current_user.password_hash, old_password):
        flash(_("Incorrect old password. Please try again."), "danger")
        return redirect(url_for("profile"))

    # Hash the new password and update the user
    hashed_password = bcrypt.generate_password_hash(new_password).decode("utf-8")
    current_user.password_hash = hashed_password
    db.session.commit()

    flash(_("Your password has been updated successfully!"), "success")
    return redirect(url_for("profile"))


# --- START: NEW SETTINGS ROUTE ---
@app.route("/settings")
@login_required
def settings():
    # Note: We don't use @family_required here because settings are user-specific,
    # and should be accessible even if a family space isn't selected.
    return render_template("settings.html", title=_("Settings"))


# --- END: NEW SETTINGS ROUTE ---


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
        flash(_("You do not have permission to delete this entry."), "danger")
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
    if current_family.owner_id != current_user.id:
        return jsonify({"success": False, "message": "Permission denied."}), 403

    chore_name = request.form.get("chore_name")
    chore_points = int(request.form.get("chore_points", 5))
    # NEW: Get frequency
    frequency_days = int(request.form.get("frequency_days", 7))

    if not chore_name:
        return (
            jsonify({"success": False, "message": "Chore name cannot be empty."}),
            400,
        )

    new_chore = Chore(
        name=chore_name,
        points=chore_points,
        family_id=current_family.id,
        frequency_days=frequency_days,  # Save it
    )
    db.session.add(new_chore)
    db.session.commit()

    return jsonify(
        {
            "success": True,
            "message": "Chore added!",
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
    # Use your permission check
    if current_family.owner_id != current_user.id:
        return jsonify({"success": False, "message": "Permission denied."}), 403

    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())

    # Check if ANY assignments exist for THIS specific week
    existing = ChoreAssignment.query.filter_by(
        family_id=current_family.id, week_of=start_of_week
    ).first()

    if existing:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Chores have already been generated for this week.",
                }
            ),
            400,
        )

    chores = Chore.query.filter_by(family_id=current_family.id).all()
    members = current_family.members

    if not chores:
        return jsonify({"success": False, "message": "Chore bank is empty."}), 400

    new_assignments = []
    # Use ISO week number to ensure rotation changes every week
    current_week_number = start_of_week.isocalendar()[1]
    assignment_index = 0

    for chore in chores:
        # --- LOGIC: IS THIS CHORE DUE? ---
        is_due = False

        if chore.last_generated_date is None:
            # Never been done? It's due.
            is_due = True
        else:
            # Calculate days passed since last generation
            days_since = (today - chore.last_generated_date).days
            # If enough time has passed (give 3 days leeway for "Weekly" to trigger on different weekdays)
            if days_since >= (chore.frequency_days - 3):
                is_due = True

        if is_due:
            # Assign to a member using rotation logic
            num_members = len(members)
            member_index = (assignment_index + current_week_number) % num_members
            assigned_member = members[member_index]

            assignment = ChoreAssignment(
                week_of=start_of_week,
                chore_id=chore.id,
                user_id=assigned_member.id,
                family_id=current_family.id,
            )
            new_assignments.append(assignment)

            # Mark this chore as generated TODAY
            chore.last_generated_date = start_of_week

            # Move to the next member for the next chore
            assignment_index += 1

    if not new_assignments:
        return jsonify(
            {
                "success": True,
                "message": "No chores are due this week based on frequency settings.",
            }
        )

    db.session.add_all(new_assignments)
    db.session.commit()

    return jsonify(
        {
            "success": True,
            "message": f"Generated {len(new_assignments)} chores due this week!",
        }
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


@app.route("/healthz")
def health_check():
    """A simple health check endpoint for the cron job to ping."""
    return "OK", 200


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
    notes = data.get("notes", "").strip()
    week_of_str = data.get("week_of")  # <-- Get the week date string
    current_family_id = session.get("current_family_id")
    meal_type = "Dinner"

    if not all([day, description, current_family_id, week_of_str]):
        return  # Ignore incomplete requests

    try:
        # Convert the string back to a date object
        week_of_date = datetime.strptime(week_of_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return  # Invalid date format

    family = Family.query.get(current_family_id)
    if not family or current_user not in family.members:
        return

    existing_meal = Meal.query.filter_by(
        family_id=current_family_id,
        day=day,
        meal_type=meal_type,
        week_of=week_of_date,  # <-- Use the date in the query
    ).first()

    if existing_meal:
        existing_meal.description = description
        existing_meal.notes = notes
        existing_meal.author_id = current_user.id
        meal_to_process = existing_meal
    else:
        new_meal = Meal(
            day=day,
            meal_type=meal_type,
            description=description,
            notes=notes,
            family_id=current_family_id,
            author_id=current_user.id,
            week_of=week_of_date,  # <-- Set the date when creating a new meal
        )
        db.session.add(new_meal)
        meal_to_process = new_meal

    db.session.commit()

    meal_data = {
        "id": meal_to_process.id,
        "description": meal_to_process.description,
        "notes": meal_to_process.notes or "",
        # UPDATE THIS LINE BELOW:
        "notes_html": bleach.linkify(
            meal_to_process.notes or "", callbacks=[set_target_blank]
        ),
        "day": meal_to_process.day,
    }

    emit(
        "meal_updated",
        {"meal": meal_data, "sid": request.sid},
        room=f"family_room_{current_family_id}",
    )
    return meal_data


# --- END: NEW SOCKETIO EVENT HANDLERS ---

# --- ADD THIS ERROR HANDLER at the end of app.py ---


@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status code explicitly
    return render_template("404.html"), 404


@app.route("/db_fix_calendar_v2")
@login_required
@family_required
def db_fix_calendar_v2(current_family):
    if current_family.owner_id != current_user.id:
        return "Unauthorized", 403
    try:
        with db.engine.connect() as conn:
            conn.execute(
                text("ALTER TABLE event ADD COLUMN IF NOT EXISTS end_time TIME")
            )
            conn.execute(
                text(
                    "ALTER TABLE event ADD COLUMN IF NOT EXISTS is_all_day BOOLEAN DEFAULT FALSE"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE event ADD COLUMN IF NOT EXISTS category VARCHAR(50) DEFAULT 'general'"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE event ADD COLUMN IF NOT EXISTS color VARCHAR(20) DEFAULT '#0d6efd'"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE event ADD COLUMN IF NOT EXISTS recurrence_type VARCHAR(20) DEFAULT 'none'"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE event ADD COLUMN IF NOT EXISTS recurrence_interval INTEGER DEFAULT 1"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE event ADD COLUMN IF NOT EXISTS recurrence_end_date DATE"
                )
            )
            conn.execute(text("ALTER TABLE event ALTER COLUMN time DROP NOT NULL"))
            conn.commit()
        return "Calendar V2 Database Updated!"
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    # This block is for LOCAL development only.
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
