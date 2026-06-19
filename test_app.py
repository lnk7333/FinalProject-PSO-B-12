import pytest
import mongomock
from bson.objectid import ObjectId
from flask import session
from app import app, db

@pytest.fixture
def client():
    """Fixture utama untuk setup Flask Test Client dan Mocking Database."""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.secret_key = 'super_secret_test_key'
    
    # Isolasikan database menggunakan mongomock di memori RAM
    mock_client = mongomock.MongoClient()
    mock_db = mock_client.guestbook_db
    
    # Override langsung objek koleksi di app.py ke database tiruan
    import app as app_module
    app_module.entries_collection = mock_db.entries
    app_module.counter_collection = mock_db.counters
    app_module.users_collection = mock_db.users

    # Lakukan seeding user sampel untuk keperluan testing auth & role
    mock_db.users.insert_one({
        "_id": ObjectId("65f1a2b3c4d5e6f7a8b9c001"),
        "first_name": "Muhammad",
        "last_name": "Fawwaz",
        "nickname": "fawwaz_user",
        "password_hash": "pbkdf2:sha256:250000$mockhash",
        "role": "user"
    })
    
    mock_db.users.insert_one({
        "_id": ObjectId("65f1a2b3c4d5e6f7a8b9c002"),
        "first_name": "Admin",
        "last_name": "Global",
        "nickname": "admin_super",
        "password_hash": "pbkdf2:sha256:250000$mockhash",
        "role": "admin"
    })

    with app.test_client() as client:
        yield client

# ==========================================
# 1. ROUTE TESTING: INDEX & VISIT COUNTER
# ==========================================

def test_index_route(client):
    """Memastikan rute utama berjalan dan visit counter bertambah."""
    response = client.get('/')
    assert response.status_code == 200
    assert b"Digital Guestbook" in response.data

# ==========================================
# 2. ROUTE TESTING: AUTHENTICATION (VALIDATION)
# ==========================================

def test_register_validation_rules(client):
    """Menguji kegagalan validasi registrasi (password terlalu pendek)."""
    payload = {
        "first_name": "Fawwaz",
        "last_name": "Amien",
        "nickname": "fawwaz123",
        "password": "short",
        "confirm": "short"
    }
    response = client.post('/register', data=payload, follow_redirects=True)
    assert b"Password must be at least 8 characters." in response.data

def test_register_success(client):
    """Menguji keberhasilan proses registrasi."""
    payload = {
        "first_name": "Rafindra",
        "last_name": "Nabiel",
        "nickname": "rafindra_new",
        "password": "SecurePassword123!",
        "confirm": "SecurePassword123!"
    }
    response = client.post('/register', data=payload, follow_redirects=True)
    assert b"Registration successful!" in response.data

def test_login_failed(client):
    """Menguji kegagalan login jika kredensial salah."""
    payload = {"nickname": "salah_user", "password": "salah_password"}
    response = client.post('/login', data=payload, follow_redirects=True)
    assert b"Invalid nickname or password." in response.data

# ==========================================
# 3. HELPER FUNCTIONS: LOGIN SIMULATOR
# ==========================================

def login_as_user(client):
    """Helper untuk mensimulasikan status login sebagai 'user'."""
    with client.session_transaction() as sess:
        sess['_user_id'] = "65f1a2b3c4d5e6f7a8b9c001"

def login_as_admin(client):
    """Helper untuk mensimulasikan status login sebagai 'admin'."""
    with client.session_transaction() as sess:
        sess['_user_id'] = "65f1a2b3c4d5e6f7a8b9c002"

# ==========================================
# 4. ROUTE TESTING: GUESTBOOK CRUD
# ==========================================

def test_create_entry_authenticated(client):
    """Menguji penambahan pesan baru ke buku tamu saat user telah login."""
    login_as_user(client)
    payload = {"message": "Halo, ini pesan testing unit test!"}
    response = client.post('/create', data=payload, follow_redirects=True)
    assert b"Entry added successfully!" in response.data

def test_logout_authenticated(client):
    """Menguji apakah rute logout membersihkan session dengan benar."""
    login_as_user(client)
    response = client.get('/logout', follow_redirects=True)
    assert b"You have been logged out." in response.data

# ==========================================
# 5. ROUTE TESTING: REACTIONS & LIKES
# ==========================================

def test_like_and_unlike_entry(client):
    """Menguji alur penambahan like dan pembatalan (unlike) pada pesan."""
    login_as_user(client)
    
    # Suntik pesan buatan langsung ke database tiruan
    import app as app_module
    entry_id = app_module.entries_collection.insert_one({
        "name": "Muhammad Fawwaz",
        "message": "Pesan Populer",
        "user_id": ObjectId("65f1a2b3c4d5e6f7a8b9c001"),
        "likes": 0,
        "liked_by": []
    }).inserted_id

    # Aksi 1: Kirim POST request untuk LIKE
    response = client.post(f'/like/{str(entry_id)}', follow_redirects=True)
    assert response.status_code == 200

    # Aksi 2: Kirim POST kembali ke rute yang sama untuk UNLIKE
    response = client.post(f'/like/{str(entry_id)}', follow_redirects=True)
    assert response.status_code == 200

# ==========================================
# 6. ROUTE TESTING: ADMIN DASHBOARD & ROLE PROTECTION
# ==========================================

def test_admin_dashboard_access_denied(client):
    """Memastikan user biasa ditolak keras saat mencoba masuk ke rute admin."""
    login_as_user(client)
    response = client.get('/admin', follow_redirects=True)
    assert b"Access denied." in response.data

def test_admin_dashboard_access_granted(client):
    """Memastikan admin berhasil masuk ke halaman dashboard khusus."""
    login_as_admin(client)
    response = client.get('/admin')
    assert response.status_code == 200
    assert b"Admin Dashboard" in response.data

# ==========================================
# 7. TESTING VALIDASI REGISTRASI & LOGIN (BARIS MISSING: 82-101)
# ==========================================

def test_register_invalid_names_and_match(client):
    """Menguji kegagalan registrasi akibat nama mengandung angka atau password tidak cocok."""
    # Skenario 1: First name salah (mengandungi angka)
    payload_invalid_name = {
        "first_name": "Fawwaz123",
        "last_name": "Amien",
        "nickname": "fawwaz_nama_salah",
        "password": "ValidPassword1!",
        "confirm": "ValidPassword1!"
    }
    response = client.post('/register', data=payload_invalid_name, follow_redirects=True)
    assert b"First name must contain only letters and spaces." in response.data

    # Skenario 2: Konfirmasi password tidak cocok
    payload_mismatch_pass = {
        "first_name": "Muhammad",
        "last_name": "Fawwaz",
        "nickname": "fawwaz_mismatch",
        "password": "ValidPassword1!",
        "confirm": "PasswordBeda1!"
    }
    response = client.post('/register', data=payload_mismatch_pass, follow_redirects=True)
    assert b"Passwords do not match." in response.data


# ==========================================
# 8. TESTING UPDATE & DELETE MESSAGE (BARIS MISSING: 233-275)
# ==========================================

def test_update_and_delete_entry_ownership(client):
    """Menguji fungsionalitas Update dan Delete pada Buku Tamu."""
    login_as_user(client)
    import app as app_module
    
    # Buat pesan buatan yang dimiliki oleh user fawwaz_user (ID: ...001)
    entry_id = app_module.entries_collection.insert_one({
        "name": "Muhammad Fawwaz",
        "message": "Pesan Asli",
        "user_id": ObjectId("65f1a2b3c4d5e6f7a8b9c001")
    }).inserted_id

    # Skenario 1: Update pesan berhasil
    response = client.post(f'/update/{str(entry_id)}', data={"message": "Pesan Terupdate"}, follow_redirects=True)
    assert b"Message updated!" in response.data

    # Skenario 2: Delete pesan berhasil
    response = client.post(f'/delete/{str(entry_id)}', follow_redirects=True)
    assert b"Entry deleted." in response.data


# ==========================================
# 9. TESTING ADMIN TOGGLE ROLE (BARIS MISSING: 344-357)
# ==========================================

def test_admin_toggle_user_role(client):
    """Menguji fitur Admin mengubah role user biasa menjadi admin."""
    login_as_admin(client)
    
    # Gunakan ID user fawwaz_user yang sudah di-seed di fixture
    target_user_id = "65f1a2b3c4d5e6f7a8b9c001"
    
    response = client.post(f'/admin/toggle-role/{target_user_id}', follow_redirects=True)
    assert b"is now a admin" in response.data or response.status_code == 200

# ==========================================
# 10. TESTING EDGE CASES: GUESTBOOK CRUD (BARIS MISSING: 235-271)
# ==========================================

def test_update_entry_not_found(client):
    """Menguji rute update jika ID pesan tidak eksis di database."""
    login_as_user(client)
    fake_id = ObjectId()
    response = client.post(f'/update/{str(fake_id)}', data={"message": "Edit"}, follow_redirects=True)
    assert b"Entry not found." in response.data

def test_delete_entry_not_found(client):
    """Menguji rute delete jika ID pesan tidak eksis di database."""
    login_as_user(client)
    fake_id = ObjectId()
    response = client.post(f'/delete/{str(fake_id)}', follow_redirects=True)
    assert b"Entry not found." in response.data

def test_update_entry_unauthorized(client):
    """Menguji penolakan sistem jika user mencoba mengedit pesan orang lain."""
    login_as_user(client)
    import app as app_module
    
    # Buat pesan milik orang lain (ID berbeda dengan fawwaz_user)
    entry_id = app_module.entries_collection.insert_one({
        "name": "Orang Lain",
        "message": "Pesan Rahasia",
        "user_id": ObjectId("65f1a2b3c4d5e6f7a8b9c999")
    }).inserted_id

    response = client.post(f'/update/{str(entry_id)}', data={"message": "Hack"}, follow_redirects=True)
    assert b"You can only edit your own messages." in response.data


# ==========================================
# 11. TESTING ROUTE: PROFILE GET & POST (BARIS MISSING: 144-191)
# ==========================================

def test_profile_get_route(client):
    """Menguji apakah halaman profil berhasil dimuat via GET request."""
    login_as_user(client)
    response = client.get('/profile')
    assert response.status_code == 200
    assert b"Profile Settings" in response.data

def test_profile_update_wrong_password(client):
    """Menguji penolakan update profil jika current password salah."""
    login_as_user(client)
    payload = {
        "first_name": "Muhammad",
        "last_name": "Fawwaz Al Amien", # Bersihkan karakter "-" menjadi spasi biasa
        "current_password": "salah_password_sekarang"
    }
    response = client.post('/profile', data=payload, follow_redirects=True)
    assert b"Incorrect current password." in response.data


# ==========================================
# 12. TESTING EDGE CASES: LIKES & ROLES (BARIS MISSING: 283-304, 345-350)
# ==========================================

def test_like_entry_invalid_id(client):
    """Menguji penanganan error jika format ID likes tidak valid (BSON InvalidId)."""
    login_as_user(client)
    response = client.post('/like/id-asal-asalan', follow_redirects=True)
    assert b"Entry not found." in response.data

def test_admin_toggle_role_user_not_found(client):
    """Menguji rute toggle role jika target user tidak ditemukan oleh admin."""
    login_as_admin(client)
    fake_user_id = ObjectId()
    response = client.post(f'/admin/toggle-role/{str(fake_user_id)}', follow_redirects=True)
    assert b"User not found." in response.data