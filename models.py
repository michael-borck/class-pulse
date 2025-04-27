from datetime import datetime
from extensions import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    
    sessions = db.relationship('Session', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    code = db.Column(db.String(10), unique=True, nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    active_question_id = db.Column(db.Integer, default=None, nullable=True)
    
    questions = db.relationship('Question', backref='session', lazy=True)
    
    def __repr__(self):
        return f'<Session {self.title}>'

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # multiple_choice, word_cloud, rating_scale
    options = db.Column(db.Text)  # JSON string for multiple_choice options or rating_scale min/max
    created_at = db.Column(db.DateTime, default=datetime.now)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'), nullable=False)
    
    responses = db.relationship('Response', backref='question', lazy=True)
    
    def __repr__(self):
        return f'<Question {self.text[:20]}...>'

class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    participant_id = db.Column(db.String(36), nullable=False)  # UUID to identify anonymous participants
    value = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    
    def __repr__(self):
        return f'<Response {self.id}>'

