from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from dotenv import load_dotenv
from functools import wraps
from io import StringIO
import os
import re
import secrets
import random
import csv
import base64

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'pathport-ai-delivery-secret-key-2025-secure')

# Configure upload folder
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads', 'parcels')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# MongoDB connection and collection initialization
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
client = None
db = None
users_collection = None
parcels_collection = None
routes_collection = None
activity_collection = None
ratings_collection = None

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1500)
    db = client['pathport_delivery']
    
    # Test connection first
    client.admin.command('ping')
    
    # Initialize collections
    users_collection = db['users']
    parcels_collection = db['parcels']
    routes_collection = db['routes']
    activity_collection = db['activity']
    ratings_collection = db['ratings']

    # Initialize collections indexes
    try:
        users_collection.create_index('email', unique=True)
        parcels_collection.create_index('order_id', unique=True)
        parcels_collection.create_index('sender_id')
        parcels_collection.create_index('delivery_partner_id')
        parcels_collection.create_index('status')
        routes_collection.create_index('partner_id')
    except Exception:
        pass
    
    # Create indexes for better performance
    parcels_collection.create_index([('sender_id', 1)])
    parcels_collection.create_index([('delivery_partner_id', 1)])
    parcels_collection.create_index([('status', 1)])
    parcels_collection.create_index([('order_id', 1)], unique=True)
    parcels_collection.create_index([('created_at', -1)])
    print("[OK] MongoDB connected successfully to: " + str(MONGO_URI))
except Exception as e:
    print("[NOTICE] MongoDB connection note: Unable to reach MongoDB host. Please verify mongod service is running.")

# ================================
# TEMPLATE HELPERS & CONTEXT PROCESSORS
# ================================

@app.context_processor
def inject_global_utilities():
    """Inject CSRF token and timestamp helpers into all templates."""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    return {
        'csrf_token': lambda: session.get('csrf_token', ''),
        'current_year': datetime.now().year
    }

@app.template_filter('timeago')
def timeago(date):
    """Format a datetime into a friendly time-ago string."""
    if not date:
        return 'N/A'
    now = datetime.now()
    diff = now - date

    if diff.days > 365:
        return f"{diff.days // 365} year(s) ago"
    elif diff.days > 30:
        return f"{diff.days // 30} month(s) ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds >= 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds >= 60:
        minutes = diff.seconds // 60
        return f"{minutes} min{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"

# ================================
# AUTHENTICATION & ACCESS DECORATORS
# ================================

def verify_csrf():
    """Verify CSRF token on POST form submissions."""
    if app.config.get('TESTING'):
        return True
    token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
    expected = session.get('csrf_token')
    if not token or not expected or not secrets.compare_digest(token, expected):
        return False
    return True

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_role' not in session or session['user_role'] != role:
                flash('Access denied. Insufficient permissions for this section.', 'error')
                user_role = session.get('user_role')
                if user_role == 'delivery_partner':
                    return redirect(url_for('delivery_dashboard'))
                elif user_role == 'sender':
                    return redirect(url_for('sender_dashboard'))
                elif user_role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ================================
# CORE UTILITY & AI-MATCHING LOGIC
# ================================

def log_activity(title, description, activity_type, icon):
    """Log an activity event for the admin dashboard and feed."""
    if activity_collection is not None:
        try:
            activity_collection.insert_one({
                'title': title,
                'description': description,
                'type': activity_type,
                'icon': icon,
                'timestamp': datetime.now()
            })
        except Exception as err:
            print(f"Error logging activity: {err}")

def generate_order_id():
    """Generate a unique order ID: PP + YYYYMMDDHHMM + 4 random digits."""
    timestamp = datetime.now().strftime('%Y%m%d%H%M')
    random_digits = ''.join(random.choices('0123456789', k=4))
    return f'PP{timestamp}{random_digits}'

def calculate_recommended_reward(weight, size, urgency):
    """
    Intelligent dynamic pricing: computes recommended reward points
    based on package weight, volume size, and delivery urgency.
    """
    points = 10
    if weight > 1.0:
        points += int((weight - 1.0) * 2)
    if urgency == 'express':
        points += 15
    elif urgency == 'urgent':
        points += 8

    if size == 'large':
        points += 6
    elif size == 'medium':
        points += 3
    return max(5, points)

def calculate_route_match(parcel, partner_routes):
    """
    Smart Route Compatibility Algorithm:
    Evaluates commuter's registered travel paths against the parcel pickup
    and dropoff locations, taking vehicle capacity into account.
    Returns (compatibility_percentage, matched_route_name).
    """
    if not partner_routes:
        return 50, "General Commute"

    best_score = 45
    best_route_name = partner_routes[0].get('route_name', 'Commute Route')

    p_pickup = parcel.get('pickup_location', '').lower()
    p_drop = parcel.get('delivery_location', '').lower()
    p_weight = float(parcel.get('weight', 1.0))

    def extract_keywords(text):
        return set(re.findall(r'\b[a-z]{3,}\b', text))

    pickup_words = extract_keywords(p_pickup)
    drop_words = extract_keywords(p_drop)

    for route in partner_routes:
        r_from = extract_keywords(route.get('from_location', '').lower())
        r_to = extract_keywords(route.get('to_location', '').lower())
        r_cap = float(route.get('capacity', 5.0))

        score = 40
        # Check start point similarity
        if pickup_words & r_from:
            score += 25
        # Check destination similarity
        if drop_words & r_to:
            score += 25
        # Capacity compliance
        if p_weight <= r_cap:
            score += 10
        else:
            score -= 15

        # Check vehicle suitability (e.g. car/van accommodates large parcels)
        if parcel.get('size') == 'large' and route.get('transport_mode') in ['car', 'van', 'suv']:
            score += 5

        score = max(25, min(98, score))
        if score > best_score:
            best_score = score
            best_route_name = route.get('route_name', 'Commute Route')

    return best_score, best_route_name

def create_admin_user():
    """Ensure default admin user exists if collection is initialized."""
    if users_collection is None:
        return
    try:
        admin_exists = users_collection.find_one({'role': 'admin'})
        if not admin_exists:
            admin_user = {
                'name': 'PathPort Admin',
                'email': 'admin@pathport.com',
                'password': generate_password_hash('admin123'),
                'role': 'admin',
                'phone': '+91-9876543210',
                'rating': 5.0,
                'created_at': datetime.now(),
                'verified': True,
                'total_parcels': 0,
                'delivered_parcels': 0,
                'points_earned': 0
            }
            users_collection.insert_one(admin_user)
            print("[OK] Default Admin initialized: admin@pathport.com / admin123")
    except Exception as e:
        print(f"Admin init notice: {e}")

# ================================
# MAIN PUBLIC & AUTH ROUTES
# ================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session and 'user_role' in session:
        role = session.get('user_role')
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif role == 'delivery_partner':
            return redirect(url_for('delivery_dashboard'))
        else:
            return redirect(url_for('sender_dashboard'))

    if request.method == 'POST':
        if not verify_csrf():
            flash('Security session expired or invalid token. Please try again.', 'error')
            return render_template('login.html')
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please enter both email and password.', 'error')
            return render_template('login.html')

        user = users_collection.find_one({'email': email}) if users_collection is not None else None

        if user and check_password_hash(user['password'], password):
            if user.get('suspended', False):
                flash('Your account has been temporarily suspended. Please contact support.', 'error')
                return render_template('login.html')

            session['user_id'] = str(user['_id'])
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            session['points_earned'] = user.get('points_earned', 0)

            flash(f'Welcome back, {user["name"]}!', 'success')

            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'delivery_partner':
                return redirect(url_for('delivery_dashboard'))
            else:
                return redirect(url_for('sender_dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'error')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session and 'user_role' in session:
        role = session.get('user_role')
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif role == 'delivery_partner':
            return redirect(url_for('delivery_dashboard'))
        else:
            return redirect(url_for('sender_dashboard'))

    if request.method == 'POST':
        if not verify_csrf():
            flash('Security session expired or invalid token. Please try again.', 'error')
            return render_template('register.html')
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirmPassword', '')
        role = request.form.get('role', 'sender')
        phone = request.form.get('phone', '').strip()

        # Strict input validation
        if not name or not email or not password or not phone:
            flash('All fields are required.', 'error')
            return render_template('register.html')

        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            flash('Please enter a valid email address.', 'error')
            return render_template('register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')

        if users_collection is not None and users_collection.find_one({'email': email}):
            flash('This email is already registered. Please login.', 'error')
            return render_template('register.html')

        # Insert new user
        hashed_password = generate_password_hash(password)
        user_data = {
            'name': name,
            'email': email,
            'password': hashed_password,
            'role': role,
            'phone': phone,
            'rating': 5.0,
            'created_at': datetime.now(),
            'verified': True if role == 'sender' else False,
            'total_parcels': 0,
            'delivered_parcels': 0,
            'points_earned': 0,
            'email_notifications': True,
            'sms_notifications': False,
            'marketing_emails': False
        }

        if users_collection is not None:
            users_collection.insert_one(user_data)
            log_activity('New User Registration', f"{name} registered as a {role.replace('_', ' ')}.", 'user', 'fa-user-plus')

        flash('Registration successful! Please login to continue.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    user_name = session.get('user_name', 'User')
    session.clear()
    flash(f'Goodbye, {user_name}! You have been safely logged out.', 'info')
    return redirect(url_for('index'))

# ================================
# SENDER ROUTES
# ================================

@app.route('/sender/dashboard')
@login_required
@role_required('sender')
def sender_dashboard():
    user_id = session['user_id']
    my_parcels = []
    if parcels_collection is not None:
        my_parcels = list(parcels_collection.find({'sender_id': user_id}).sort('created_at', -1))
    return render_template('sender/dashboard.html', parcels=my_parcels)

@app.route('/sender/create-parcel', methods=['GET', 'POST'])
@login_required
@role_required('sender')
def create_parcel():
    if request.method == 'POST':
        if not verify_csrf():
            flash('Security session expired or invalid token. Please try again.', 'error')
            return render_template('sender/create_parcel.html')

        pickup_loc = request.form.get('pickup_location', '').strip()
        delivery_loc = request.form.get('delivery_location', '').strip()
        if not pickup_loc or not delivery_loc:
            flash('Both pickup and delivery locations are required.', 'error')
            return render_template('sender/create_parcel.html')

        if pickup_loc.lower() == delivery_loc.lower():
            flash('Pickup and delivery locations cannot be the same address.', 'error')
            return render_template('sender/create_parcel.html')
        order_id = generate_order_id()
        pickup_otp = ''.join(random.choices('0123456789', k=6))
        delivery_otp = ''.join(random.choices('0123456789', k=6))

        try:
            weight = float(request.form.get('weight', 1.0))
        except ValueError:
            weight = 1.0

        size = request.form.get('size', 'medium')
        urgency = request.form.get('urgency', 'normal')

        # Calculate or accept reward points
        recommended_pts = calculate_recommended_reward(weight, size, urgency)
        try:
            reward_points = int(request.form.get('reward_points', recommended_pts))
        except ValueError:
            reward_points = recommended_pts

        parcel_data = {
            'order_id': order_id,
            'sender_id': session['user_id'],
            'sender_name': session['user_name'],
            'title': request.form.get('title', 'Parcel'),
            'description': request.form.get('description', ''),
            'pickup_location': request.form.get('pickup_location', ''),
            'delivery_location': request.form.get('delivery_location', ''),
            'receiver_name': request.form.get('receiver_name', ''),
            'receiver_phone': request.form.get('receiver_phone', ''),
            'receiver_email': request.form.get('receiver_email', ''),
            'weight': weight,
            'size': size,
            'urgency': urgency,
            'pickup_otp': pickup_otp,
            'delivery_otp': delivery_otp,
            'reward_points': reward_points,
            'status': 'pending',
            'created_at': datetime.now(),
            'delivery_partner_id': None,
            'failed_otp_attempts': 0,
            'tracking_history': [{
                'status': 'pending',
                'timestamp': datetime.now(),
                'description': f"Parcel registered by {session['user_name']}"
            }]
        }

        # Secure file upload to static/uploads/parcels/
        if 'parcel_image' in request.files:
            file = request.files['parcel_image']
            if file and file.filename:
                safe_name = secure_filename(file.filename)
                unique_filename = f"{order_id}_{safe_name}"
                dest_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(dest_path)
                parcel_data['image_path'] = f"uploads/parcels/{unique_filename}"

        if parcels_collection is not None:
            parcels_collection.insert_one(parcel_data)
            log_activity('New Parcel Created', f"Parcel '{parcel_data['title']}' created by {session['user_name']}.", 'parcel', 'fa-box')
            users_collection.update_one({'_id': ObjectId(session['user_id'])}, {'$inc': {'total_parcels': 1}})

        flash(f'Parcel created successfully! Your Order ID is {order_id}. Share the pickup OTP with your delivery partner on collection.', 'success')
        return redirect(url_for('sender_dashboard'))

    return render_template('sender/create_parcel.html')

@app.route('/sender/track-parcel')
@login_required
@role_required('sender')
def track_parcel():
    user_id = session['user_id']
    parcels = []
    if parcels_collection is not None:
        parcels = list(parcels_collection.find({'sender_id': user_id}).sort('created_at', -1))
    return render_template('sender/track_parcel.html', parcels=parcels)

@app.route('/sender/profile', methods=['GET', 'POST'])
@login_required
@role_required('sender')
def sender_profile():
    user_id = session['user_id']
    if request.method == 'POST':
        update_data = {
            'name': request.form.get('name', ''),
            'phone': request.form.get('phone', ''),
            'address': request.form.get('address', ''),
            'email_notifications': 'email_notifications' in request.form,
            'sms_notifications': 'sms_notifications' in request.form,
            'marketing_emails': 'marketing_emails' in request.form
        }
        if users_collection is not None:
            users_collection.update_one({'_id': ObjectId(user_id)}, {'$set': update_data})
        session['user_name'] = update_data['name']
        flash('Profile settings updated successfully!', 'success')
        return redirect(url_for('sender_profile'))

    user = users_collection.find_one({'_id': ObjectId(user_id)}) if users_collection is not None else {}
    return render_template('sender/profile.html', user=user)

# ================================
# DELIVERY PARTNER ROUTES
# ================================

@app.route('/delivery/dashboard')
@login_required
@role_required('delivery_partner')
def delivery_dashboard():
    partner_id = session['user_id']
    assigned_parcels = []
    available_parcels = []

    if parcels_collection is not None:
        assigned_parcels = list(parcels_collection.find({'delivery_partner_id': partner_id}).sort('created_at', -1))
        available_parcels = list(parcels_collection.find({'status': 'pending'}).sort('created_at', -1).limit(10))

    partner_routes = []
    if routes_collection is not None:
        partner_routes = list(routes_collection.find({'partner_id': partner_id, 'active': True}))

    # Calculate match score for available parcels
    for p in available_parcels:
        score, route_name = calculate_route_match(p, partner_routes)
        p['match_score'] = score
        p['matched_route_name'] = route_name

    available_parcels.sort(key=lambda x: x.get('match_score', 0), reverse=True)

    return render_template('delivery/dashboard.html',
                           assigned_parcels=assigned_parcels,
                           available_parcels=available_parcels)

@app.route('/delivery/available-parcels')
@login_required
@role_required('delivery_partner')
def available_parcels():
    partner_id = session['user_id']
    parcels = []
    if parcels_collection is not None:
        parcels = list(parcels_collection.find({'status': 'pending'}).sort('created_at', -1))

    partner_routes = []
    if routes_collection is not None:
        partner_routes = list(routes_collection.find({'partner_id': partner_id, 'active': True}))

    for p in parcels:
        score, route_name = calculate_route_match(p, partner_routes)
        p['match_score'] = score
        p['matched_route_name'] = route_name

    # Priority sort: highest route match first
    parcels.sort(key=lambda x: x.get('match_score', 0), reverse=True)

    return render_template('delivery/available_parcels.html', parcels=parcels)

@app.route('/delivery/my-routes', methods=['GET', 'POST'])
@login_required
@role_required('delivery_partner')
def my_routes():
    partner_id = session['user_id']

    if request.method == 'POST':
        route_data = {
            'partner_id': partner_id,
            'route_name': request.form.get('route_name', 'Daily Commute'),
            'from_location': request.form.get('from_location', ''),
            'to_location': request.form.get('to_location', ''),
            'departure_time': request.form.get('departure_time', '09:00'),
            'capacity': int(request.form.get('capacity', 5)),
            'frequency': request.form.get('frequency', 'daily'),
            'transport_mode': request.form.get('transport', 'car'),
            'active': True,
            'created_at': datetime.now()
        }
        if routes_collection is not None:
            routes_collection.insert_one(route_data)
            log_activity('New Route Added', f"{session['user_name']} added route '{route_data['route_name']}'.", 'delivery', 'fa-route')
        flash('Route added successfully! Compatible delivery requests will now show top priority match scores.', 'success')
        return redirect(url_for('my_routes'))

    routes = []
    if routes_collection is not None:
        routes = list(routes_collection.find({'partner_id': partner_id}).sort('created_at', -1))
    return render_template('delivery/my_routes.html', routes=routes)

@app.route('/delivery/earnings')
@login_required
@role_required('delivery_partner')
def delivery_earnings():
    partner_id = session['user_id']
    completed_deliveries = []
    if parcels_collection is not None:
        completed_deliveries = list(parcels_collection.find({
            'delivery_partner_id': partner_id,
            'status': 'delivered'
        }).sort('delivered_at', -1))

    total_points = sum(p.get('reward_points', 10) for p in completed_deliveries)
    return render_template('delivery/earnings.html', deliveries=completed_deliveries, total_points=total_points)

@app.route('/delivery/verify-otp')
@login_required
@role_required('delivery_partner')
def verify_otp_page():
    partner_id = session['user_id']
    active_parcels = []
    if parcels_collection is not None:
        active_parcels = list(parcels_collection.find({
            'delivery_partner_id': partner_id,
            'status': {'$in': ['assigned', 'picked_up']}
        }).sort('created_at', -1))
    return render_template('delivery/verify_otp.html', active_parcels=active_parcels)

# ================================
# ORDER STATE & API ACTIONS
# ================================

@app.route('/api/accept-parcel/<parcel_id>', methods=['GET', 'POST'])
@login_required
@role_required('delivery_partner')
def accept_parcel(parcel_id):
    """Assign an available parcel to the current delivery partner."""
    try:
        partner_user = users_collection.find_one({'_id': ObjectId(session['user_id'])}) if users_collection is not None else None
        partner_phone = partner_user.get('phone', '') if partner_user else ''

        result = parcels_collection.update_one(
            {'_id': ObjectId(parcel_id), 'status': 'pending'},
            {'$set': {
                'delivery_partner_id': session['user_id'],
                'delivery_partner_name': session['user_name'],
                'delivery_partner_phone': partner_phone,
                'status': 'assigned',
                'assigned_at': datetime.now()
            }}
        )

        if result.modified_count > 0:
            parcel = parcels_collection.find_one({'_id': ObjectId(parcel_id)})
            if parcel:
                parcels_collection.update_one(
                    {'_id': ObjectId(parcel_id)},
                    {'$push': {
                        'tracking_history': {
                            'status': 'assigned',
                            'timestamp': datetime.now(),
                            'description': f"Accepted by delivery partner {session['user_name']}"
                        }
                    }}
                )
            log_activity('Parcel Accepted', f"Parcel accepted by {session['user_name']}.", 'delivery', 'fa-check')
            flash('Parcel accepted successfully! Coordinate with the sender for package pickup.', 'success')
        else:
            flash('Parcel is no longer available or was already accepted.', 'warning')
    except Exception as e:
        flash(f'Error accepting parcel: {str(e)}', 'error')

    return redirect(url_for('delivery_dashboard'))

@app.route('/api/update-parcel-status/<parcel_id>/<status>', methods=['GET', 'POST'])
@login_required
def update_parcel_status(parcel_id, status):
    """
    Update parcel lifecycle status with role & ownership checks.
    Only assigned partner or administrator can modify status.
    """
    try:
        parcel = parcels_collection.find_one({'_id': ObjectId(parcel_id)})
        if not parcel:
            return jsonify({'success': False, 'message': 'Parcel not found'}), 404

        # Ownership authorization check
        is_assigned_partner = (parcel.get('delivery_partner_id') == session['user_id'])
        is_admin = (session.get('user_role') == 'admin')

        if not (is_assigned_partner or is_admin):
            return jsonify({'success': False, 'message': 'Unauthorized: You are not assigned to this parcel'}), 403

        allowed_statuses = ['assigned', 'picked_up', 'in_transit', 'delivered', 'cancelled']
        if status not in allowed_statuses:
            return jsonify({'success': False, 'message': 'Invalid status'}), 400

        update_data = {'status': status}
        if status == 'picked_up':
            update_data['picked_up_at'] = datetime.now()
        elif status == 'delivered':
            update_data['delivered_at'] = datetime.now()
            # Credit reward points to delivery partner
            points = parcel.get('reward_points', 10)
            users_collection.update_one(
                {'_id': ObjectId(parcel['delivery_partner_id'])},
                {'$inc': {'points_earned': points, 'delivered_parcels': 1}}
            )

        parcels_collection.update_one({'_id': ObjectId(parcel_id)}, {'$set': update_data})
        parcels_collection.update_one(
            {'_id': ObjectId(parcel_id)},
            {'$push': {
                'tracking_history': {
                    'status': status,
                    'timestamp': datetime.now(),
                    'description': f"Status updated to {status.replace('_', ' ').title()}"
                }
            }}
        )

        return jsonify({'success': True, 'message': f'Status updated to {status}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/verify-pickup-otp', methods=['POST'])
@login_required
@role_required('delivery_partner')
def verify_pickup_otp():
    """Verify pickup OTP with brute-force prevention."""
    data = request.get_json() or {}
    order_id = data.get('orderId', '').strip()
    otp = data.get('otp', '').strip()

    parcel = parcels_collection.find_one({'order_id': order_id})
    if not parcel:
        return jsonify({'success': False, 'message': 'Invalid Order ID'}), 404

    # Security lockout check
    failed_attempts = parcel.get('failed_otp_attempts', 0)
    if failed_attempts >= 5:
        return jsonify({'success': False, 'message': 'Too many failed attempts. Parcel pickup is locked for security.'}), 429

    if parcel.get('pickup_otp') == otp:
        parcels_collection.update_one(
            {'order_id': order_id},
            {
                '$set': {
                    'status': 'picked_up',
                    'picked_up_at': datetime.now(),
                    'picked_up_by': session['user_id'],
                    'failed_otp_attempts': 0
                },
                '$push': {
                    'tracking_history': {
                        'status': 'picked_up',
                        'timestamp': datetime.now(),
                        'description': f"Pickup verified with OTP by partner {session['user_name']}"
                    }
                }
            }
        )
        log_activity('Parcel Picked Up', f"Parcel {order_id} picked up by {session['user_name']}.", 'parcel', 'fa-truck-loading')
        return jsonify({'success': True, 'message': 'Pickup verified successfully!'})

    # Record failed attempt
    parcels_collection.update_one({'order_id': order_id}, {'$inc': {'failed_otp_attempts': 1}})
    remaining = 4 - failed_attempts
    return jsonify({'success': False, 'message': f'Incorrect OTP. {remaining} attempt(s) remaining.'}), 400

@app.route('/api/verify-delivery-otp', methods=['POST'])
@login_required
@role_required('delivery_partner')
def verify_delivery_otp():
    """Verify delivery OTP with points crediting and security checks."""
    data = request.get_json() or {}
    order_id = data.get('orderId', '').strip()
    otp = data.get('otp', '').strip()

    parcel = parcels_collection.find_one({'order_id': order_id})
    if not parcel:
        return jsonify({'success': False, 'message': 'Invalid Order ID'}), 404

    failed_attempts = parcel.get('failed_otp_attempts', 0)
    if failed_attempts >= 5:
        return jsonify({'success': False, 'message': 'Too many failed attempts. Delivery verification locked.'}), 429

    if parcel.get('delivery_otp') == otp:
        reward = parcel.get('reward_points', 10)
        parcels_collection.update_one(
            {'order_id': order_id},
            {
                '$set': {
                    'status': 'delivered',
                    'delivered_at': datetime.now(),
                    'delivered_by': session['user_id'],
                    'failed_otp_attempts': 0
                },
                '$push': {
                    'tracking_history': {
                        'status': 'delivered',
                        'timestamp': datetime.now(),
                        'description': f"Parcel delivered to {parcel.get('receiver_name', 'recipient')} and verified"
                    }
                }
            }
        )

        # Credit partner points
        users_collection.update_one(
            {'_id': ObjectId(session['user_id'])},
            {'$inc': {'points_earned': reward, 'delivered_parcels': 1}}
        )
        session['points_earned'] = session.get('points_earned', 0) + reward
        log_activity('Delivery Completed', f"Order {order_id} delivered by {session['user_name']} (+{reward} pts).", 'delivery', 'fa-check-circle')

        return jsonify({'success': True, 'message': f'Delivery completed successfully! +{reward} points awarded.'})

    parcels_collection.update_one({'order_id': order_id}, {'$inc': {'failed_otp_attempts': 1}})
    remaining = 4 - failed_attempts
    return jsonify({'success': False, 'message': f'Incorrect OTP. {remaining} attempt(s) remaining.'}), 400

@app.route('/api/rate-delivery/<parcel_id>', methods=['POST'])
@login_required
def rate_delivery(parcel_id):
    """Allow sender to rate delivery partner and record reviews."""
    try:
        data = request.get_json() or {}
        rating = int(data.get('rating', 5))
        comment = data.get('comment', '').strip()

        if rating < 1 or rating > 5:
            return jsonify({'success': False, 'message': 'Rating must be between 1 and 5 stars.'}), 400

        parcel = parcels_collection.find_one({'_id': ObjectId(parcel_id)})
        if not parcel:
            return jsonify({'success': False, 'message': 'Parcel not found.'}), 404

        if parcel.get('sender_id') != session['user_id']:
            return jsonify({'success': False, 'message': 'Only the parcel sender can rate this delivery.'}), 403

        if parcel.get('status') != 'delivered':
            return jsonify({'success': False, 'message': 'You can only rate completed deliveries.'}), 400

        partner_id = parcel.get('delivery_partner_id')
        if not partner_id:
            return jsonify({'success': False, 'message': 'No delivery partner assigned to rate.'}), 400

        # Save to ratings collection
        rating_doc = {
            'parcel_id': parcel_id,
            'order_id': parcel.get('order_id'),
            'sender_id': session['user_id'],
            'sender_name': session.get('user_name', 'Sender'),
            'partner_id': partner_id,
            'rating': rating,
            'comment': comment,
            'created_at': datetime.now()
        }
        if ratings_collection is not None:
            ratings_collection.insert_one(rating_doc)

        # Update parcel state
        parcels_collection.update_one(
            {'_id': ObjectId(parcel_id)},
            {'$set': {'is_rated': True, 'rating': rating, 'review_comment': comment}}
        )

        # Recalculate partner aggregate score
        if ratings_collection is not None and users_collection is not None:
            all_ratings = list(ratings_collection.find({'partner_id': partner_id}))
            if all_ratings:
                avg_rating = sum(r.get('rating', 5) for r in all_ratings) / len(all_ratings)
                users_collection.update_one(
                    {'_id': ObjectId(partner_id)},
                    {'$set': {'rating': round(avg_rating, 1)}}
                )

        log_activity('Partner Rated', f"{session.get('user_name')} gave {rating} stars for order {parcel.get('order_id')}.", 'rating', 'fa-star')
        return jsonify({'success': True, 'message': 'Thank you! Your feedback has been recorded.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/delete-route/<route_id>', methods=['GET', 'POST'])
@login_required
@role_required('delivery_partner')
def delete_route(route_id):
    """Delete a commute route owned by the current partner."""
    try:
        result = routes_collection.delete_one({
            '_id': ObjectId(route_id),
            'partner_id': session['user_id']
        })
        if result.deleted_count > 0:
            flash('Route deleted successfully.', 'success')
        else:
            flash('Route not found or unauthorized.', 'error')
    except Exception as e:
        flash(f'Error deleting route: {str(e)}', 'error')
    return redirect(url_for('my_routes'))

@app.route('/api/toggle-route-status/<route_id>', methods=['GET', 'POST'])
@login_required
@role_required('delivery_partner')
def toggle_route_status(route_id):
    """Toggle a commute route between active and inactive."""
    try:
        route = routes_collection.find_one({
            '_id': ObjectId(route_id),
            'partner_id': session['user_id']
        })
        if route:
            new_status = not route.get('active', True)
            routes_collection.update_one({'_id': ObjectId(route_id)}, {'$set': {'active': new_status}})
            state_text = 'activated' if new_status else 'paused'
            flash(f'Route {state_text} successfully.', 'success')
        else:
            flash('Route not found.', 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('my_routes'))

# ================================
# TRACKING & GEOLOCATION
# ================================

@app.route('/track/<order_id>')
def track_parcel_status(order_id):
    """Public tracking page for an order."""
    parcel = parcels_collection.find_one({'order_id': order_id}) if parcels_collection is not None else None
    if not parcel:
        flash(f"Order #{order_id} could not be found. Please check your order ID.", 'error')
        return redirect(url_for('index'))
    return render_template('tracking.html', parcel=parcel)

@app.route('/api/parcel-location/<order_id>')
def get_parcel_location(order_id):
    """
    Return progressive geolocation coordinates based on Mumbai logistics landmarks
    and current order status.
    """
    parcel = parcels_collection.find_one({'order_id': order_id}) if parcels_collection is not None else None
    if not parcel:
        return jsonify({'error': 'Invalid Order ID'}), 404

    # Progressive coordinates based on status (Pickup: Malad/Andheri, Transit: Bandra, Delivered: Lower Parel/Colaba)
    status = parcel.get('status', 'pending')
    if status == 'delivered':
        coords = {'lat': 18.9986, 'lng': 72.8258, 'label': 'Delivered at Destination'}
    elif status in ['picked_up', 'in_transit']:
        coords = {'lat': 19.0596, 'lng': 72.8295, 'label': 'In Transit with Commuter'}
    else:
        coords = {'lat': 19.1136, 'lng': 72.8697, 'label': 'Awaiting Pickup'}

    return jsonify(parcel.get('current_location', coords))

@app.route('/api/track-parcel/<order_id>')
def track_parcel_api(order_id):
    """REST API endpoint for parcel tracking data."""
    parcel = parcels_collection.find_one({'order_id': order_id}) if parcels_collection is not None else None
    if not parcel:
        return jsonify({'success': False, 'message': 'Invalid order ID'}), 404

    parcel.pop('pickup_otp', None)
    parcel.pop('delivery_otp', None)
    parcel['_id'] = str(parcel['_id'])
    return jsonify({
        'success': True,
        'parcel': parcel,
        'tracking_history': parcel.get('tracking_history', [])
    })

# ================================
@app.route('/api/chat', methods=['POST'])
def chat_api():
    """AI Assistant (PathBot) API endpoint for answering logistics queries and tracking parcels."""
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({'success': False, 'reply': "Please enter a message or question.", 'suggestions': []})

    text_lower = message.lower()
    
    # 1. Check for order ID pattern
    order_id_match = re.search(r'\b(PP\d{8,14})\b', message, re.IGNORECASE)
    
    if order_id_match:
        oid = order_id_match.group(1).upper()
        parcel = parcels_collection.find_one({'order_id': oid}) if parcels_collection is not None else None
        if parcel:
            status = parcel.get('status', 'unknown')
            status_labels = {
                'pending': '⏳ Awaiting Partner Assignment',
                'assigned': '🛵 Assigned to Commuter Partner',
                'picked_up': '🚆 In Transit with Commuter',
                'delivered': '✅ Successfully Delivered'
            }
            status_text = status_labels.get(status, status.title())
            partner_name = parcel.get('delivery_partner_name') or 'Not yet assigned'
            route_str = f"{parcel.get('pickup_location', 'N/A')} ➔ {parcel.get('delivery_location', 'N/A')}"
            
            reply = (
                f"📦 **Order Status Found: {oid}**\n\n"
                f"• **Title:** {parcel.get('title', 'Parcel')}\n"
                f"• **Current Status:** {status_text}\n"
                f"• **Route:** {route_str}\n"
                f"• **Commuter Partner:** {partner_name}\n"
                f"• **Reward Points:** {parcel.get('reward_points', 0)} pts"
            )
            return jsonify({
                'success': True,
                'reply': reply,
                'order': {
                    'order_id': oid,
                    'status': status,
                    'title': parcel.get('title'),
                    'route': route_str,
                    'track_url': url_for('track_parcel_page', order_id=oid)
                },
                'suggestions': ['Track another order', 'How does delivery work?', 'CO2 impact']
            })
        else:
            return jsonify({
                'success': True,
                'reply': (
                    f"⚠️ Order **{oid}** was not found in our live database. \n\n"
                    f"Here are active sample seed orders you can test right now:\n"
                    f"• `PP202611151010` (Pending pickup in Bandra)\n"
                    f"• `PP202611152010` (Assigned to Arun Patel)\n"
                    f"• `PP202611153010` (In transit with Priya Singh)\n"
                    f"• `PP202611144010` (Delivered & 5★ rated)"
                ),
                'suggestions': ['Track PP202611153010', 'Track PP202611152010', 'Track PP202611144010']
            })

    # 2. Intent detection
    if any(k in text_lower for k in ['track', 'order', 'status', 'where is']):
        return jsonify({
            'success': True,
            'reply': (
                "🔍 **Track Your Parcel**\n\n"
                "Please enter your **Order ID** (e.g. `PP202611153010`).\n\n"
                "Or click one of these active test parcels to preview live tracking:"
            ),
            'suggestions': ['Track PP202611153010', 'Track PP202611152010', 'Track PP202611144010', 'Track PP202611151010']
        })

    if any(k in text_lower for k in ['earn', 'money', 'reward', 'points', 'payout', 'commuter', 'partner']):
        return jsonify({
            'success': True,
            'reply': (
                "💰 **How Commuters Earn with PathPort**\n\n"
                "1. **Register your daily commute:** Add your regular office/college route (e.g., Borivali to Dadar).\n"
                "2. **Get smart matches:** Our AI matches you with lightweight parcels along your exact path.\n"
                "3. **Earn on the go:** Earn **₹150 to ₹400** (or 15-40 PathPort Points) per delivery without taking any detours!\n"
                "4. **Instant Redeem:** Convert points to cash vouchers, fuel cards, or metro recharge."
            ),
            'suggestions': ['Become a Partner', 'Calculate CO2 Savings', 'Safety & OTPs']
        })

    if any(k in text_lower for k in ['carbon', 'co2', 'eco', 'green', 'environment', 'emission']):
        return jsonify({
            'success': True,
            'reply': (
                "🌿 **Sustainable Logistics & Carbon Savings**\n\n"
                "Traditional courier vans generate **~220g of CO₂ per km** making dedicated trips.\n\n"
                "Because PathPort utilizes **existing commuter trips** via Metro, Local Trains, and Carpools, every parcel delivered prevents an average of **1.2 kg to 3.5 kg of net CO₂ emissions**!\n\n"
                "Together our community has prevented over **28.4 metric tons of CO₂**."
            ),
            'suggestions': ['How does it work?', 'Track an order', 'How do commuters earn?']
        })

    if any(k in text_lower for k in ['otp', 'safe', 'security', 'verified', 'trust', 'loss']):
        return jsonify({
            'success': True,
            'reply': (
                "🛡️ **PathPort Trust & Safety**\n\n"
                "• **Dual OTP Verification:** 6-digit pickup OTP verified with sender; 6-digit delivery OTP required at handover.\n"
                "• **Identity Verified Partners:** Government ID & mobile verification required for all commuters.\n"
                "• **Real-Time GPS Tracking:** Live status checkpoints along the commute route.\n"
                "• **In-Transit Protection:** Value coverage on verified platform deliveries."
            ),
            'suggestions': ['Track an order', 'How does delivery work?']
        })

    if any(k in text_lower for k in ['how it works', 'how does', 'step', 'works', 'explain']):
        return jsonify({
            'success': True,
            'reply': (
                "🚀 **How PathPort Works in 3 Easy Steps**\n\n"
                "1. **Senders Post:** Enter parcel size, weight, pickup & drop location.\n"
                "2. **AI Matches:** Commuters traveling that corridor accept the delivery.\n"
                "3. **Secure Handover:** Commuter picks up using OTP, travels regular route, and drops off with recipient OTP!"
            ),
            'suggestions': ['Send a parcel', 'Become a commuter', 'Track an order']
        })

    if any(k in text_lower for k in ['hi', 'hello', 'hey', 'greetings', 'namaste']):
        return jsonify({
            'success': True,
            'reply': (
                "👋 **Hi there! I'm PathBot, your AI Logistics Assistant.**\n\n"
                "I can help you track parcels, calculate commuter earnings, or learn how crowdsourced green delivery works. What can I do for you today?"
            ),
            'suggestions': ['Track PP202611153010', 'How do commuters earn?', 'Carbon savings', 'Safety & OTPs']
        })

    # Default fallback
    return jsonify({
        'success': True,
        'reply': (
            "🤖 I'm PathBot! I can help you with:\n\n"
            "• **Live parcel tracking** (give me an Order ID like `PP202611153010`)\n"
            "• **Commuter earnings & reward points**\n"
            "• **Environmental CO₂ offset metrics**\n"
            "• **Safety & 2-factor OTP verification**\n\n"
            "What would you like to explore?"
        ),
        'suggestions': ['Track PP202611153010', 'How do commuters earn?', 'CO2 calculator', 'Safety & OTPs']
    })

# ================================
# # ADMIN DASHBOARD & MANAGEMENT
# ================================

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    stats = {
        'total_users': users_collection.count_documents({}),
        'active_parcels': parcels_collection.count_documents({'status': {'$nin': ['delivered', 'cancelled']}}),
        'active_drivers': users_collection.count_documents({'role': 'delivery_partner', 'verified': True})
    }

    labels = []
    completed_data = []
    new_orders_data = []
    for i in range(6, -1, -1):
        day = datetime.now() - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        labels.append(day.strftime('%a'))
        completed_data.append(parcels_collection.count_documents({
            'status': 'delivered',
            'delivered_at': {'$gte': day_start, '$lt': day_end}
        }))
        new_orders_data.append(parcels_collection.count_documents({
            'created_at': {'$gte': day_start, '$lt': day_end}
        }))

    delivery_chart_data = {
        'labels': labels,
        'completed': completed_data,
        'new_orders': new_orders_data
    }

    senders_count = users_collection.count_documents({'role': 'sender'})
    partners_count = users_collection.count_documents({'role': 'delivery_partner'})
    user_chart_data = {
        'labels': ['Senders', 'Delivery Partners'],
        'data': [senders_count, partners_count]
    }

    dashboard_data = {
        "stats": stats,
        "deliveryChart": delivery_chart_data,
        "userChart": user_chart_data
    }

    # Fetch real dynamic activities
    recent_activities = list(activity_collection.find().sort('timestamp', -1).limit(8))

    return render_template('admin/dashboard.html', dashboard_data=dashboard_data, activities=recent_activities)

@app.route('/admin/users')
@login_required
@role_required('admin')
def admin_users():
    users = list(users_collection.find({}, {'password': 0}).sort('created_at', -1))
    total_users = len(users)
    verified_users = sum(1 for u in users if u.get('verified', False))
    delivery_partners = sum(1 for u in users if u.get('role') == 'delivery_partner')
    senders = sum(1 for u in users if u.get('role') == 'sender')

    week_ago = datetime.now() - timedelta(days=7)
    recent_registrations = sum(1 for u in users if u.get('created_at', datetime.min) >= week_ago)
    delivery_partners_this_week = sum(1 for u in users if u.get('role') == 'delivery_partner' and u.get('created_at', datetime.min) >= week_ago)
    senders_this_week = sum(1 for u in users if u.get('role') == 'sender' and u.get('created_at', datetime.min) >= week_ago)

    recent_activities = list(activity_collection.find().sort('timestamp', -1).limit(6))

    return render_template('admin/users.html',
                           users=users,
                           total_users=total_users,
                           verified_users=verified_users,
                           delivery_partners=delivery_partners,
                           senders=senders,
                           recent_registrations=recent_registrations,
                           delivery_partners_this_week=delivery_partners_this_week,
                           senders_this_week=senders_this_week,
                           recent_activities=recent_activities)

@app.route('/admin/orders')
@login_required
@role_required('admin')
def admin_orders():
    stats = {
        'total_active': parcels_collection.count_documents({'status': {'$nin': ['delivered', 'cancelled']}}),
        'pending_assignments': parcels_collection.count_documents({'status': 'pending'}),
        'in_transit': parcels_collection.count_documents({'status': {'$in': ['picked_up', 'in_transit']}}),
        'delivered_today': parcels_collection.count_documents({
            'status': 'delivered',
            'delivered_at': {'$gte': datetime.now().replace(hour=0, minute=0, second=0)}
        })
    }

    parcels = list(parcels_collection.find().sort('created_at', -1))
    activities = list(activity_collection.find().sort('timestamp', -1).limit(10))

    return render_template('admin/orders.html', stats=stats, parcels=parcels, activities=activities)

@app.route('/admin/add-user', methods=['POST'])
@login_required
@role_required('admin')
def admin_add_user():
    try:
        name = request.form['name']
        email = request.form['email'].strip().lower()
        phone = request.form['phone']
        password = request.form['password']
        role = request.form['role']

        if users_collection.find_one({'email': email}):
            flash('Email already registered!', 'error')
            return redirect(url_for('admin_users'))

        user_data = {
            'name': name,
            'email': email,
            'password': generate_password_hash(password),
            'role': role,
            'phone': phone,
            'rating': 5.0,
            'created_at': datetime.now(),
            'verified': True,
            'total_parcels': 0,
            'delivered_parcels': 0,
            'points_earned': 0,
            'email_notifications': True,
            'sms_notifications': False,
            'marketing_emails': False
        }
        users_collection.insert_one(user_data)
        log_activity('User Added by Admin', f"Admin added user {name} ({role}).", 'user', 'fa-user-plus')
        flash(f'User {name} created successfully!', 'success')
    except Exception as e:
        flash(f'Error adding user: {str(e)}', 'error')

    return redirect(url_for('admin_users'))

@app.route('/admin/api/verify-user/<user_id>')
@login_required
@role_required('admin')
def verify_user(user_id):
    try:
        result = users_collection.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {'verified': True, 'suspended': False}}
        )
        if result.modified_count > 0:
            flash('User verified successfully!', 'success')
        else:
            flash('User not found.', 'error')
    except Exception as e:
        flash(f'Error verifying user: {str(e)}', 'error')
    return redirect(url_for('admin_users'))

@app.route('/admin/api/suspend-user/<user_id>')
@login_required
@role_required('admin')
def suspend_user(user_id):
    try:
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        if user and user.get('role') == 'admin':
            flash('Cannot suspend administrator accounts.', 'error')
            return redirect(url_for('admin_users'))

        users_collection.update_one({'_id': ObjectId(user_id)}, {'$set': {'verified': False, 'suspended': True}})
        flash(f"User {user.get('name', 'account')} suspended successfully.", 'warning')
    except Exception as e:
        flash(f'Error suspending user: {str(e)}', 'error')
    return redirect(url_for('admin_users'))

@app.route('/admin/api/delete-user/<user_id>')
@login_required
@role_required('admin')
def delete_user(user_id):
    try:
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        if user and user.get('role') == 'admin':
            flash('Cannot delete administrator accounts.', 'error')
            return redirect(url_for('admin_users'))

        if user_id == session.get('user_id'):
            flash('Cannot delete your own active session.', 'error')
            return redirect(url_for('admin_users'))

        users_collection.delete_one({'_id': ObjectId(user_id)})
        flash('User account deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('admin_users'))

@app.route('/admin/api/export-users')
@login_required
@role_required('admin')
def export_users():
    """Export user directory as a downloadable CSV."""
    try:
        users = list(users_collection.find({}, {'password': 0}))
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Name', 'Email', 'Phone', 'Role', 'Status', 'Joined Date', 'Total Parcels', 'Delivered', 'Points'])

        for u in users:
            status = 'Suspended' if u.get('suspended') else ('Verified' if u.get('verified') else 'Pending')
            writer.writerow([
                u.get('name', ''),
                u.get('email', ''),
                u.get('phone', ''),
                u.get('role', '').replace('_', ' ').title(),
                status,
                u.get('created_at', datetime.now()).strftime('%Y-%m-%d'),
                u.get('total_parcels', 0),
                u.get('delivered_parcels', 0),
                u.get('points_earned', 0)
            ])

        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=pathport_users_{datetime.now().strftime("%Y%m%d")}.csv'
        return response
    except Exception as e:
        flash(f'Error exporting users: {str(e)}', 'error')
        return redirect(url_for('admin_users'))

@app.route('/admin/api/search-users')
@login_required
@role_required('admin')
def search_users():
    """API endpoint to filter and search registered users."""
    query = request.args.get('q', '').strip()
    role = request.args.get('role', '').strip()

    search_criteria = {}
    if query:
        search_criteria['$or'] = [
            {'name': {'$regex': query, '$options': 'i'}},
            {'email': {'$regex': query, '$options': 'i'}}
        ]
    if role:
        search_criteria['role'] = role

    users = list(users_collection.find(search_criteria, {'password': 0}).sort('created_at', -1).limit(50))
    results = []
    for u in users:
        results.append({
            'id': str(u['_id']),
            'name': u.get('name', ''),
            'email': u.get('email', ''),
            'role': u.get('role', ''),
            'verified': u.get('verified', False),
            'points_earned': u.get('points_earned', 0)
        })
    return jsonify({'success': True, 'users': results, 'count': len(results)})

# ================================
# ERROR HANDLERS
# ================================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

# ================================
# APPLICATION ENTRYPOINT
# ================================

def auto_seed_if_empty():
    """Auto seed rich sample data if collections are empty."""
    if parcels_collection is not None and users_collection is not None:
        try:
            if parcels_collection.count_documents({}) == 0:
                print("[INFO] Database is empty. Seeding initial test data...")
                from seed import seed_database
                seed_database()
        except Exception as e:
            print(f"[NOTICE] Auto-seed status: {e}")

if __name__ == '__main__':
    create_admin_user()
    auto_seed_if_empty()
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    print("[INFO] PathPort Application Ready")
    print(f"[INFO] Serving on http://127.0.0.1:{port}")
    print("[INFO] Admin Login: admin@pathport.com / admin123")
    app.run(debug=debug, host='0.0.0.0', port=port)
