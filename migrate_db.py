import os
from flask import Flask
import sqlite3
from app import app as flask_app

def migrate_database():
    """
    Add active_question_id column to Session table
    """
    # Get the database path from the Flask app config
    db_path = flask_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    
    print(f"Database path: {db_path}")
    
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if the column already exists
    cursor.execute("PRAGMA table_info(session)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    
    if 'active_question_id' not in column_names:
        print("Adding active_question_id column to session table...")
        # Add the new column
        cursor.execute("ALTER TABLE session ADD COLUMN active_question_id INTEGER")
        conn.commit()
        print("Column added successfully.")
    else:
        print("Column active_question_id already exists.")
    
    # Close the connection
    conn.close()

if __name__ == "__main__":
    migrate_database()
    print("Migration completed successfully.")