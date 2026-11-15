"""
PathPort - Comprehensive Database Seeding Script
Populates realistic sample data across all user roles, commuter routes,
active & delivered parcels, ratings, and activity feeds.
"""

from pymongo import MongoClient
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')

def seed_database():
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
        db = client['pathport_delivery']
        client.admin.command('ping')
        print(f"[OK] Connected to MongoDB at: {MONGO_URI}")
    except Exception as e:
        print(f"[ERROR] Cannot connect to MongoDB: {e}")
        return

    users_col = db['users']
    parcels_col = db['parcels']
    routes_col = db['routes']
    activity_col = db['activity']
    ratings_col = db['ratings']

    # 1. Clean existing sample data (optional, keep admin if needed)
    print("[INFO] Clearing existing collections for fresh seed...")
    users_col.delete_many({})
    parcels_col.delete_many({})
    routes_col.delete_many({})
    activity_col.delete_many({})
    ratings_col.delete_many({})

    # 2. Seed Users
    print("[INFO] Seeding Users...")
    now = datetime.now()
    users_data = [
        # Administrator
        {
            'name': 'PathPort Admin',
            'email': 'admin@pathport.com',
            'password': generate_password_hash('admin123'),
            'role': 'admin',
            'phone': '+91-9876543210',
            'rating': 5.0,
            'created_at': now - timedelta(days=60),
            'verified': True,
            'total_parcels': 0,
            'delivered_parcels': 0,
            'points_earned': 0
        },
        # Senders
        {
            'name': 'Raj Sharma',
            'email': 'raj@example.com',
            'password': generate_password_hash('password123'),
            'role': 'sender',
            'phone': '+91-9820123456',
            'rating': 4.9,
            'created_at': now - timedelta(days=35),
            'verified': True,
            'total_parcels': 14,
            'delivered_parcels': 11,
            'points_earned': 0,
            'email_notifications': True,
            'sms_notifications': True,
            'marketing_emails': False
        },
        {
            'name': 'Ananya Roy',
            'email': 'ananya@example.com',
            'password': generate_password_hash('password123'),
            'role': 'sender',
            'phone': '+91-9833445566',
            'rating': 5.0,
            'created_at': now - timedelta(days=20),
            'verified': True,
            'total_parcels': 8,
            'delivered_parcels': 7,
            'points_earned': 0,
            'email_notifications': True,
            'sms_notifications': False,
            'marketing_emails': True
        },
        {
            'name': 'Vikram Mehta',
            'email': 'vikram@example.com',
            'password': generate_password_hash('password123'),
            'role': 'sender',
            'phone': '+91-9811223344',
            'rating': 4.8,
            'created_at': now - timedelta(days=12),
            'verified': True,
            'total_parcels': 5,
            'delivered_parcels': 4,
            'points_earned': 0,
            'email_notifications': True,
            'sms_notifications': False,
            'marketing_emails': False
        },
        # Delivery Partners (Commuters)
        {
            'name': 'Arun Patel',
            'email': 'arun@example.com',
            'password': generate_password_hash('password123'),
            'role': 'delivery_partner',
            'phone': '+91-9876543211',
            'rating': 4.9,
            'created_at': now - timedelta(days=45),
            'verified': True,
            'total_parcels': 0,
            'delivered_parcels': 42,
            'points_earned': 345,
            'email_notifications': True,
            'sms_notifications': True,
            'marketing_emails': False
        },
        {
            'name': 'Priya Singh',
            'email': 'priya@example.com',
            'password': generate_password_hash('password123'),
            'role': 'delivery_partner',
            'phone': '+91-9876543212',
            'rating': 4.8,
            'created_at': now - timedelta(days=28),
            'verified': True,
            'total_parcels': 0,
            'delivered_parcels': 24,
            'points_earned': 195,
            'email_notifications': True,
            'sms_notifications': False,
            'marketing_emails': False
        },
        {
            'name': 'Rohit Verma',
            'email': 'rohit@example.com',
            'password': generate_password_hash('password123'),
            'role': 'delivery_partner',
            'phone': '+91-9876543213',
            'rating': 4.7,
            'created_at': now - timedelta(days=15),
            'verified': True,
            'total_parcels': 0,
            'delivered_parcels': 11,
            'points_earned': 95,
            'email_notifications': True,
            'sms_notifications': False,
            'marketing_emails': False
        }
    ]

    inserted_users = users_col.insert_many(users_data)
    user_map = {u['email']: str(u['_id']) for u in users_col.find()}
    print(f"[OK] Seeded {len(user_map)} users.")

    # 3. Seed Commuter Routes
    print("[INFO] Seeding Commute Routes...")
    arun_id = user_map['arun@example.com']
    priya_id = user_map['priya@example.com']
    rohit_id = user_map['rohit@example.com']

    routes_data = [
        {
            'partner_id': arun_id,
            'route_name': 'Bandra to Powai Daily Commute',
            'from_location': 'Bandra West, Mumbai',
            'to_location': 'Powai Hiranandani, Mumbai',
            'departure_time': '08:30 AM',
            'capacity': 10,
            'frequency': 'daily',
            'transport_mode': 'car',
            'active': True,
            'created_at': now - timedelta(days=40)
        },
        {
            'partner_id': arun_id,
            'route_name': 'BKC to Thane Evening Run',
            'from_location': 'BKC Bandra Kurla Complex, Mumbai',
            'to_location': 'Thane West, Maharashtra',
            'departure_time': '06:15 PM',
            'capacity': 12,
            'frequency': 'daily',
            'transport_mode': 'car',
            'active': True,
            'created_at': now - timedelta(days=30)
        },
        {
            'partner_id': priya_id,
            'route_name': 'Borivali to Dadar Metro Route',
            'from_location': 'Borivali West, Mumbai',
            'to_location': 'Dadar West, Mumbai',
            'departure_time': '09:00 AM',
            'capacity': 5,
            'frequency': 'daily',
            'transport_mode': 'public',
            'active': True,
            'created_at': now - timedelta(days=25)
        },
        {
            'partner_id': rohit_id,
            'route_name': 'Andheri to Lower Parel Highway',
            'from_location': 'Andheri East, Mumbai',
            'to_location': 'Lower Parel, Mumbai',
            'departure_time': '09:30 AM',
            'capacity': 6,
            'frequency': 'daily',
            'transport_mode': 'bike',
            'active': True,
            'created_at': now - timedelta(days=14)
        }
    ]
    routes_col.insert_many(routes_data)
    print(f"[OK] Seeded {len(routes_data)} commuter routes.")

    # 4. Seed Parcels Across Various Stages
    print("[INFO] Seeding Parcels...")
    raj_id = user_map['raj@example.com']
    ananya_id = user_map['ananya@example.com']
    vikram_id = user_map['vikram@example.com']

    parcels_data = [
        # PENDING PARCELS (Available for pickup)
        {
            'order_id': 'PP202611151010',
            'sender_id': raj_id,
            'sender_name': 'Raj Sharma',
            'title': 'Urgent Legal Property Documents',
            'description': 'Confidential contract file with stamp papers. Handle with care.',
            'pickup_location': 'Bandra West, Mumbai',
            'delivery_location': 'Powai Hiranandani, Mumbai',
            'receiver_name': 'Ramesh Iyer',
            'receiver_phone': '+91-9820987654',
            'receiver_email': 'ramesh@partnerlaw.com',
            'weight': 0.8,
            'size': 'small',
            'urgency': 'express',
            'pickup_otp': '482910',
            'delivery_otp': '739102',
            'reward_points': 25,
            'status': 'pending',
            'created_at': now - timedelta(minutes=45),
            'delivery_partner_id': None,
            'failed_otp_attempts': 0,
            'tracking_history': [
                {'status': 'pending', 'timestamp': now - timedelta(minutes=45), 'description': 'Order registered by Raj Sharma'}
            ]
        },
        {
            'order_id': 'PP202611151020',
            'sender_id': ananya_id,
            'sender_name': 'Ananya Roy',
            'title': 'Handcrafted Artisan Ceramics Gift',
            'description': 'Fragile terracotta decorative mug set in bubble wrap packaging.',
            'pickup_location': 'Andheri East, Mumbai',
            'delivery_location': 'Lower Parel, Mumbai',
            'receiver_name': 'Meera Kapoor',
            'receiver_phone': '+91-9877112233',
            'receiver_email': 'meera@gallery.org',
            'weight': 2.2,
            'size': 'medium',
            'urgency': 'urgent',
            'pickup_otp': '591823',
            'delivery_otp': '840291',
            'reward_points': 20,
            'status': 'pending',
            'created_at': now - timedelta(hours=1, minutes=20),
            'delivery_partner_id': None,
            'failed_otp_attempts': 0,
            'tracking_history': [
                {'status': 'pending', 'timestamp': now - timedelta(hours=1, minutes=20), 'description': 'Order registered by Ananya Roy'}
            ]
        },
        {
            'order_id': 'PP202611151030',
            'sender_id': vikram_id,
            'sender_name': 'Vikram Mehta',
            'title': 'Medical Diagnostic Sample Vials',
            'description': 'Temperature insulated sample box for pathological laboratory verification.',
            'pickup_location': 'Borivali West, Mumbai',
            'delivery_location': 'Dadar West, Mumbai',
            'receiver_name': 'Dr. Sunita Rao',
            'receiver_phone': '+91-9988776655',
            'receiver_email': 'srao@medlab.in',
            'weight': 1.1,
            'size': 'small',
            'urgency': 'express',
            'pickup_otp': '320914',
            'delivery_otp': '918273',
            'reward_points': 28,
            'status': 'pending',
            'created_at': now - timedelta(hours=2),
            'delivery_partner_id': None,
            'failed_otp_attempts': 0,
            'tracking_history': [
                {'status': 'pending', 'timestamp': now - timedelta(hours=2), 'description': 'Order registered by Vikram Mehta'}
            ]
        },
        {
            'order_id': 'PP202611151040',
            'sender_id': raj_id,
            'sender_name': 'Raj Sharma',
            'title': 'Gourmet Organic Bakery Basket',
            'description': 'Freshly baked sourdough and almond croissants for office celebration.',
            'pickup_location': 'Malad West, Mumbai',
            'delivery_location': 'BKC Bandra Kurla Complex, Mumbai',
            'receiver_name': 'Corporate Desk',
            'receiver_phone': '+91-9819283746',
            'receiver_email': 'reception@financehub.com',
            'weight': 3.0,
            'size': 'large',
            'urgency': 'normal',
            'pickup_otp': '741258',
            'delivery_otp': '852963',
            'reward_points': 18,
            'status': 'pending',
            'created_at': now - timedelta(hours=3),
            'delivery_partner_id': None,
            'failed_otp_attempts': 0,
            'tracking_history': [
                {'status': 'pending', 'timestamp': now - timedelta(hours=3), 'description': 'Order registered by Raj Sharma'}
            ]
        },

        # ASSIGNED PARCEL
        {
            'order_id': 'PP202611152010',
            'sender_id': ananya_id,
            'sender_name': 'Ananya Roy',
            'title': 'Replacement Ultrabook Charger & Mouse',
            'description': 'Electronics accessory packet for immediate workstation repair.',
            'pickup_location': 'Bandra West, Mumbai',
            'delivery_location': 'Powai Hiranandani, Mumbai',
            'receiver_name': 'Tanmay Joshi',
            'receiver_phone': '+91-9821345678',
            'receiver_email': 'tanmay@techcorp.io',
            'weight': 0.6,
            'size': 'small',
            'urgency': 'urgent',
            'pickup_otp': '112233',
            'delivery_otp': '445566',
            'reward_points': 18,
            'status': 'assigned',
            'created_at': now - timedelta(hours=2, minutes=30),
            'assigned_at': now - timedelta(hours=1, minutes=45),
            'delivery_partner_id': arun_id,
            'delivery_partner_name': 'Arun Patel',
            'failed_otp_attempts': 0,
            'tracking_history': [
                {'status': 'pending', 'timestamp': now - timedelta(hours=2, minutes=30), 'description': 'Order created by Ananya Roy'},
                {'status': 'assigned', 'timestamp': now - timedelta(hours=1, minutes=45), 'description': 'Delivery partner Arun Patel accepted order'}
            ]
        },

        # IN TRANSIT (PICKED UP) PARCEL
        {
            'order_id': 'PP202611153010',
            'sender_id': vikram_id,
            'sender_name': 'Vikram Mehta',
            'title': 'Architectural Floorplans & Swatches',
            'description': 'Rolled blueprint tube and material fabric finish samples.',
            'pickup_location': 'Borivali West, Mumbai',
            'delivery_location': 'Dadar West, Mumbai',
            'receiver_name': 'Studio Axis Architects',
            'receiver_phone': '+91-9892019283',
            'receiver_email': 'projects@axis.design',
            'weight': 1.5,
            'size': 'medium',
            'urgency': 'express',
            'pickup_otp': '998877',
            'delivery_otp': '332211',
            'reward_points': 24,
            'status': 'picked_up',
            'created_at': now - timedelta(hours=4),
            'assigned_at': now - timedelta(hours=3, minutes=15),
            'picked_up_at': now - timedelta(hours=1, minutes=10),
            'delivery_partner_id': priya_id,
            'delivery_partner_name': 'Priya Singh',
            'failed_otp_attempts': 0,
            'tracking_history': [
                {'status': 'pending', 'timestamp': now - timedelta(hours=4), 'description': 'Order registered by Vikram Mehta'},
                {'status': 'assigned', 'timestamp': now - timedelta(hours=3, minutes=15), 'description': 'Partner Priya Singh assigned to commute route'},
                {'status': 'picked_up', 'timestamp': now - timedelta(hours=1, minutes=10), 'description': 'Pickup OTP verified by Priya Singh. In transit on Western Line.'}
            ]
        },

        # COMPLETED (DELIVERED) PARCELS WITH RATINGS
        {
            'order_id': 'PP202611144010',
            'sender_id': raj_id,
            'sender_name': 'Raj Sharma',
            'title': 'Executed Commercial Lease Agreement',
            'description': 'Original stamped lease documents with notary seal.',
            'pickup_location': 'Bandra West, Mumbai',
            'delivery_location': 'Powai Hiranandani, Mumbai',
            'receiver_name': 'Global Capital Realty',
            'receiver_phone': '+91-9870123450',
            'receiver_email': 'contact@globalcap.com',
            'weight': 0.7,
            'size': 'small',
            'urgency': 'urgent',
            'pickup_otp': '654321',
            'delivery_otp': '123456',
            'reward_points': 22,
            'status': 'delivered',
            'created_at': now - timedelta(days=1, hours=5),
            'assigned_at': now - timedelta(days=1, hours=4),
            'picked_up_at': now - timedelta(days=1, hours=3),
            'delivered_at': now - timedelta(days=1, hours=1, minutes=30),
            'delivery_partner_id': arun_id,
            'delivery_partner_name': 'Arun Patel',
            'failed_otp_attempts': 0,
            'is_rated': True,
            'rating': 5,
            'review_comment': 'Arun was extremely courteous, verified the OTP seamlessly, and delivered the papers ahead of schedule!',
            'tracking_history': [
                {'status': 'pending', 'timestamp': now - timedelta(days=1, hours=5), 'description': 'Order placed by Raj Sharma'},
                {'status': 'assigned', 'timestamp': now - timedelta(days=1, hours=4), 'description': 'Accepted by commuter Arun Patel'},
                {'status': 'picked_up', 'timestamp': now - timedelta(days=1, hours=3), 'description': 'Pickup verified with OTP'},
                {'status': 'delivered', 'timestamp': now - timedelta(days=1, hours=1, minutes=30), 'description': 'Delivered to Global Capital Realty and confirmed with OTP'}
            ]
        },
        {
            'order_id': 'PP202611145020',
            'sender_id': ananya_id,
            'sender_name': 'Ananya Roy',
            'title': 'Exclusive Festive Handloom Saree',
            'description': 'Custom designer silk apparel gift in branded luxury carton.',
            'pickup_location': 'Andheri East, Mumbai',
            'delivery_location': 'Lower Parel, Mumbai',
            'receiver_name': 'Kavita Singhania',
            'receiver_phone': '+91-9867543219',
            'receiver_email': 'kavita@lifestyle.in',
            'weight': 1.8,
            'size': 'medium',
            'urgency': 'express',
            'pickup_otp': '876543',
            'delivery_otp': '345678',
            'reward_points': 26,
            'status': 'delivered',
            'created_at': now - timedelta(days=2, hours=3),
            'assigned_at': now - timedelta(days=2, hours=2),
            'picked_up_at': now - timedelta(days=2, hours=1),
            'delivered_at': now - timedelta(days=1, hours=22),
            'delivery_partner_id': rohit_id,
            'delivery_partner_name': 'Rohit Verma',
            'failed_otp_attempts': 0,
            'is_rated': True,
            'rating': 5,
            'review_comment': 'Speedy bike delivery despite heavy Mumbai traffic! Package was immaculate.',
            'tracking_history': [
                {'status': 'pending', 'timestamp': now - timedelta(days=2, hours=3), 'description': 'Order placed by Ananya Roy'},
                {'status': 'assigned', 'timestamp': now - timedelta(days=2, hours=2), 'description': 'Accepted by Rohit Verma'},
                {'status': 'picked_up', 'timestamp': now - timedelta(days=2, hours=1), 'description': 'Picked up and verified'},
                {'status': 'delivered', 'timestamp': now - timedelta(days=1, hours=22), 'description': 'Delivered successfully to Kavita Singhania'}
            ]
        }
    ]

    parcels_col.insert_many(parcels_data)
    print(f"[OK] Seeded {len(parcels_data)} parcels.")

    # 5. Seed Customer Ratings Collection
    print("[INFO] Seeding Ratings...")
    ratings_data = [
        {
            'order_id': 'PP202611144010',
            'sender_id': raj_id,
            'sender_name': 'Raj Sharma',
            'partner_id': arun_id,
            'rating': 5,
            'comment': 'Arun was extremely courteous, verified the OTP seamlessly, and delivered the papers ahead of schedule!',
            'created_at': now - timedelta(days=1, hours=1)
        },
        {
            'order_id': 'PP202611145020',
            'sender_id': ananya_id,
            'sender_name': 'Ananya Roy',
            'partner_id': rohit_id,
            'rating': 5,
            'comment': 'Speedy bike delivery despite heavy Mumbai traffic! Package was immaculate.',
            'created_at': now - timedelta(days=1, hours=21)
        }
    ]
    ratings_col.insert_many(ratings_data)
    print(f"[OK] Seeded {len(ratings_data)} rating reviews.")

    # 6. Seed Dynamic Activity Feed
    print("[INFO] Seeding Activity Feed...")
    activity_data = [
        {
            'title': 'Delivery Completed',
            'description': 'Arun Patel completed delivery for Order #PP202611144010 (+22 pts).',
            'type': 'delivery',
            'icon': 'fa-check-circle',
            'timestamp': now - timedelta(minutes=15)
        },
        {
            'title': 'New Parcel Placed',
            'description': "Raj Sharma registered 'Urgent Legal Property Documents' (Bandra to Powai).",
            'type': 'parcel',
            'icon': 'fa-box',
            'timestamp': now - timedelta(minutes=45)
        },
        {
            'title': 'Pickup Verified',
            'description': 'Priya Singh verified pickup OTP for Architectural Blueprints.',
            'type': 'parcel',
            'icon': 'fa-truck-loading',
            'timestamp': now - timedelta(hours=1, minutes=10)
        },
        {
            'title': 'Commuter Accepted Job',
            'description': 'Arun Patel accepted parcel delivery #PP202611152010.',
            'type': 'delivery',
            'icon': 'fa-handshake',
            'timestamp': now - timedelta(hours=1, minutes=45)
        },
        {
            'title': '5-Star Review Received',
            'description': 'Ananya Roy left a 5-star rating for Rohit Verma.',
            'type': 'rating',
            'icon': 'fa-star',
            'timestamp': now - timedelta(hours=2, minutes=20)
        },
        {
            'title': 'New Commute Route',
            'description': 'Rohit Verma registered route: Andheri to Lower Parel.',
            'type': 'delivery',
            'icon': 'fa-route',
            'timestamp': now - timedelta(hours=5)
        },
        {
            'title': 'User Verified',
            'description': 'Administrator verified delivery partner Priya Singh.',
            'type': 'user',
            'icon': 'fa-user-check',
            'timestamp': now - timedelta(days=1, hours=3)
        }
    ]
    activity_col.insert_many(activity_data)
    print(f"[OK] Seeded {len(activity_data)} system activities.")

    print("\n" + "="*50)
    print("✅ DATABASE SEEDING COMPLETED SUCCESSFULLY!")
    print("="*50)
    print("🔑 Test User Accounts:")
    print("   • Admin:    admin@pathport.com  / admin123")
    print("   • Sender:   raj@example.com    / password123")
    print("   • Sender:   ananya@example.com / password123")
    print("   • Partner:  arun@example.com   / password123 (345 pts)")
    print("   • Partner:  priya@example.com  / password123 (195 pts)")
    print("="*50 + "\n")

if __name__ == '__main__':
    seed_database()
