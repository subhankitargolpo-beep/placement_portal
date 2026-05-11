from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

# Initialize the SQLAlchemy object
db = SQLAlchemy()

# 1. Base User Table (Handles Authentication for all 3 roles)
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False) # Roles: 'admin', 'company', 'student'
    
    # Links to detailed profiles
    company_profile = db.relationship('CompanyProfile', backref='user', uselist=False, cascade="all, delete-orphan")
    student_profile = db.relationship('StudentProfile', backref='user', uselist=False, cascade="all, delete-orphan")

# 2. Company Profile Table
class CompanyProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Links back to User table
    company_name = db.Column(db.String(150), nullable=False)
    hr_contact = db.Column(db.String(100), nullable=False)
    website = db.Column(db.String(150))
    is_approved = db.Column(db.Boolean, default=False) # Admin needs to approve before they can post drives
    is_blacklisted = db.Column(db.Boolean, default=False) # From the wireframe logic
    
    # One company can have many placement drives
    drives = db.relationship('PlacementDrive', backref='company', lazy=True, cascade="all, delete-orphan")

# 3. Student Profile Table
class StudentProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Links back to User table
    full_name = db.Column(db.String(150), nullable=False)
    department = db.Column(db.String(100)) # Taken from your wireframe
    skills = db.Column(db.String(200))
    resume_file = db.Column(db.String(200)) # We will store the filename here when they upload it
    is_blacklisted = db.Column(db.Boolean, default=False)
    
    # One student can have many applications
    applications = db.relationship('Application', backref='student', lazy=True, cascade="all, delete-orphan")

# 4. Placement Drive Table
class PlacementDrive(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company_profile.id'), nullable=False)
    job_title = db.Column(db.String(150), nullable=False)
    job_description = db.Column(db.Text, nullable=False)
    eligibility_criteria = db.Column(db.Text, nullable=False)
    application_deadline = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='Pending') # Statuses: Pending, Approved, Closed
    
    # One drive can receive many applications
    applications = db.relationship('Application', backref='drive', lazy=True, cascade="all, delete-orphan")

# 5. Application Table
class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'), nullable=False)
    drive_id = db.Column(db.Integer, db.ForeignKey('placement_drive.id'), nullable=False)
    application_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Applied') # Statuses: Applied, Shortlisted, Selected, Rejected