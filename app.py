import os
import re
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())

# Fetch MongoDB URI from environment variables (DevSecOps Best Practice)
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/guestbook_db")
client = MongoClient(MONGO_URI)
db = client.get_default_database("guestbook_db")

# Collections
entries_collection = db.entries
counter_collection = db.counters
users_collection = db.users

# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'


class User(UserMixin):
    def __init__(self, user_doc):
        self.id = str(user_doc["_id"])
        self.nickname = user_doc["nickname"]
        self.first_name = user_doc.get("first_name", "")
        self.last_name = user_doc.get("last_name", "")
        self.role = user_doc.get("role", "user")


@login_manager.user_loader
def load_user(user_id):
    user_doc = users_collection.find_one({"_id": ObjectId(user_id)})
    return User(user_doc) if user_doc else None


# --- Seed Admin from Environment Variables ---
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
if ADMIN_USERNAME and ADMIN_PASSWORD:
    existing_admin = users_collection.find_one({"nickname": ADMIN_USERNAME})
    if not existing_admin:
        users_collection.insert_one({
            "first_name": ADMIN_USERNAME,
            "last_name": "",
            "nickname": ADMIN_USERNAME,
            "password_hash": generate_password_hash(ADMIN_PASSWORD),
            "role": "admin"
        })
        print(f"Seeded admin user: {ADMIN_USERNAME}")


# --- Auth Routes ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        nickname = request.form.get('nickname', '').strip()
        password = request.form.get('password')
        confirm = request.form.get('confirm')

        if not first_name or not re.match(r'^[A-Za-z ]+$', first_name):
            flash('First name must contain only letters and spaces.', 'danger')
            return redirect(url_for('register'))
        if last_name and not re.match(r'^[A-Za-z ]+$', last_name):
            flash('Last name must contain only letters and spaces.', 'danger')
            return redirect(url_for('register'))
        if len(nickname) < 3 or len(nickname) > 30 or not re.match(r'^[A-Za-z0-9_]+$', nickname):
            flash('Nickname must be 3-30 characters (letters, numbers, underscores only).', 'danger')
            return redirect(url_for('register'))
        if not password or len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return redirect(url_for('register'))
        if not re.search(r'[A-Za-z]', password) or not re.search(r'[^A-Za-z]', password):
            flash('Password must contain at least 1 letter and 1 non-letter character (number/symbol).', 'danger')
            return redirect(url_for('register'))
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))
        if users_collection.find_one({"nickname": {"$regex": f"^{re.escape(nickname)}$", "$options": "i"}}):
            flash('Nickname already taken.', 'danger')
            return redirect(url_for('register'))

        users_collection.insert_one({
            "first_name": first_name,
            "last_name": last_name,
            "nickname": nickname,
            "password_hash": generate_password_hash(password),
            "role": "user"
        })
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nickname = request.form.get('nickname')
        password = request.form.get('password')

        user_doc = users_collection.find_one({"nickname": nickname})
        if user_doc and check_password_hash(user_doc["password_hash"], password):
            login_user(User(user_doc))
            flash(f'Welcome back, {nickname}!', 'success')
            return redirect(url_for('index'))

        flash('Invalid nickname or password.', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm = request.form.get('confirm')

        # Validate name fields (same rules as register)
        if not first_name or not re.match(r'^[A-Za-z ]+$', first_name):
            flash('First name must contain only letters and spaces.', 'danger')
            return redirect(url_for('profile'))
        if last_name and not re.match(r'^[A-Za-z ]+$', last_name):
            flash('Last name must contain only letters and spaces.', 'danger')
            return redirect(url_for('profile'))

        # Fetch current user document to verify current password
        user_doc = users_collection.find_one({"_id": ObjectId(current_user.get_id())})
        if not user_doc or not check_password_hash(user_doc["password_hash"], current_password):
            flash('Incorrect current password.', 'danger')
            return redirect(url_for('profile'))

        update_data = {
            "first_name": first_name,
            "last_name": last_name
        }

        # If new_password: validate it (min 8, letter + non-letter), hash it, update
        if new_password:
            if len(new_password) < 8:
                flash('Password must be at least 8 characters.', 'danger')
                return redirect(url_for('profile'))
            if not re.search(r'[A-Za-z]', new_password) or not re.search(r'[^A-Za-z]', new_password):
                flash('Password must contain at least 1 letter and 1 non-letter character (number/symbol).', 'danger')
                return redirect(url_for('profile'))
            if new_password != confirm:
                flash('Passwords do not match.', 'danger')
                return redirect(url_for('profile'))
            
            update_data["password_hash"] = generate_password_hash(new_password)

        users_collection.update_one(
            {"_id": ObjectId(current_user.get_id())},
            {"$set": update_data}
        )

        flash('Profile updated!', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html')


# --- Main Routes ---

@app.route('/', methods=['GET'])
def index():
    # 1. READ & UPDATE: Increment global visit counter
    counter_doc = counter_collection.find_one_and_update(
        {"_id": "global_visits"},
        {"$inc": {"count": 1}},
        upsert=True,
        return_document=True
    )
    visit_count = counter_doc["count"]

    # 2. READ: Fetch all guestbook entries
    entries = list(entries_collection.find().sort("_id", -1))

    return render_template('index.html', entries=entries, visit_count=visit_count)


@app.route('/create', methods=['POST'])
@login_required
def create():
    # 3. CREATE: Add new entry (linked to the logged-in user)
    message = request.form.get('message')
    if message:
        full_name = f"{current_user.first_name} {current_user.last_name}".strip()
        entries_collection.insert_one({
            "name": full_name,
            "message": message,
            "user_id": ObjectId(current_user.get_id())
        })
        flash('Entry added successfully!', 'success')
    return redirect(url_for('index'))


@app.route('/update/<id>', methods=['POST'])
@login_required
def update(id):
    # 4. UPDATE: Modify an existing message
    entry = entries_collection.find_one({"_id": ObjectId(id)})
    if not entry:
        flash('Entry not found.', 'danger')
        return redirect(url_for('index'))

    entry_user_id = entry.get("user_id")
    user_id = ObjectId(current_user.get_id())
    is_admin = current_user.role == "admin"

    if entry_user_id != user_id and not is_admin:
        flash('You can only edit your own messages.', 'danger')
        return redirect(url_for('index'))

    new_message = request.form.get('message')
    if new_message:
        entries_collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"message": new_message}}
        )
        flash('Message updated!', 'success')
    return redirect(url_for('index'))


@app.route('/delete/<id>', methods=['POST'])
@login_required
def delete(id):
    # 5. DELETE: Remove an entry
    entry = entries_collection.find_one({"_id": ObjectId(id)})
    if not entry:
        flash('Entry not found.', 'danger')
        return redirect(url_for('index'))

    entry_user_id = entry.get("user_id")
    user_id = ObjectId(current_user.get_id())
    is_admin = current_user.role == "admin"

    if entry_user_id != user_id and not is_admin:
        flash('You can only delete your own messages.', 'danger')
        return redirect(url_for('index'))

    entries_collection.delete_one({"_id": ObjectId(id)})
    flash('Entry deleted.', 'success')
    return redirect(url_for('index'))


if __name__ == '__main__':
    # Cloud Run binds to the PORT environment variable automatically
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)