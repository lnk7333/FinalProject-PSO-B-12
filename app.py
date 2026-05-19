import os
from flask import Flask, render_template, request, redirect, url_for
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)

# Fetch MongoDB URI from environment variables (DevSecOps Best Practice)
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/guestbook_db")
client = MongoClient(MONGO_URI)
db = client.get_default_database("guestbook_db")

# Collections
entries_collection = db.entries
counter_collection = db.counters

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
def create():
    # 3. CREATE: Add new entry
    name = request.form.get('name')
    message = request.form.get('message')
    if name and message:
        entries_collection.insert_one({"name": name, "message": message})
    return redirect(url_for('index'))

@app.route('/update/<id>', methods=['POST'])
def update(id):
    # 4. UPDATE: Modify an existing message
    new_message = request.form.get('message')
    if new_message:
        entries_collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"message": new_message}}
        )
    return redirect(url_for('index'))

@app.route('/delete/<id>', methods=['POST'])
def delete(id):
    # 5. DELETE: Remove an entry
    entries_collection.delete_one({"_id": ObjectId(id)})
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Cloud Run binds to the PORT environment variable automatically
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)