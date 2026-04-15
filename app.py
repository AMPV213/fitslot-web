import os
import pika
import json
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timezone, timedelta

# --- APP INITIALIZATION ---
app = Flask(__name__)
app.secret_key = 'super_secret_fitslot_key' 
app.config['UPLOAD_FOLDER'] = 'static/uploads'

MAX_CAPACITY = 3 

def get_db_connection():
    conn = sqlite3.connect('fitslot.db')
    conn.row_factory = sqlite3.Row  
    return conn

# --- RABBITMQ SETUP ---
def send_rabbitmq_notification(name, workout, time):
    # Fetch the RabbitMQ URL from Render's environment variables
    amqp_url = os.environ.get('CLOUDAMQP_URL', 'amqp://localhost')
    
    try:
        params = pika.URLParameters(amqp_url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        
        # Ensure the queue exists
        channel.queue_declare(queue='gym_bookings', durable=True)
        
        # The message payload
        message = {
            "event": "NEW_BOOKING",
            "user": name,
            "zone": workout,
            "time": time
        }
        
        # Send to the queue
        channel.basic_publish(
            exchange='',
            routing_key='gym_bookings',
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2) # Persistent message
        )
        connection.close()
        print(f"[RabbitMQ] Successfully queued booking for {name}")
    except Exception as e:
        print(f"[RabbitMQ Error] {e}")


# --- AUTHENTICATION ROUTES ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username'] 
            session['name'] = user['name']
            session['is_admin'] = user['is_admin'] # Track admin status
            
            # --- NEW: Get Philippine Time (UTC +8) ---
            pht_zone = timezone(timedelta(hours=8))
            pht_time = datetime.now(pht_zone).strftime('%Y-%m-%d %H:%M:%S')
            
            # Log the login timestamp explicitly with PHT
            conn.execute('INSERT INTO login_logs (user_id, login_time) VALUES (?, ?)', (user['id'], pht_time))
            conn.commit()
            
            conn.close()
            return redirect(url_for('dashboard'))
            
            conn.close()
            return redirect(url_for('dashboard'))
        else:
            conn.close()
            flash("Invalid credentials.", "danger")
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        password = request.form.get('password')
        photo = request.files.get('profile_photo')
        
        hashed_pw = generate_password_hash(password)
        filename = 'default.png'
        
        if photo and photo.filename != '':
            filename = secure_filename(photo.filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (name, username, password, profile_pic) VALUES (?, ?, ?, ?)', 
                         (name, username, hashed_pw, filename))
            conn.commit()
            flash("Account created! Please log in.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username already exists. Please choose another.", "danger")
        finally:
            conn.close()
            
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# --- ADMIN ROUTE ---
@app.route('/admin')
def admin_panel():
    # Security Check: Kick out non-admins
    if 'user_id' not in session or not session.get('is_admin'):
        flash("Access Denied: Admins only.", "danger")
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    
    # Fetch recent logins by joining logs with the users table
    logs = conn.execute('''
        SELECT users.name, users.username, login_logs.login_time 
        FROM login_logs 
        JOIN users ON login_logs.user_id = users.id 
        ORDER BY login_logs.login_time DESC 
        LIMIT 50
    ''').fetchall()
    
    # Get total user count
    total_users = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
    
    conn.close()
    
    return render_template('admin.html', logs=logs, total_users=total_users)


# --- DASHBOARD & SETTINGS ROUTES ---
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    
    roster_data = conn.execute('''
        SELECT members.*, users.is_private, users.profile_pic 
        FROM members 
        JOIN users ON members.user_id = users.id 
        ORDER BY members.time ASC
    ''').fetchall()
    
    capacity_counts = {}
    for row in roster_data:
        key = f"{row['time']}_{row['workout']}"
        capacity_counts[key] = capacity_counts.get(key, 0) + 1
        
    conn.close()
    
    return render_template('dashboard.html', data=roster_data, user=user, counts=capacity_counts, max_cap=MAX_CAPACITY)

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session: return redirect(url_for('login'))
        
    is_private = 1 if request.form.get('privacy_toggle') else 0
    photo = request.files.get('profile_photo')
    
    conn = get_db_connection()
    conn.execute('UPDATE users SET is_private = ? WHERE id = ?', (is_private, session['user_id']))
    
    if photo and photo.filename != '':
        filename = secure_filename(photo.filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        conn.execute('UPDATE users SET profile_pic = ? WHERE id = ?', (filename, session['user_id']))

    conn.commit()
    conn.close()
    flash("Profile updated successfully.", "success")
    return redirect(url_for('dashboard'))


# --- BOOKING & MANAGEMENT ROUTES ---
@app.route('/book', methods=['POST'])
def book_slot():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    name = request.form.get('n')
    workout = request.form.get('w')
    time = request.form.get('t')
    
    conn = get_db_connection()
    
    conflict = conn.execute('SELECT * FROM members WHERE user_id = ? AND time = ?', (session['user_id'], time)).fetchone()
    if conflict:
        flash(f"Scheduling Conflict: You already have a session booked at {time}.", "danger")
        conn.close()
        return redirect(url_for('dashboard'))

    current_bookings = conn.execute('SELECT COUNT(*) as count FROM members WHERE workout = ? AND time = ?', (workout, time)).fetchone()['count']
    if current_bookings >= MAX_CAPACITY:
        flash(f"Capacity Reached: {workout} is completely full at {time}. Please choose another time.", "warning")
        conn.close()
        return redirect(url_for('dashboard'))

    conn.execute('INSERT INTO members (user_id, name, workout, time, status) VALUES (?, ?, ?, ?, ?)',
                 (session['user_id'], name, workout, time, 'Active'))
    conn.commit()
    conn.close()
    
    # --- TRIGGER RABBITMQ HERE ---
    send_rabbitmq_notification(name, workout, time)
    
    flash(f"Successfully booked {workout} at {time}!", "success")
    return redirect(url_for('dashboard'))

@app.route('/edit/<int:slot_id>', methods=['POST'])
def edit_slot(slot_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    new_zone = request.form.get('w')
    new_time = request.form.get('t')
    # --- NEW: Get the new status from the form ---
    new_status = request.form.get('status')
    
    conn = get_db_connection()
    
    # If Admin, they can update Zone, Time, AND Status for ANY slot.
    if session.get('is_admin'):
        conn.execute('''
            UPDATE members 
            SET workout = ?, time = ?, status = ?
            WHERE id = ?
        ''', (new_zone, new_time, new_status, slot_id))
    else:
        # Normal user can only update Zone and Time, and ONLY for their own slot.
        conn.execute('''
            UPDATE members 
            SET workout = ?, time = ?
            WHERE id = ? AND user_id = ?
        ''', (new_zone, new_time, slot_id, session['user_id']))
        
    conn.commit()
    conn.close()
    
    flash("Booking updated successfully!", "success")
    return redirect(url_for('dashboard'))

@app.route('/cancel/<int:id>', methods=['POST'])
def cancel_slot(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    conn.execute('DELETE FROM members WHERE id = ? AND user_id = ?', (id, session['user_id']))
    conn.commit()
    conn.close()
    
    flash("Booking cancelled.", "success")
    return redirect(url_for('dashboard'))

@app.route('/home')
def home():
    # Placeholder data for testing the UI
    context = {
        'display_name': 'Porras',
        'current_level': 14,
        'current_streak': 30
    }
    return render_template('home.html', **context)

if __name__ == '__main__':
    app.run(debug=True, port=5000)