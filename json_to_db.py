import json
import sqlite3
import os

def import_json_to_db(json_filename, db_filename):
    if not os.path.exists(json_filename):
        print(f"Error: {json_filename} not found! Run xml_to_json.py first.")
        return

    if not os.path.exists(db_filename):
        print(f"Error: {db_filename} not found! Make sure your main app has created the database.")
        return

    print(f"Reading {json_filename}...")
    with open(json_filename, 'r') as file:
        bookings = json.load(file)

    print(f"Connecting to {db_filename}...")
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()

    inserted_count = 0

    for booking in bookings:
        try:
            # Insert into the members table. We default the status to 'Active'
            cursor.execute('''
                INSERT INTO members (user_id, name, workout, time, status) 
                VALUES (?, ?, ?, ?, ?)
            ''', (booking['user_id'], booking['name'], booking['workout'], booking['time'], 'Active'))
            inserted_count += 1
        except Exception as e:
            print(f"Failed to insert {booking['name']}: {e}")

    conn.commit()
    conn.close()

    print(f"Successfully imported {inserted_count} bookings into the database!")

if __name__ == "__main__":
    import_json_to_db('bookings.json', 'fitslot.db')