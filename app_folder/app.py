from flask import Flask, render_template, request, redirect, url_for, flash , jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import os
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, CompanyProfile, StudentProfile, PlacementDrive, Application
from datetime import datetime
# Initialize the Flask application
app = Flask(__name__)

# --- Configuration ---
app.config['SECRET_KEY'] = 'my_super_secret_placement_key_123' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///placement_portal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'resumes')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Link the database to our Flask app
db.init_app(app)

# --- Authentication Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 

# This tells Flask-Login how to load a user from the database via their ID
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Programmatic Database & Admin Creation ---
with app.app_context():
    db.create_all()
    
    # Requirement: "Admin must pre-exist in the database (no admin registration)"
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        # Create a default admin account if one doesn't exist
        hashed_password = generate_password_hash('admin123')
        new_admin = User(username='admin', password=hashed_password, role='admin')
        db.session.add(new_admin)
        db.session.commit()
        print("Default admin created -> Username: admin | Password: admin123")


# --- Routes ---

@app.route('/')
def home():
    # If a user is already logged in, send them directly to their dashboard
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'company':
            return redirect(url_for('company_dashboard'))
        elif current_user.role == 'student':
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        display_name = request.form.get('display_name')

        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('register'))

        # Hash the password for security
        hashed_password = generate_password_hash(password)
        
        # Create the Base User
        new_user = User(username=username, password=hashed_password, role=role)
        db.session.add(new_user)
        db.session.flush() # This gets us the new_user.id before committing

        # Create the specific profile based on role
        if role == 'student':
            profile = StudentProfile(user_id=new_user.id, full_name=display_name)
            db.session.add(profile)
        elif role == 'company':
            # Note: is_approved defaults to False in our models.py
            profile = CompanyProfile(user_id=new_user.id, company_name=display_name, hr_contact="TBD")
            db.session.add(profile)

        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()

        # Check if user exists and password matches the hash
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            
            # Role-based redirection
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'company':
                return redirect(url_for('company_dashboard'))
            elif user.role == 'student':
                return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# --- Admin Dashboard & Management Routes ---

@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return "Access Denied: Admins Only", 403

    total_students = StudentProfile.query.count()
    total_companies = CompanyProfile.query.count()
    total_drives = PlacementDrive.query.count()
    total_applications = Application.query.count()

    # --- Search Logic ---
    search_company = request.args.get('search_company', '')
    search_student = request.args.get('search_student', '')

    if search_company:
        companies = CompanyProfile.query.filter(CompanyProfile.company_name.ilike(f'%{search_company}%')).all()
    else:
        companies = CompanyProfile.query.all()

    if search_student:
        if search_student.isdigit():
            students = StudentProfile.query.filter_by(id=int(search_student)).all()
        else:
            students = StudentProfile.query.filter(StudentProfile.full_name.ilike(f'%{search_student}%')).all()
    else:
        students = StudentProfile.query.all()

    drives = PlacementDrive.query.all()

    # --- Chart.js Data Preparation ---
    # We fetch all applications and count them by their current status
    all_apps = Application.query.all()
    chart_data = {
        'Applied': len([a for a in all_apps if a.status == 'Applied']),
        'Shortlisted': len([a for a in all_apps if a.status == 'Shortlisted']),
        'Selected': len([a for a in all_apps if a.status == 'Selected']),
        'Rejected': len([a for a in all_apps if a.status == 'Rejected'])
    }

    return render_template('admin_dashboard.html', 
                           total_students=total_students,
                           total_companies=total_companies,
                           total_drives=total_drives,
                           total_applications=total_applications,
                           companies=companies, 
                           students=students, 
                           drives=drives,
                           chart_data=chart_data) 


@app.route('/admin/company/approve/<int:company_id>')
@login_required
def approve_company(company_id):
    if current_user.role != 'admin': return "Access Denied", 403
    
    company = CompanyProfile.query.get_or_404(company_id)
    company.is_approved = not company.is_approved # Toggles between True and False
    db.session.commit()
    
    status = "approved" if company.is_approved else "unapproved"
    flash(f'Company {company.company_name} has been {status}.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/company/blacklist/<int:company_id>')
@login_required
def blacklist_company(company_id):
    if current_user.role != 'admin': return "Access Denied", 403
    
    company = CompanyProfile.query.get_or_404(company_id)
    company.is_blacklisted = not company.is_blacklisted
    
    # Wireframe logic: If blacklisted, cancel their drives and revoke approval
    if company.is_blacklisted:
        company.is_approved = False
        for drive in company.drives:
            drive.status = 'Closed'
            
    db.session.commit()
    flash(f'Blacklist status updated for {company.company_name}.', 'warning')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/student/blacklist/<int:student_id>')
@login_required
def blacklist_student(student_id):
    if current_user.role != 'admin': return "Access Denied", 403
    
    student = StudentProfile.query.get_or_404(student_id)
    student.is_blacklisted = not student.is_blacklisted
    db.session.commit()
    flash(f'Blacklist status updated for {student.full_name}.', 'warning')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/drive/toggle/<int:drive_id>')
@login_required
def toggle_drive_status(drive_id):
    if current_user.role != 'admin': return "Access Denied", 403
    
    drive = PlacementDrive.query.get_or_404(drive_id)
    # Cycle through statuses
    if drive.status == 'Pending':
        drive.status = 'Approved'
    elif drive.status == 'Approved':
        drive.status = 'Closed'
    else:
        drive.status = 'Pending'
        
    db.session.commit()
    flash(f'Drive status updated to {drive.status}.', 'success')
    return redirect(url_for('admin_dashboard'))


# --- Company Dashboard & Job Management Routes ---

@app.route('/company_dashboard')
@login_required
def company_dashboard():
    if current_user.role != 'company':
        return "Access Denied: Companies Only", 403
    
    company = current_user.company_profile
    
    # Split drives into Active (Pending/Approved) and Closed for the UI
    active_drives = PlacementDrive.query.filter_by(company_id=company.id).filter(PlacementDrive.status != 'Closed').all()
    closed_drives = PlacementDrive.query.filter_by(company_id=company.id, status='Closed').all()
    
    return render_template('company_dashboard.html', 
                           company=company, 
                           active_drives=active_drives, 
                           closed_drives=closed_drives)

@app.route('/company/drive/create', methods=['GET', 'POST'])
@login_required
def create_drive():
    if current_user.role != 'company': return "Access Denied", 403
    company = current_user.company_profile
    
    # Milestone Requirement: Check if company is approved before allowing drive creation
    if not company.is_approved:
        flash("You must be approved by the Admin before you can post a placement drive.", "warning")
        return redirect(url_for('company_dashboard'))
        
    if request.method == 'POST':
        job_title = request.form.get('job_title')
        job_description = request.form.get('job_description')
        eligibility_criteria = request.form.get('eligibility_criteria')
        deadline_str = request.form.get('application_deadline')
        
        # Convert HTML datetime-local string to Python datetime object
        deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M') if deadline_str else datetime.utcnow()
        
        new_drive = PlacementDrive(
            company_id=company.id,
            job_title=job_title,
            job_description=job_description,
            eligibility_criteria=eligibility_criteria,
            application_deadline=deadline,
            status='Pending' # Drives need Admin approval per wireframe logic
        )
        db.session.add(new_drive)
        db.session.commit()
        flash('Drive created successfully! Awaiting Admin approval.', 'success')
        return redirect(url_for('company_dashboard'))
        
    return render_template('create_drive.html')

@app.route('/company/drive/close/<int:drive_id>')
@login_required
def close_drive(drive_id):
    if current_user.role != 'company': return "Access Denied", 403
    
    drive = PlacementDrive.query.get_or_404(drive_id)
    # Ensure a company can only close its own drives
    if drive.company_id == current_user.company_profile.id:
        drive.status = 'Closed'
        db.session.commit()
        flash('Drive marked as closed.', 'success')
        
    return redirect(url_for('company_dashboard'))

@app.route('/company/drive/<int:drive_id>/applications')
@login_required
def company_applications(drive_id):
    if current_user.role != 'company': return "Access Denied", 403
    
    drive = PlacementDrive.query.get_or_404(drive_id)
    if drive.company_id != current_user.company_profile.id:
        return "Access Denied", 403
        
    applications = Application.query.filter_by(drive_id=drive.id).all()
    return render_template('company_applications.html', drive=drive, applications=applications)

@app.route('/company/application/update/<int:app_id>', methods=['POST'])
@login_required
def update_application(app_id):
    if current_user.role != 'company': return "Access Denied", 403
    
    application = Application.query.get_or_404(app_id)
    if application.drive.company_id != current_user.company_profile.id:
        return "Access Denied", 403
        
    new_status = request.form.get('status')
    application.status = new_status
    db.session.commit()
    
    flash(f"Application for {application.student.full_name} updated to {new_status}.", "success")
    return redirect(url_for('company_applications', drive_id=application.drive_id))


# --- Student Dashboard & Job Application Routes ---

@app.route('/student_dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        return "Access Denied: Students Only", 403
    
    student = current_user.student_profile
    
    applied_apps = Application.query.filter_by(student_id=student.id).all()
    applied_drive_ids = [app.drive_id for app in applied_apps]
    
    # --- Search Logic ---
    search_job = request.args.get('search_job', '')
    
    # Start with a base query for approved drives
    query = PlacementDrive.query.filter(PlacementDrive.status == 'Approved')
    
    # Exclude drives the student already applied to
    if applied_drive_ids:
        query = query.filter(~PlacementDrive.id.in_(applied_drive_ids))
        
    # Apply search filter across job title or company name
    if search_job:
        # We join the CompanyProfile table so we can search by company name too!
        query = query.join(CompanyProfile).filter(
            (PlacementDrive.job_title.ilike(f'%{search_job}%')) |
            (CompanyProfile.company_name.ilike(f'%{search_job}%'))
        )
        
    available_drives = query.all()

    return render_template('student_dashboard.html', 
                           student=student, 
                           available_drives=available_drives, 
                           applied_apps=applied_apps)



@app.route('/student/profile/update', methods=['POST'])
@login_required
def update_profile():
    if current_user.role != 'student': return "Access Denied", 403
    
    student = current_user.student_profile
    student.department = request.form.get('department')
    student.skills = request.form.get('skills')
    
    # Handle Resume Upload
    file = request.files.get('resume')
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        # Create a unique filename to prevent overwriting
        unique_filename = f"student_{student.id}_{filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        student.resume_file = unique_filename
        
    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('student_dashboard'))

@app.route('/drive/details/<int:drive_id>')
@login_required
def drive_details(drive_id):
    drive = PlacementDrive.query.get_or_404(drive_id)
    return render_template('drive_details.html', drive=drive)

@app.route('/student/apply/<int:drive_id>', methods=['POST'])
@login_required
def apply_drive(drive_id):
    if current_user.role != 'student': return "Access Denied", 403
    
    student = current_user.student_profile
    
    # Prevent duplicate applications
    existing_app = Application.query.filter_by(student_id=student.id, drive_id=drive_id).first()
    if existing_app:
        flash('You have already applied for this drive.', 'warning')
    else:
        new_application = Application(student_id=student.id, drive_id=drive_id)
        db.session.add(new_application)
        db.session.commit()
        flash(f'Successfully applied to {new_application.drive.job_title}!', 'success')
        
    return redirect(url_for('student_dashboard'))

# --- API Endpoints ---

# 1. API to get all Approved Placement Drives (All Logged-in Users)
@app.route('/api/drives', methods=['GET'])
@login_required
def api_get_drives():
    approved_drives = PlacementDrive.query.filter_by(status='Approved').all()
    drives_data = []
    for drive in approved_drives:
        drives_data.append({
            'drive_id': drive.id,
            'company_name': drive.company.company_name,
            'job_title': drive.job_title,
            'description': drive.job_description,
            'deadline': drive.application_deadline.strftime('%Y-%m-%d %H:%M')
        })
    return jsonify({'status': 'success', 'total_drives': len(drives_data), 'data': drives_data})

# 2. API to get all Approved Companies (All Logged-in Users)
@app.route('/api/companies', methods=['GET'])
@login_required
def api_get_companies():
    companies = CompanyProfile.query.filter_by(is_approved=True).all()
    company_data = []
    for comp in companies:
        company_data.append({
            'company_id': comp.id,
            'company_name': comp.company_name,
            'website': comp.website or "Not Provided",
            'total_drives_posted': len(comp.drives)
        })
    return jsonify({'status': 'success', 'total_companies': len(company_data), 'data': company_data})

# 3. API to get a Directory of Students (Admins & Companies ONLY)
@app.route('/api/students', methods=['GET'])
@login_required
def api_get_students():
    if current_user.role not in ['admin', 'company']:
        return jsonify({'status': 'error', 'message': 'Access Denied: Authorized personnel only.'}), 403

    students = StudentProfile.query.all()
    student_data = []
    for student in students:
        student_data.append({
            'name': student.full_name,
            'department': student.department or "Not specified",
            'skills': student.skills or "Not specified"
        })
    return jsonify({'status': 'success', 'total_students': len(student_data), 'data': student_data})

# 4. API to get Application Status (Admins & The Drive's Owning Company ONLY)
@app.route('/api/applications/<int:drive_id>', methods=['GET'])
@login_required
def api_get_applications(drive_id):
    drive = PlacementDrive.query.get_or_404(drive_id)
    
    # Security Check: Only Admin or the Company that owns this drive can view its applications
    if current_user.role == 'student' or (current_user.role == 'company' and drive.company_id != current_user.company_profile.id):
        return jsonify({'status': 'error', 'message': 'Access Denied: You do not have permission to view this.'}), 403

    applications = Application.query.filter_by(drive_id=drive_id).all()
    app_data = []
    for app in applications:
        app_data.append({
            'student_name': app.student.full_name,
            'applied_on': app.application_date.strftime('%Y-%m-%d'),
            'status': app.status
        })
        
    return jsonify({
        'status': 'success', 
        'drive_title': drive.job_title,
        'total_applications': len(app_data), 
        'data': app_data
    })


if __name__ == '__main__':
    app.run(debug=True)