import sqlite3
import random
from werkzeug.security import generate_password_hash

def setup_database():
    conn = sqlite3.connect('fitslot.db')
    cursor = conn.cursor()

    # --- UPDATED: Added is_admin column ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            profile_pic TEXT DEFAULT 'default.png',
            is_private INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0 
        )
    ''')

    # --- NEW: Login Tracker Table ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS login_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # --- Existing Members Table ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            workout TEXT NOT NULL,
            time TEXT,
            status TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Clear out old data for a fresh start
    cursor.execute('DELETE FROM users')
    cursor.execute('DELETE FROM members')
    cursor.execute('DELETE FROM login_logs')

    # 1. Create System User (Admin Account)
    sys_pw = generate_password_hash('FSPass')
    cursor.execute('INSERT INTO users (name, username, password, is_private, is_admin) VALUES (?, ?, ?, ?, ?)', 
                   ('System Admin', 'FSAdmin', sys_pw, 0, 1))
    system_user_id = cursor.lastrowid

    # 2. Create Test User (Normal User)
    test_pw = generate_password_hash('password123')
    cursor.execute('INSERT INTO users (name, username, password, is_private, is_admin) VALUES (?, ?, ?, ?, ?)', 
                   ('Test User', 'testuser', test_pw, 0, 0))

    # 3. Generate Legacy Members Dummy Data
    zones = [
        "Olympic Weightlifting", "Cardio & Core", "Basketball Court", 
        "Swimming Pool", "Yoga Studio", "Boxing Ring"
    ]
    
    legacy_names = [
        "Juan", "Harold Garzon", "Al Michael Villanueva",
        "Belle Cheska Medina", "Timothy Porras", "Zeun Allen Suelo"
    ]

    times = ["06:00", "07:30", "09:00", "11:30", "13:00", "15:30", "17:00", "18:30", "20:00"]

    legacy_members = []
    for name in legacy_names:
        random_zone = random.choice(zones)
        random_time = random.choice(times)
        # Tie the legacy members to the system user account
        legacy_members.append((system_user_id, name, random_zone, random_time, 'Legacy Member'))

    # Insert all legacy members into the DB
    cursor.executemany('INSERT INTO members (user_id, name, workout, time, status) VALUES (?, ?, ?, ?, ?)', legacy_members)
    
    conn.commit()
    conn.close()
    
    print("Success: Database completely rebuilt with Admin and Tracking features!")

if __name__ == '__main__':
    setup_database()