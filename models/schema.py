from dataclasses import dataclass
from fasthtml.common import database
from typing import Optional, List
import random
import string

# Create database connection
db = database('classpulse.db')

# Define tables
users = db.t.users
sessions = db.t.sessions
questions = db.t.questions
responses = db.t.responses

# Create tables with schema if they don't exist
if users not in db.t:
    users.create(
        id=int,
        username=str,
        password_hash=str,
        email=str,
        display_name=str,
        pk='id'
    )

if sessions not in db.t:
    sessions.create(
        id=int,
        code=str,
        name=str,
        created_at=str,
        user_id=int,
        active=bool,
        pk='id'
    )

if questions not in db.t:
    questions.create(
        id=int,
        session_id=int,
        type=str,  # 'multiple_choice', 'word_cloud', 'rating'
        title=str,
        options=str,  # JSON string for multiple choice options
        active=bool,
        created_at=str,
        order=int,
        pk='id'
    )

if responses not in db.t:
    responses.create(
        id=int,
        question_id=int,
        session_id=int,
        response_value=str,
        respondent_id=str,  # Anonymous ID for audience member
        created_at=str,
        pk='id'
    )

# Generate dataclasses
User = users.dataclass()
Session = sessions.dataclass()
Question = questions.dataclass()
Response = responses.dataclass()

def generate_session_code(length=6):
    """Generate a random alphanumeric code for session joining"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))
