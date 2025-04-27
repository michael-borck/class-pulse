#!/usr/bin/env python
"""
ClassPulse starter script - runs the database migration and starts the server
"""

import os
import sys
import subprocess

def print_header():
    print("\n====================================")
    print("     ClassPulse Starter Script      ")
    print("====================================\n")

def run_migration():
    print("Running database migration...")
    from migrate_db import migrate_database
    migrate_database()
    print("Migration completed.\n")

def start_server(args):
    print("Starting ClassPulse server...\n")
    
    # Build the Flask command with any passed arguments
    cmd = [sys.executable, "-m", "flask", "run"]
    
    # Add any arguments from command line
    if args:
        cmd.extend(args)
    
    # Run the Flask app
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == "__main__":
    print_header()
    
    # Ensure we're in a virtual environment
    if not os.environ.get('VIRTUAL_ENV'):
        print("Warning: It appears you're not running in a virtual environment.")
        print("It's recommended to run ClassPulse inside a virtual environment.")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Exiting. Please activate your virtual environment and try again.")
            sys.exit(1)
    
    # Check for dependencies
    try:
        import flask
        import flask_socketio
        import flask_sqlalchemy
    except ImportError:
        print("Error: Missing dependencies.")
        print("Please run: pip install -r requirements.txt")
        sys.exit(1)
    
    # Run migration
    run_migration()
    
    # Get any command line arguments to pass to Flask
    args = sys.argv[1:]
    
    # Start the server
    start_server(args)