from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)  # In production, use hashed passwords!

class DeploymentLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    triggered_by = db.Column(db.String(100), nullable=False)
    pipeline = db.Column(db.String(50), default="DEV")
    status = db.Column(db.String(50))
    build_id = db.Column(db.String(50))
    build_number = db.Column(db.String(50))
    pr_count = db.Column(db.Integer)
    details = db.Column(db.Text)
