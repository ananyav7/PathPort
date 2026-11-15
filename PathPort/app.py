from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import os
import base64
from functools import wraps
import random
from io import StringIO
import csv

app = Flask(__name__)
app.secret_key = 'pathport-ai-delivery-secret-key-2024'

# MongoDB connection and collection initialization
try:
    client = MongoClient('mongodb://localhost:27017/')
    db = client['pathport_delivery']
    
    # Initialize collections
    users_collection = db['users']
    parcels_collection = db['parcels']
    routes_collection = db['routes']
    activity_collection = db['activity']
    ratings_collection = db['ratings']
    
    # Create indexes for better performance
    parcels_collection.create_index([('sender_id', 1)])
    parcels_collection.create_index([('delivery_partner_id', 1)])
    parcels_collection.create_index([('status', 1)])
    parcels_collection.create_index([('order_id', 1)], unique=True)
    parcels_collection.create_index([('created_at', -1)])
    
    # Test connection
    client.admin.command('ping')
    print("✅ MongoDB connected successfully!")
    
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")
    exit(1)

# Authentication decorator
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
                flash('Access denied. Insufficient permissions.', 'error')
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Helper function to create admin user if doesn't exist
def create_admin_user():
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
            'delivered_parcels': 0
        }
        users_collection.insert_one(admin_user)
        print("✅ Admin user created: admin@pathport.com / admin123")

# Add this function to solve the NameError, placing it before any route calls it
def log_activity(title, description, activity_type, icon):
    """Log an activity for the admin dashboard/activity feed."""
    activity_collection.insert_one({
        'title': title,
        'description': description,
        'type': activity_type,
        'icon': icon,
        'timestamp': datetime.now()
    })

# Add this function at the top with other utility functions
def generate_order_id():
    """Generate a unique order ID"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M')
    random_digits = ''.join(random.choices('0123456789', k=4))
    return f'PP{timestamp}{random_digits}'

# ================================
# MAIN ROUTES
# ================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = users_collection.find_one({'email': email})
        
        if user and check_password_hash(user['password'], password):
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
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirmPassword']
        role = request.form['role']
        phone = request.form['phone']
        
        # Validation
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        if users_collection.find_one({'email': email}):
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        # Create new user
        hashed_password = generate_password_hash(password)
        user_data = {
            'name': name,
            'email': email,
            'password': hashed_password,
            'role': role,
            'phone': phone,
            'rating': 5.0,
            'created_at': datetime.now(),
            'verified': False,
            'total_parcels': 0,
            'delivered_parcels': 0,
            'points_earned': 0,
            'email_notifications': True,
            'sms_notifications': False,
            'marketing_emails': False
        }
        
        users_collection.insert_one(user_data)
        flash('Registration successful! Please login to continue.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    user_name = session.get('user_name', 'User')
    session.clear()
    flash(f'Goodbye, {user_name}! You have been logged out.', 'info')
    return redirect(url_for('index'))

# ================================
# UPDATED ADMIN ROUTES
# ================================

@app.route('/admin/users')
@login_required
@role_required('admin')
def admin_users():
    # Get all users except current admin
    users = list(users_collection.find({}, {'password': 0}).sort('created_at', -1))
    
    # Calculate statistics
    total_users = len(users)
    verified_users = sum(1 for user in users if user.get('verified', False))
    delivery_partners = sum(1 for user in users if user.get('role') == 'delivery_partner')
    senders = sum(1 for user in users if user.get('role') == 'sender')
    
    # Calculate recent registrations (last 7 days)
    week_ago = datetime.now() - timedelta(days=7)
    recent_registrations = sum(1 for user in users if user.get('created_at', datetime.min) >= week_ago)
    delivery_partners_this_week = sum(1 for user in users 
                                      if user.get('role') == 'delivery_partner' 
                                      and user.get('created_at', datetime.min) >= week_ago)
    senders_this_week = sum(1 for user in users 
                            if user.get('role') == 'sender' 
                            and user.get('created_at', datetime.min) >= week_ago)
    
    # Get recent activities
    recent_activities = []
    recent_users = sorted([user for user in users if user.get('created_at', datetime.min) >= week_ago], 
                          key=lambda x: x.get('created_at', datetime.min), reverse=True)[:5]
    
    for user in recent_users:
        time_diff = datetime.now() - user.get('created_at', datetime.min)
        if time_diff.days == 0:
            if time_diff.seconds < 3600:
                time_ago = f"{time_diff.seconds // 60} mins ago"
            else:
                time_ago = f"{time_diff.seconds // 3600} hours ago"
        else:
            time_ago = f"{time_diff.days} days ago"
            
        recent_activities.append({
            'title': 'New user registered',
            'description': f"{user['name']} registered as a {user['role'].replace('_', ' ')}",
            'time_ago': time_ago
        })
    
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

@app.route('/admin/add-user', methods=['POST'])
@login_required
@role_required('admin')
def admin_add_user():
    try:
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        role = request.form['role']
        
        # Check if email already exists
        if users_collection.find_one({'email': email}):
            flash('Email already exists!', 'error')
            return redirect(url_for('admin_users'))
        
        # Create new user
        hashed_password = generate_password_hash(password)
        user_data = {
            'name': name,
            'email': email,
            'password': hashed_password,
            'role': role,
            'phone': phone,
            'rating': 5.0,
            'created_at': datetime.now(),
            'verified': True,  # Admin-created users are auto-verified
            'total_parcels': 0,
            'delivered_parcels': 0,
            'points_earned': 0,
            'email_notifications': True,
            'sms_notifications': False,
            'marketing_emails': False
        }
        
        users_collection.insert_one(user_data)
        flash(f'User {name} added successfully!', 'success')
        
    except Exception as e:
        flash(f'Error adding user: {str(e)}', 'error')
    
    return redirect(url_for('admin_users'))

# Update the existing admin dashboard route to show actual statistics
@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    # Calculate the statistics from the database
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
        
        labels.append(day.strftime('%a')) # e.g., 'Mon'
        
        completed_count = parcels_collection.count_documents({
            'status': 'delivered',
            'delivered_at': {'$gte': day_start, '$lt': day_end}
        })
        completed_data.append(completed_count)

        new_orders_count = parcels_collection.count_documents({
            'created_at': {'$gte': day_start, '$lt': day_end}
        })
        new_orders_data.append(new_orders_count)

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

    # --- 4. Consolidate all data to pass to the template ---
    dashboard_data = {
        "stats": stats,
        "deliveryChart": delivery_chart_data,
        "userChart": user_chart_data
    }

    return render_template('admin/dashboard.html', dashboard_data=dashboard_data)
    
@app.route('/admin/orders')
@login_required
@role_required('admin')
def admin_orders():
    # Get statistics
    stats = {
        'total_active': parcels_collection.count_documents({
            'status': {'$nin': ['delivered', 'cancelled']}
        }),
        'pending_assignments': parcels_collection.count_documents({
            'status': 'pending'
        }),
        'in_transit': parcels_collection.count_documents({
            'status': {'$in': ['picked_up', 'in_transit']}
        }),
        'delivered_today': parcels_collection.count_documents({
            'status': 'delivered',
            'delivered_at': {'$gte': datetime.now().replace(hour=0, minute=0, second=0)}
        })
    }

    # Get all parcels with user details using aggregation
    parcels = list(parcels_collection.aggregate([
        {
            '$lookup': {
                'from': 'users',
                'let': { 'sender_obj_id': { '$toObjectId': '$sender_id' } },
                'pipeline': [
                    { '$match': { '$expr': { '$eq': [ '$_id', '$$sender_obj_id' ] } } }
                ],
                'as': 'sender'
            }
        },
        {
            '$lookup': {
                'from': 'users',
                'let': {
                    'partner_obj_id': {
                        '$cond': {
                            'if': '$delivery_partner_id',
                            'then': { '$toObjectId': '$delivery_partner_id' },
                            'else': None
                        }
                    }
                },
                'pipeline': [
                    { '$match': { '$expr': { '$eq': [ '$_id', '$$partner_obj_id' ] } } }
                ],
                'as': 'delivery_partner'
            }
        },
        {
            '$unwind': {
                'path': '$sender',
                'preserveNullAndEmptyArrays': True
            }
        },
        {
            '$unwind': {
                'path': '$delivery_partner',
                'preserveNullAndEmptyArrays': True
            }
        },
        {
            '$sort': {'created_at': -1}
        }
    ]))

    # Get recent activities
    activities = list(activity_collection.find().sort('timestamp', -1).limit(10))

    return render_template('admin/orders.html', 
                           stats=stats, 
                           parcels=parcels, 
                           activities=activities)

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
            # Get user info for notification
            user = users_collection.find_one({'_id': ObjectId(user_id)}, {'name': 1})
            flash(f'User {user["name"] if user else "Unknown"} verified successfully!', 'success')
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
        # Don't allow suspension of admin users
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        if user and user.get('role') == 'admin':
            flash('Cannot suspend admin users.', 'error')
            return redirect(url_for('admin_users'))
        
        result = users_collection.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {'verified': False, 'suspended': True}}
        )
        
        if result.modified_count > 0:
            flash(f'User {user["name"] if user else "Unknown"} suspended successfully!', 'warning')
            
            # Also cancel any active deliveries for delivery partners
            if user and user.get('role') == 'delivery_partner':
                parcels_collection.update_many(
                    {'delivery_partner_id': user_id, 'status': {'$in': ['assigned', 'picked_up']}},
                    {'$set': {'status': 'pending', 'delivery_partner_id': None}}
                )
        else:
            flash('User not found.', 'error')
            
    except Exception as e:
        flash(f'Error suspending user: {str(e)}', 'error')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/api/delete-user/<user_id>')
@login_required
@role_required('admin')
def delete_user(user_id):
    try:
        # Don't allow deletion of admin users or current user
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        if user and user.get('role') == 'admin':
            flash('Cannot delete admin users.', 'error')
            return redirect(url_for('admin_users'))
        
        if user_id == session['user_id']:
            flash('Cannot delete your own account.', 'error')
            return redirect(url_for('admin_users'))
        
        result = users_collection.delete_one({'_id': ObjectId(user_id)})
        
        if result.deleted_count > 0:
            # Clean up related data
            parcels_collection.update_many(
                {'sender_id': user_id},
                {'$set': {'sender_id': None}}  # Keep parcels but remove reference
            )
            parcels_collection.update_many(
                {'delivery_partner_id': user_id, 'status': {'$in': ['assigned', 'picked_up']}},
                {'$set': {'status': 'pending', 'delivery_partner_id': None}}
            )
            routes_collection.delete_many({'partner_id': user_id})
            
            flash(f'User {user["name"] if user else "Unknown"} and associated data deleted successfully!', 'success')
        else:
            flash('User not found.', 'error')
            
    except Exception as e:
        flash(f'Error deleting user: {str(e)}', 'error')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/api/export-users')
@login_required
@role_required('admin')
def export_users():
    """Export users to CSV"""
    try:
        
        # Get all users
        users = list(users_collection.find({}, {
            'name': 1, 'email': 1, 'phone': 1, 'role': 1, 
            'verified': 1, 'created_at': 1, 'total_parcels': 1, 
            'delivered_parcels': 1, 'points_earned': 1, 'rating': 1
        }))
        
        # Create CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Name', 'Email', 'Phone', 'Role', 'Status', 'Joined Date',
            'Total Parcels', 'Delivered Parcels', 'Points Earned', 'Rating'
        ])
        
        # Data rows
        for user in users:
            status = 'Verified' if user.get('verified', False) else 'Pending'
            if user.get('suspended', False):
                status = 'Suspended'
                
            writer.writerow([
                user.get('name', ''),
                user.get('email', ''),
                user.get('phone', ''),
                user.get('role', '').replace('_', ' ').title(),
                status,
                user.get('created_at', datetime.now()).strftime('%Y-%m-%d'),
                user.get('total_parcels', 0),
                user.get('delivered_parcels', 0),
                user.get('points_earned', 0),
                user.get('rating', 0)
            ])
        
        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=pathport_users_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        return response
        
    except Exception as e:
        flash(f'Error exporting users: {str(e)}', 'error')
        return redirect(url_for('admin_users'))

# Add this route for user search API
@app.route('/admin/api/search-users')
@login_required
@role_required('admin')
def search_users():
    """API endpoint for searching users"""
    query = request.args.get('q', '').strip()
    role = request.args.get('role', '').strip()
    status = request.args.get('status', '').strip()
    
    # Build search criteria
    search_criteria = {}
    
    if query:
        search_criteria['$or'] = [
            {'name': {'$regex': query, '$options': 'i'}},
            {'email': {'$regex': query, '$options': 'i'}}
        ]
    
    if role:
        search_criteria['role'] = role
    
    if status == 'verified':
        search_criteria['verified'] = True
        search_criteria['suspended'] = {'$ne': True}
    elif status == 'pending':
        search_criteria['verified'] = False
        search_criteria['suspended'] = {'$ne': True}
    elif status == 'suspended':
        search_criteria['suspended'] = True
    
    # Execute search
    users = list(users_collection.find(search_criteria, {'password': 0})
                 .sort('created_at', -1).limit(50))
    
    # Format results
    results = []
    for user in users:
        results.append({
            'id': str(user['_id']),
            'name': user.get('name', ''),
            'email': user.get('email', ''),
            'phone': user.get('phone', ''),
            'role': user.get('role', ''),
            'verified': user.get('verified', False),
            'suspended': user.get('suspended', False),
            'created_at': user.get('created_at', datetime.now()).strftime('%d %b %Y'),
            'total_parcels': user.get('total_parcels', 0),
            'delivered_parcels': user.get('delivered_parcels', 0),
            'points_earned': user.get('points_earned', 0),
            'rating': user.get('rating', 0)
        })
    
    return jsonify({
        'success': True,
        'users': results,
        'count': len(results)
    })

# ================================
# SENDER ROUTES
# ================================

@app.route('/sender/dashboard')
@login_required
def sender_dashboard():
    user_id = session['user_id']
    my_parcels = list(parcels_collection.find({'sender_id': user_id}).sort('created_at', -1))
    return render_template('sender/dashboard.html', parcels=my_parcels)


@app.route('/sender/create-parcel', methods=['GET', 'POST'])
@login_required
def create_parcel():
    if request.method == 'POST':
        # Generate unique order ID
        order_id = generate_order_id()
        
        # Generate OTPs for pickup and delivery
        pickup_otp = ''.join(random.choices('0123456789', k=6))
        delivery_otp = ''.join(random.choices('0123456789', k=6))
        
        parcel_data = {
            'order_id': order_id,
            'sender_id': session['user_id'],
            'sender_name': session['user_name'],
            'title': request.form['title'],
            'description': request.form.get('description', ''),
            'pickup_location': request.form['pickup_location'],
            'delivery_location': request.form['delivery_location'],
            'receiver_name': request.form['receiver_name'],
            'receiver_phone': request.form['receiver_phone'],
            'receiver_email': request.form['receiver_email'],
            'weight': float(request.form['weight']),
            'size': request.form['size'],
            'urgency': request.form['urgency'],
            'pickup_otp': pickup_otp,
            'delivery_otp': delivery_otp,
            'reward_points': int(request.form.get('reward_points', 10)),
            'status': 'pending',
            'created_at': datetime.now(),
            'delivery_partner_id': None,
            'tracking_history': [{
                'status': 'pending',
                'timestamp': datetime.now(),
                'description': 'Parcel registered'
            }]
        }
        
        # Handle image upload
        if 'parcel_image' in request.files:
            file = request.files['parcel_image']
            if file and file.filename:
                # Convert image to base64 for MongoDB storage
                image_data = base64.b64encode(file.read()).decode('utf-8')
                parcel_data['image'] = {
                    'data': image_data,
                    'filename': secure_filename(file.filename),
                    'mimetype': file.content_type
                }

        parcels_collection.insert_one(parcel_data)
        log_activity('New Parcel', f"Parcel '{parcel_data['title']}' created by {session['user_name']}.", 'parcel', 'fa-box')
        
        # Update user's parcel count
        users_collection.update_one(
            {'_id': ObjectId(session['user_id'])},
            {'$inc': {'total_parcels': 1}}
        )
        
        flash(f'Parcel created successfully! Order ID: {order_id}', 'success')
        return redirect(url_for('sender_dashboard'))
    
    return render_template('sender/create_parcel.html')

@app.route('/sender/track-parcel')
@login_required
def track_parcel():
    user_id = session['user_id']
    parcels = list(parcels_collection.find({'sender_id': user_id}).sort('created_at', -1))
    return render_template('sender/track_parcel.html', parcels=parcels)

@app.route('/sender/profile', methods=['GET', 'POST'])
@login_required
def sender_profile():
    user_id = session['user_id']
    
    if request.method == 'POST':
        update_data = {
            'name': request.form['name'],
            'phone': request.form['phone'],
            'address': request.form.get('address', ''),
            'email_notifications': 'email_notifications' in request.form,
            'sms_notifications': 'sms_notifications' in request.form,
            'marketing_emails': 'marketing_emails' in request.form
        }
        
        users_collection.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': update_data}
        )
        
        session['user_name'] = update_data['name']
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('sender_profile'))
    
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    return render_template('sender/profile.html', user=user)

# ================================
# DELIVERY PARTNER ROUTES
# ================================

@app.route('/delivery/dashboard')
@login_required
@role_required('delivery_partner')
def delivery_dashboard():
    partner_id = session['user_id']
    assigned_parcels = list(parcels_collection.find({'delivery_partner_id': partner_id}).sort('created_at', -1))
    available_parcels = list(parcels_collection.find({'status': 'pending'}).sort('created_at', -1).limit(10))
    
    return render_template('delivery/dashboard.html', 
                           assigned_parcels=assigned_parcels, 
                           available_parcels=available_parcels)

@app.route('/delivery/available-parcels')
@login_required
@role_required('delivery_partner')
def available_parcels():
    parcels = list(parcels_collection.find({'status': 'pending'}).sort('created_at', -1))
    return render_template('delivery/available_parcels.html', parcels=parcels)

@app.route('/delivery/my-routes', methods=['GET', 'POST'])
@login_required
@role_required('delivery_partner')
def my_routes():
    if request.method == 'POST':
        route_data = {
            'partner_id': session['user_id'],
            'route_name': request.form['route_name'],
            'from_location': request.form['from_location'],
            'to_location': request.form['to_location'],
            'departure_time': request.form['departure_time'],
            'capacity': int(request.form['capacity']),
            'frequency': request.form['frequency'],
            'transport_mode': request.form['transport'],
            'active': True,
            'created_at': datetime.now()
        }
        
        routes_collection.insert_one(route_data)
        flash('Route added successfully! You will start receiving matching parcels.', 'success')
        return redirect(url_for('my_routes'))
    
    partner_id = session['user_id']
    routes = list(routes_collection.find({'partner_id': partner_id}).sort('created_at', -1))
    return render_template('delivery/my_routes.html', routes=routes)

@app.route('/delivery/earnings')
@login_required
@role_required('delivery_partner')
def delivery_earnings():
    partner_id = session['user_id']
    completed_deliveries = list(parcels_collection.find({
        'delivery_partner_id': partner_id, 
        'status': 'delivered'
    }).sort('delivered_at', -1))
    
    total_points = sum(parcel.get('reward_points', 10) for parcel in completed_deliveries)
    
    return render_template('delivery/earnings.html', 
                           deliveries=completed_deliveries, 
                           total_points=total_points)

@app.route('/delivery/verify-otp')
@login_required
@role_required('delivery_partner')
def verify_otp_page():
    # Get active parcels for the delivery partner
    active_parcels = list(parcels_collection.find({
        'delivery_partner_id': session['user_id'],
        'status': {'$in': ['assigned', 'picked_up']}
    }).sort('created_at', -1))
    
    return render_template('delivery/verify_otp.html', active_parcels=active_parcels)

# ================================
# API ROUTES
# ================================

@app.route('/api/accept-parcel/<parcel_id>')
@login_required
@role_required('delivery_partner')
def accept_parcel(parcel_id):
    try:
        result = parcels_collection.update_one(
            {'_id': ObjectId(parcel_id), 'status': 'pending'},
            {'$set': {
                'delivery_partner_id': session['user_id'],
                'status': 'assigned',
                'assigned_at': datetime.now()
            }}
        )
        
        if result.modified_count > 0:
            flash('Parcel accepted successfully! Contact the sender to arrange pickup.', 'success')
        else:
            flash('Parcel is no longer available or already assigned.', 'warning')
            
    except Exception as e:
        flash(f'Error accepting parcel: {str(e)}', 'error')
    
    return redirect(url_for('delivery_dashboard'))

@app.route('/api/update-parcel-status/<parcel_id>/<status>')
@login_required
@role_required('delivery_partner')
def update_parcel_status(parcel_id, status):
    try:
        update_data = {'status': status}
        
        if status == 'picked_up':
            update_data['picked_up_at'] = datetime.now()
        elif status == 'delivered':
            update_data['delivered_at'] = datetime.now()
            
            # Award points to delivery partner
            parcel = parcels_collection.find_one({'_id': ObjectId(parcel_id)})
            if parcel:
                points = parcel.get('reward_points', 10)
                users_collection.update_one(
                    {'_id': ObjectId(session['user_id'])},
                    {'$inc': {
                        'points_earned': points,
                        'delivered_parcels': 1
                    }}
                )
                session['points_earned'] = session.get('points_earned', 0) + points
        
        parcels_collection.update_one(
            {'_id': ObjectId(parcel_id)},
            {'$set': update_data}
        )
        
        return jsonify({'success': True, 'message': f'Parcel status updated to {status}'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/delete-route/<route_id>')
@login_required
@role_required('delivery_partner')
def delete_route(route_id):
    try:
        result = routes_collection.delete_one({
            '_id': ObjectId(route_id),
            'partner_id': session['user_id']
        })
        
        if result.deleted_count > 0:
            flash('Route deleted successfully!', 'success')
        else:
            flash('Route not found or you do not have permission to delete it.', 'error')
            
    except Exception as e:
        flash(f'Error deleting route: {str(e)}', 'error')
    
    return redirect(url_for('my_routes'))

@app.route('/api/toggle-route-status/<route_id>')
@login_required
@role_required('delivery_partner')
def toggle_route_status(route_id):
    try:
        route = routes_collection.find_one({
            '_id': ObjectId(route_id),
            'partner_id': session['user_id']
        })
        
        if route:
            new_status = not route.get('active', True)
            routes_collection.update_one(
                {'_id': ObjectId(route_id)},
                {'$set': {'active': new_status}}
            )
            
            status_text = 'activated' if new_status else 'deactivated'
            flash(f'Route {status_text} successfully!', 'success')
        else:
            flash('Route not found.', 'error')
            
    except Exception as e:
        flash(f'Error updating route status: {str(e)}', 'error')
    
    return redirect(url_for('my_routes'))

def update_parcel_tracking(order_id, status, description):
    """Update parcel tracking history"""
    parcels_collection.update_one(
        {'order_id': order_id},
        {
            '$push': {
                'tracking_history': {
                    'status': status,
                    'timestamp': datetime.now(),
                    'description': description
                }
            }
        }
    )

@app.route('/api/track-parcel/<order_id>')
def track_parcel_api(order_id):
    parcel = parcels_collection.find_one({'order_id': order_id})
    if not parcel:
        return jsonify({'success': False, 'message': 'Invalid order ID'}), 404
    
    # Remove sensitive information
    parcel.pop('pickup_otp', None)
    parcel.pop('delivery_otp', None)
    parcel.pop('_id', None)
    
    return jsonify({
        'success': True,
        'parcel': parcel,
        'tracking_history': parcel.get('tracking_history', [])
    })

@app.route('/api/parcel-details/<parcel_id>')
@login_required
def get_parcel_details(parcel_id):
    try:
        parcel = parcels_collection.find_one({'_id': ObjectId(parcel_id)})
        if not parcel:
            return jsonify({'error': 'Parcel not found'}), 404
            
        # Convert ObjectId to string for JSON serialization
        parcel['_id'] = str(parcel['_id'])
        
        # Convert datetime objects to strings
        for key in ['created_at', 'assigned_at', 'picked_up_at', 'delivered_at']:
            if key in parcel and parcel[key]:
                parcel[key] = parcel[key].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(parcel)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/parcel-details/<parcel_id>')
@login_required
@role_required('admin')
def get_admin_parcel_details(parcel_id):
    try:
        parcel = parcels_collection.find_one({'_id': ObjectId(parcel_id)})
        if not parcel:
            return jsonify({'error': 'Parcel not found'}), 404

        # Add sender and delivery partner details
        parcel['sender'] = users_collection.find_one({'_id': ObjectId(parcel['sender_id'])})
        if parcel.get('delivery_partner_id'):
            parcel['delivery_partner'] = users_collection.find_one(
                {'_id': ObjectId(parcel['delivery_partner_id'])}
            )

        # Convert ObjectId to string
        parcel['_id'] = str(parcel['_id'])
        if parcel['sender']:
            parcel['sender']['_id'] = str(parcel['sender']['_id'])
        if parcel.get('delivery_partner'):
            parcel['delivery_partner']['_id'] = str(parcel['delivery_partner']['_id'])

        return jsonify(parcel)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
# UTILITY FUNCTIONS
# ================================

def init_sample_data():
    """Initialize sample data for demonstration"""
    # Check if sample data already exists
    if users_collection.count_documents({}) > 1:  # More than just admin
        return
    
    # Create sample users
    sample_users = [
        {
            'name': 'Raj Sharma',
            'email': 'raj@example.com',
            'password': generate_password_hash('password123'),
            'role': 'sender',
            'phone': '+91-9876543210',
            'rating': 4.8,
            'created_at': datetime.now() - timedelta(days=15),
            'verified': True,
            'total_parcels': 24,
            'delivered_parcels': 22
        },
        {
            'name': 'Arun Patel',
            'email': 'arun@example.com',
            'password': generate_password_hash('password123'),
            'role': 'delivery_partner',
            'phone': '+91-9876543211',
            'rating': 4.9,
            'created_at': datetime.now() - timedelta(days=12),
            'verified': True,
            'points_earned': 320,
            'delivered_parcels': 47
        },
        {
            'name': 'Priya Singh',
            'email': 'priya@example.com',
            'password': generate_password_hash('password123'),
            'role': 'delivery_partner',
            'phone': '+91-9876543212',
            'rating': 4.7,
            'created_at': datetime.now() - timedelta(days=5),
            'verified': False,
            'points_earned': 0,
            'delivered_parcels': 0
        }
    ]
    
    for user in sample_users:
        if not users_collection.find_one({'email': user['email']}):
            users_collection.insert_one(user)
    
    # Create sample parcels
    # Find the newly created user IDs for linking
    raj_id = str(users_collection.find_one({'email': 'raj@example.com'})['_id'])
    arun_id = str(users_collection.find_one({'email': 'arun@example.com'})['_id'])

    sample_parcels = [
        {
            'sender_id': raj_id,
            'sender_name': 'Raj Sharma',
            'title': 'Important Documents',
            'description': 'Legal papers for signature',
            'order_id': generate_order_id(),
            'pickup_location': 'Malad West, Mumbai',
            'delivery_location': 'Bandra East, Mumbai',
            'receiver_name': 'Receiver One',
            'receiver_phone': '9999900001',
            'receiver_email': 'receiver1@mail.com',
            'weight': 0.5,
            'size': 'small',
            'urgency': 'urgent',
            'reward_points': 15,
            'pickup_otp': '123456',
            'delivery_otp': '654321',
            'status': 'delivered',
            'delivery_partner_id': arun_id,
            'created_at': datetime.now() - timedelta(days=3),
            'assigned_at': datetime.now() - timedelta(days=3, hours=1),
            'picked_up_at': datetime.now() - timedelta(days=3, hours=3),
            'delivered_at': datetime.now() - timedelta(days=3, hours=5),
            'tracking_history': [
                {'status': 'pending', 'timestamp': datetime.now() - timedelta(days=3), 'description': 'Parcel registered'},
                {'status': 'assigned', 'timestamp': datetime.now() - timedelta(days=3, hours=1), 'description': 'Assigned to Arun Patel'},
                {'status': 'picked_up', 'timestamp': datetime.now() - timedelta(days=3, hours=3), 'description': 'Picked up by Arun Patel'},
                {'status': 'delivered', 'timestamp': datetime.now() - timedelta(days=3, hours=5), 'description': 'Delivered successfully'}
            ]
        },
        {
            'sender_id': raj_id,
            'sender_name': 'Raj Sharma',
            'title': 'Electronics Package',
            'description': 'Mobile phone for repair',
            'order_id': generate_order_id(),
            'pickup_location': 'Goregaon, Mumbai',
            'delivery_location': 'Lower Parel, Mumbai',
            'receiver_name': 'Receiver Two',
            'receiver_phone': '9999900002',
            'receiver_email': 'receiver2@mail.com',
            'weight': 1.2,
            'size': 'medium',
            'urgency': 'normal',
            'reward_points': 10,
            'pickup_otp': '234567',
            'delivery_otp': '765432',
            'status': 'assigned',
            'delivery_partner_id': arun_id,
            'created_at': datetime.now() - timedelta(hours=4),
            'assigned_at': datetime.now() - timedelta(hours=2),
            'tracking_history': [
                {'status': 'pending', 'timestamp': datetime.now() - timedelta(hours=4), 'description': 'Parcel registered'},
                {'status': 'assigned', 'timestamp': datetime.now() - timedelta(hours=2), 'description': 'Assigned to Arun Patel'}
            ]
        }
    ]
    
    for parcel in sample_parcels:
        if not parcels_collection.find_one({'title': parcel['title']}):
            parcels_collection.insert_one(parcel)
    
    print("✅ Sample data initialized!")

@app.route('/generate_otp')
def generate_otp():
    new_otp = ''.join(random.choices('0123456789', k=6))
    return jsonify({'otp': new_otp})

@app.template_filter('timeago')
def timeago(date):
    now = datetime.now()
    diff = now - date

    if diff.days > 0:
        return f"{diff.days} days ago"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600} hours ago"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60} minutes ago"
    else:
        return "Just now"

@app.route('/track/<order_id>')
def track_parcel_status(order_id):
    # Get parcel details from database
    parcel = parcels_collection.find_one({'order_id': order_id})
    if not parcel:
        flash('Invalid order ID')
        return redirect(url_for('index'))
    
    return render_template('tracking.html', parcel=parcel)

@app.route('/api/parcel-location/<order_id>')
def get_parcel_location(order_id):
    # Get current location from database
    parcel = parcels_collection.find_one({'order_id': order_id})
    if not parcel:
        return jsonify({'error': 'Invalid order ID'}), 404
    
    # NOTE: This assumes 'current_location' exists in your parcel schema,
    # but it was not defined in the parcel creation or sample data.
    # We will return dummy data for now.
    dummy_location = {
        'lat': 19.0760, # Mumbai latitude
        'lng': 72.8777 # Mumbai longitude
    }

    return jsonify(parcel.get('current_location', dummy_location))


@app.route('/api/verify-pickup-otp', methods=['POST'])
@login_required
@role_required('delivery_partner')
def verify_pickup_otp():
    data = request.get_json()
    order_id = data.get('orderId')
    otp = data.get('otp')

    # Get parcel from database
    parcel = parcels_collection.find_one({'order_id': order_id})
    
    if not parcel:
        return jsonify({'success': False, 'message': 'Invalid order ID'}), 404
    
    if parcel.get('pickup_otp') == otp:
        # Update parcel status to picked up
        parcels_collection.update_one(
            {'order_id': order_id},
            {
                '$set': {
                    'status': 'picked_up',
                    'picked_up_at': datetime.now(),
                    'picked_up_by': session['user_id']
                }
            }
        )
        update_parcel_tracking(order_id, 'picked_up', f"Parcel picked up by {session['user_name']}.")
        return jsonify({'success': True, 'message': 'Pickup verified successfully'})
    
    return jsonify({'success': False, 'message': 'Invalid OTP'}), 400

@app.route('/api/verify-delivery-otp', methods=['POST'])
@login_required
@role_required('delivery_partner')
def verify_delivery_otp():
    data = request.get_json()
    order_id = data.get('orderId')
    otp = data.get('otp')

    # Get parcel from database
    parcel = parcels_collection.find_one({'order_id': order_id})
    
    if not parcel:
        return jsonify({'success': False, 'message': 'Invalid order ID'}), 404
    
    if parcel.get('delivery_otp') == otp:
        # Update parcel status to delivered
        parcels_collection.update_one(
            {'order_id': order_id},
            {
                '$set': {
                    'status': 'delivered',
                    'delivered_at': datetime.now(),
                    'delivered_by': session['user_id']
                }
            }
        )
        update_parcel_tracking(order_id, 'delivered', f"Parcel delivered successfully to {parcel['receiver_name']}.")

        # Award points to delivery partner and log activity
        partner_name = users_collection.find_one({'_id': ObjectId(session['user_id'])})['name']
        log_activity('Parcel Delivered', f"Parcel '{parcel['order_id']}' was delivered by {partner_name}.", 'delivery', 'fa-check-circle')
        
        # Award points and update delivered count (logic repeated from update_parcel_status for completeness)
        points = parcel.get('reward_points', 10)
        users_collection.update_one(
            {'_id': ObjectId(session['user_id'])},
            {'$inc': {
                'points_earned': points,
                'delivered_parcels': 1
            }}
        )
        session['points_earned'] = session.get('points_earned', 0) + points

        return jsonify({'success': True, 'message': 'Delivery verified successfully'})
    
    return jsonify({'success': False, 'message': 'Invalid OTP'}), 400

# ================================
# APPLICATION INITIALIZATION
# ================================

if __name__ == '__main__':
    # Create admin user and sample data
    create_admin_user()
    init_sample_data()
    
    print("🚀 PathPort Application Starting...")
    print("📝 Admin Login: admin@pathport.com / admin123")
    print("👤 Sample Users: raj@example.com (Sender), arun@example.com (Partner) / password123")
    
    app.run(debug=True, host='0.0.0.0', port=5000)