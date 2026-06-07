# Features for FinalProject-PSO-B-12

This document describes three independent features to implement on the digital guestbook project. Each person picks one feature, implements it on their own branch, and opens a PR to `main` to trigger the CI/CD pipeline.

---

## Project Context (read this first)

### Tech Stack
- **Backend:** Python Flask + Flask-Login + PyMongo
- **Frontend:** Bootstrap 5 (server-rendered Jinja2 templates)
- **Database:** MongoDB Atlas (via `MONGO_URI` env var)
- **Auth:** Session-based login (Flask-Login) with Werkzeug password hashing
- **CI/CD:** GitHub Actions → Trivy scan → Artifact Registry → Cloud Run

### Current App Structure

```
FinalProject-PSO-B-12/
├── .github/workflows/deploy.yml   # CI/CD pipeline
├── templates/
│   ├── index.html                  # Guestbook page (list entries, create form)
│   ├── login.html                  # Login form
│   └── register.html               # Registration form
├── app.py                          # Flask routes + auth logic
├── Dockerfile
├── requirements.txt
└── README.md
```

### Database Collections

**`entries`** — guestbook messages:
```json
{
  "_id": ObjectId,
  "name": "John Doe",
  "message": "Hello world!",
  "user_id": ObjectId
}
```

**`users`** — user accounts:
```json
{
  "_id": ObjectId,
  "first_name": "John",
  "last_name": "Doe",
  "nickname": "johnny",
  "password_hash": "pbkdf2:sha256:...",
  "role": "user"
}
```

**`counters`** — visit counter:
```json
{
  "_id": "global_visits",
  "count": 42
}
```

### User Roles & Access Rules

| Action | Guest | User | Admin |
|--------|-------|------|-------|
| View guestbook | ✅ | ✅ | ✅ |
| Create entry | ❌ | ✅ | ✅ |
| Edit own entry | ❌ | ✅ | ✅ |
| Edit others' entry | ❌ | ❌ | ✅ |
| Delete own entry | ❌ | ✅ | ✅ |
| Delete others' entry | ❌ | ❌ | ✅ |

### Key Imports Already Available

```python
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
```

Current User object has: `current_user.id`, `current_user.nickname`, `current_user.first_name`, `current_user.last_name`, `current_user.role`.

---

## Feature 1: Profile Settings

**Goal:** Allow logged-in users to edit their first name, last name, and password.

### Backend (`app.py`)

Add a new route:

```python
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
        # Verify current_password against the stored hash
        # If new_password: validate it (min 8, letter + non-letter), hash it, update
        # Update first_name/last_name in DB

        flash('Profile updated!', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html')
```

### Frontend

Create `templates/profile.html` — Bootstrap card with:
- "First Name" input (pre-filled from `current_user.first_name`)
- "Last Name" input (pre-filled from `current_user.last_name`)
- Separator: "Change Password" section
  - "Current Password" input
  - "New Password" input (with strength meter — copy from register.html)
  - "Confirm New Password" input
- Save button

### Changes

- `app.py`: Add `/profile` route
- `templates/profile.html`: New file
- `templates/index.html`: Add "Profile" link in nav bar (after nickname, before Logout)

---

## Feature 2: Admin Dashboard

**Goal:** Admin-only page showing user list, stats, and the ability to promote/demote users.

### Backend (`app.py`)

```python
@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    total_users = users_collection.count_documents({})
    total_entries = entries_collection.count_documents({})
    counter = counter_collection.find_one({"_id": "global_visits"})
    total_visits = counter["count"] if counter else 0

    users = list(users_collection.find())
    for user in users:
        user["_id"] = str(user["_id"])
        user["message_count"] = entries_collection.count_documents(
            {"user_id": ObjectId(user["_id"])}
        )

    return render_template('admin.html', users=users, total_users=total_users,
                           total_entries=total_entries, total_visits=total_visits)
```

```python
@app.route('/admin/toggle-role/<user_id>', methods=['POST'])
@login_required
def toggle_role(user_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    target = users_collection.find_one({"_id": ObjectId(user_id)})
    if not target:
        flash('User not found.', 'danger')
        return redirect(url_for('admin_dashboard'))
    new_role = "admin" if target["role"] == "user" else "user"
    users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": new_role}}
    )
    flash(f'{target["nickname"]} is now a {new_role}.', 'success')
    return redirect(url_for('admin_dashboard'))
```

### Frontend

Create `templates/admin.html` — Bootstrap page with:
- **Stats cards** row (3 cards): Total Users, Total Entries, Total Visits
- **Users table**: Nickname, First/Last Name, Role, Message Count, Actions
- Use Bootstrap's `table` class with striped rows

### Nav Bar Update

In `templates/index.html`, add inside the authenticated block:
```html
{% if current_user.role == 'admin' %}
    <a class="nav-link" href="{{ url_for('admin_dashboard') }}">Dashboard</a>
{% endif %}
```

### Changes

- `app.py`: Add `/admin` and `/admin/toggle-role/<user_id>` routes
- `templates/admin.html`: New file
- `templates/index.html`: Add "Dashboard" link in nav (admin-only)

---

## Feature 3: Reactions / Likes

**Goal:** Allow logged-in users to like/unlike guestbook entries. Each entry shows a like count and a toggle button.

### Backend (`app.py`)

```python
@app.route('/like/<entry_id>', methods=['POST'])
@login_required
def like(entry_id):
    entry = entries_collection.find_one({"_id": ObjectId(entry_id)})
    if not entry:
        flash('Entry not found.', 'danger')
        return redirect(url_for('index'))

    user_id_str = current_user.get_id()
    liked_by = entry.get("liked_by", [])

    if user_id_str in liked_by:
        entries_collection.update_one(
            {"_id": ObjectId(entry_id)},
            {"$pull": {"liked_by": user_id_str}, "$inc": {"likes": -1}}
        )
    else:
        entries_collection.update_one(
            {"_id": ObjectId(entry_id)},
            {"$push": {"liked_by": user_id_str}, "$inc": {"likes": 1}}
        )

    return redirect(url_for('index'))
```

Entry document now has two new fields:
- `"likes": 0`
- `"liked_by": []` (array of user ID strings)

### Frontend (`templates/index.html`)

After the message text and before the edit/delete buttons, add:

```html
{% if current_user.is_authenticated %}
<form action="/like/{{ entry._id }}" method="POST" class="d-inline">
    <button type="submit"
        class="btn btn-sm {{ 'btn-primary' if current_user.get_id() in entry.get('liked_by', []) else 'btn-outline-primary' }}">
        {{ '❤️' if current_user.get_id() in entry.get('liked_by', []) else '🤍' }}
        {{ entry.get('likes', 0) }}
    </button>
</form>
{% else %}
    <span class="text-muted small">🤍 {{ entry.get('likes', 0) }}</span>
{% endif %}
```

### Migration Note

Existing entries won't have `likes` or `liked_by` fields. `entry.get('likes', 0)` handles this gracefully — old entries simply show 0 likes.

### Changes

- `app.py`: Add `/like/<entry_id>` route
- `templates/index.html`: Add like button next to each entry

---

## Development Checklist (for all features)

Each feature should:

1. [ ] Create a feature branch: `git checkout -b feature/your-feature-name`
2. [ ] Implement backend changes in `app.py`
3. [ ] Create or update templates
4. [ ] Test locally:
   ```powershell
   $env:MONGO_URI = "mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/guestbook_db?retryWrites=true&w=majority"
   $env:ADMIN_USERNAME = "admin"
   $env:ADMIN_PASSWORD = "admin123"
   python app.py
   ```
5. [ ] Verify no syntax errors
6. [ ] Commit and push, then open PR to `main`
7. [ ] Watch the GitHub Actions pipeline run (build → Trivy scan → deploy)
8. [ ] Verify the deployed app on Cloud Run
