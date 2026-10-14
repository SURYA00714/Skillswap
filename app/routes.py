import os
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, current_app
from firebase_admin import storage, firestore
from .firebase_config import db, bucket
from datetime import datetime, timedelta
import random
from math import ceil
import uuid
import time

main = Blueprint('main', __name__)

# ----------------------- Helper ------------------
def generate_random_rating():
    value = round(random.uniform(1, 5), 1)
    return int(value) if value.is_integer() else value

def get_avatar_url(photo_url, name, email=""):
    """
    Profile images determined by their email address and credentials.
    Generates a high-quality Google-style letter avatar with deterministic palette
    keyed directly off their email address and credentials.
    """
    if photo_url and photo_url != '/static/default-profile.png' and not photo_url.endswith('default-profile.png') and not photo_url.endswith('default-profile.svg'):
        return photo_url
    
    # Extract identifier text from email or name
    display_name = (name or '').strip()
    clean_email = (email or '').strip().lower()
    
    if clean_email:
        seed = clean_email
    elif display_name:
        seed = display_name
    else:
        seed = 'swapskills'
        
    initial = (display_name[:1] or (clean_email[:1] if clean_email else 'S')).upper()
    
    # Deterministic color palette keyed by email hash
    import hashlib
    import urllib.parse
    hash_val = int(hashlib.md5(seed.encode('utf-8')).hexdigest()[:6], 16)
    color_palette = [
        '1a73e8', # Google Blue
        '0f9d58', # Google Green
        'ea4335', # Google Red
        'fbbc04', # Google Yellow
        '673ab7', # Purple
        'e91e63', # Pink
        '0097a7', # Cyan
        'f57c00', # Orange
        '3f51b5'  # Indigo
    ]
    bg_color = color_palette[hash_val % len(color_palette)]
    
    return f"https://ui-avatars.com/api/?name={urllib.parse.quote(initial)}&background={bg_color}&color=fff&size=150&font-size=0.55&bold=true&rounded=true"


# ---------------------- Landing Page --------------
@main.route('/')
def landing():
    """Landing page for non-authenticated users"""
    if session.get('user_id'):
        return redirect(url_for('main.app'))
    return render_template('landing.html')

# ------------------ Home Route (for backward compatibility) ------------------
@main.route('/home')
def home():
    """Redirect to app home for backward compatibility"""
    return redirect(url_for('main.app'))

# ------------------ App Home ------------------
@main.route('/app')
def app():
    """Main app page for authenticated users"""
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('main.login'))
    
    query = request.args.get('q', '').strip().lower()
    page = int(request.args.get('page', 1))
    per_page = 12

    # Get total user count from Firebase
    users_ref = db.collection('users')
    total_users_query = users_ref.where('profileVisibility', '==', 'Public').stream()
    total_users = len(list(total_users_query))

    # Fetch ALL users from Firebase
    users_ref = db.collection('users').stream()
    user_data = []

    for doc in users_ref:
        user = doc.to_dict()
        user_id = doc.id

        # Skip users who are not public
        if user.get('profileVisibility', 'Public') != 'Public':
            continue

        # Get location data
        city = user.get('city', '')
        state = user.get('state', '')
        location = user.get('location', '')
        
        # Create display location
        if city and state:
            display_location = f"{city}, {state}"
        elif city:
            display_location = city
        elif location:
            display_location = location
        else:
            display_location = "Location not specified"

        # Get skills
        offered_skills = [skill.lower() for skill in user.get('offeredSkill', [])]
        requested_skills = [skill.lower() for skill in user.get('requestedSkill', [])]
        
        # Get user name
        user_name = user.get('name', '').lower()
        
        # Enhanced search functionality - ONLY search by name and offered skills
        matches_search = False
        if not query:
            matches_search = True  # Show all if no query
        else:
            # Search in user name
            if query in user_name:
                matches_search = True
            
            # Search in offered skills (EXACT MATCH or CONTAINS)
            for skill in offered_skills:
                if query in skill or query == skill:
                    matches_search = True
                    break
        
        # Only add user if they match the search criteria
        if matches_search:
            u_name = user.get('name', 'Anonymous')
            u_photo = get_avatar_url(user.get('photo_url'), u_name, user.get('email', ''))
            user_data.append({
                'name': u_name,
                'photo_url': u_photo,
                'offeredSkill': user.get('offeredSkill', []),
                'requestedSkill': user.get('requestedSkill', []),
                'rating': generate_random_rating(),
                'user_id': doc.id,
                'city': city,
                'state': state,
                'location': location,
                'display_location': display_location,
                'availability': user.get('availability', '')
            })

    # Sort users by name
    user_data.sort(key=lambda x: x['name'])

    # Get AI recommendations for logged-in users
    ai_recommendations = []
    current_user_id = session.get('user_id')
    is_authenticated = bool(current_user_id)
    
    if current_user_id:
        current_user_doc = db.collection('users').document(current_user_id).get()
        if current_user_doc.exists:
            current_user_data = current_user_doc.to_dict()
            wanted_skills = current_user_data.get('requestedSkill', [])
            
            for skill in wanted_skills:
                if not skill.strip():
                    continue
                    
                skill_users = db.collection('users').where('offeredSkill', 'array_contains', skill.strip()).stream()
                
                for doc in skill_users:
                    user = doc.to_dict()
                    user_id = doc.id
                    
                    if (user.get('profileVisibility', 'Public') != 'Public' or 
                        user_id == current_user_id or
                        any(rec['user_id'] == user_id for rec in ai_recommendations)):
                        continue
                    
                    # Get location for recommendations too
                    city = user.get('city', '')
                    state = user.get('state', '')
                    location = user.get('location', '')
                    
                    if city and state:
                        display_location = f"{city}, {state}"
                    elif city:
                        display_location = city
                    elif location:
                        display_location = location
                    else:
                        display_location = "Location not specified"
                    
                    rec_name = user.get('name', 'Anonymous')
                    ai_recommendations.append({
                        'name': rec_name,
                        'photo_url': get_avatar_url(user.get('photo_url'), rec_name, user.get('email', '')),
                        'offeredSkill': user.get('offeredSkill', []),
                        'requestedSkill': user.get('requestedSkill', []),
                        'rating': generate_random_rating(),
                        'user_id': user_id,
                        'display_location': display_location
                    })
                    
                    if len(ai_recommendations) >= 6:
                        break
                
                if len(ai_recommendations) >= 6:
                    break

    # Pagination
    total_filtered_users = len(user_data)
    total_pages = ceil(total_filtered_users / per_page) if total_filtered_users > 0 else 1
    
    # Ensure page is within valid range
    if page < 1:
        page = 1
    elif page > total_pages and total_pages > 0:
        page = total_pages
    
    start = (page - 1) * per_page
    end = start + per_page
    paginated_users = user_data[start:end]

    return render_template(
        'index.html',
        swaps=paginated_users,
        current_page=page,
        total_pages=total_pages,
        query=query,
        total_users=total_users,
        ai_recommendations=ai_recommendations,
        is_authenticated=is_authenticated,
        search_results_count=total_filtered_users
    )

# ------------------ Enhanced Search API Endpoint ------------------
@main.route('/api/search_users', methods=['GET'])
def api_search_users():
    """API endpoint for searching users across entire database"""
    try:
        query = request.args.get('q', '').strip().lower()
        users_ref = db.collection('users').stream()
        
        search_results = []
        
        for doc in users_ref:
            user = doc.to_dict()
            user_id = doc.id

            if user.get('profileVisibility', 'Public') != 'Public':
                continue

            # Get user name and skills
            user_name = user.get('name', '').lower()
            offered_skills = [skill.lower() for skill in user.get('offeredSkill', [])]
            
            # Check if matches search query
            matches = False
            if not query:
                matches = True
            else:
                # Search in user name
                if query in user_name:
                    matches = True
                
                # Search in offered skills
                if not matches:
                    for skill in offered_skills:
                        if query in skill or query == skill:
                            matches = True
                            break
            
            if matches:
                # Get location
                city = user.get('city', '')
                state = user.get('state', '')
                if city and state:
                    display_location = f"{city}, {state}"
                elif city:
                    display_location = city
                else:
                    display_location = user.get('location', 'Location not specified')
                
                search_results.append({
                    'name': user.get('name', 'Anonymous'),
                    'photo_url': user.get('photo_url', '/static/default-profile.png'),
                    'offeredSkill': user.get('offeredSkill', []),
                    'requestedSkill': user.get('requestedSkill', []),
                    'rating': generate_random_rating(),
                    'user_id': user_id,
                    'display_location': display_location
                })
        
        return jsonify({
            'status': 'success',
            'count': len(search_results),
            'results': search_results[:10]  # Limit to 10 results for performance
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# ------------------ Auth Routes ------------------
@main.route('/login')
def login():
    if session.get('user_id'):
        return redirect(url_for('main.app'))
    return render_template('signin.html')

@main.route('/signup')
def signup():
    if session.get('user_id'):
        return redirect(url_for('main.app'))
    return render_template('signup.html')

@main.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.landing'))

@main.route('/set-session', methods=['POST'])
def set_session():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        email = data.get('email', '')
        
        if not user_id:
            return jsonify({'status': 'error', 'error': 'No user ID provided'}), 400
        
        # Set session
        session['user_id'] = user_id
        session['logged_in'] = True

        # Check if user already exists or needs onboarding
        user_doc_ref = db.collection('users').document(user_id)
        user_doc = user_doc_ref.get()
        needs_onboarding = True

        # Also check by email if uid didn't match directly (e.g. seeded user accounts)
        if not user_doc.exists and email:
            email_matches = list(db.collection('users').where('email', '==', email).stream())
            if email_matches:
                existing_doc = email_matches[0]
                user_doc_ref = db.collection('users').document(existing_doc.id)
                user_doc = user_doc_ref.get()
                session['user_id'] = existing_doc.id

        if not user_doc.exists:
            user_doc_ref.set({
                'id': user_id,
                'email': email,
                'name': email.split('@')[0] if email else 'User',
                'createdAt': datetime.utcnow().isoformat(),
                'profileVisibility': 'Public',
                'photo_url': '/static/default-profile.svg',
                'onboarding_completed': False
            })
        else:
            u_data = user_doc.to_dict()
            needs_onboarding = not u_data.get('onboarding_completed', False)
        
        redirect_url = '/onboarding' if needs_onboarding else '/app'

        return jsonify({
            'status': 'success',
            'message': 'Session set successfully',
            'needs_onboarding': needs_onboarding,
            'redirect_url': redirect_url
        })
        
    except Exception as e:
        print(f"Session error: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@main.route('/onboarding')
def onboarding_page():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('main.login'))
    return render_template('onboarding.html')

@main.route('/api/save-onboarding', methods=['POST'])
def save_onboarding():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    try:
        data = request.get_json() or {}
        data['onboarding_completed'] = True
        db.collection('users').document(user_id).set(data, merge=True)
        return jsonify({'status': 'success', 'message': 'Onboarding saved successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ------------------ Profile Routes ------------------
@main.route('/profile')
def profile():
    """User profile page"""
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('main.login'))
    
    # Get user data from Firestore
    user_doc = db.collection('users').document(user_id).get()
    
    if user_doc.exists:
        user_data = user_doc.to_dict()
        # Initialize new fields if they don't exist
        default_fields = {
            'headline': '',
            'about': '',
            'country': 'India',
            'email': '',
            'phone': '',
            'website': '',
            'languages': [],
            'education': [],
            'experience': [],
            'certifications': [],
            'projects': [],
            'achievements': [],
            'skills': []
        }
        
        # Add any missing default fields
        for field, default_value in default_fields.items():
            if field not in user_data:
                user_data[field] = default_value
                
    else:
        user_data = {
            'headline': '',
            'about': '',
            'country': 'India',
            'email': '',
            'phone': '',
            'website': '',
            'languages': [],
            'education': [],
            'experience': [],
            'certifications': [],
            'projects': [],
            'achievements': [],
            'skills': []
        }
    
    user_data['photo_url'] = get_avatar_url(
        user_data.get('photo_url'),
        user_data.get('name', ''),
        user_data.get('email', '')
    )
    return render_template('profile.html', user_data=user_data)

# NEW ROUTE: Save extended profile data via AJAX
@main.route('/save-extended-profile', methods=['POST'])
def save_extended_profile():
    """Save extended profile data via AJAX"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
        
        data = request.get_json()
        
        # Extract all fields from the request
        update_data = {
            # Personal Info
            'name': data.get('name', ''),
            'headline': data.get('headline', ''),
            'about': data.get('about', ''),
            'city': data.get('city', ''),
            'state': data.get('state', ''),
            'country': data.get('country', 'India'),
            'availability': data.get('availability', 'Flexible'),
            'email': data.get('email', ''),
            'phone': data.get('phone', ''),
            'website': data.get('website', ''),
            'photo_url': data.get('photo_url', ''),
            
            # Social Links
            'linkedin': data.get('linkedin', ''),
            'twitter': data.get('twitter', ''),
            'instagram': data.get('instagram', ''),
            'github': data.get('github', ''),
            
            # Skills
            'offeredSkill': data.get('offeredSkill', []),
            'requestedSkill': data.get('requestedSkill', []),
            
            # New Sections
            'languages': data.get('languages', []),
            'education': data.get('education', []),
            'experience': data.get('experience', []),
            'certifications': data.get('certifications', []),
            'projects': data.get('projects', []),
            'achievements': data.get('achievements', []),
            'skills': data.get('skills', []),
            
            # Gender and Visibility Settings
            'gender': data.get('gender', 'Prefer not to say'),
            'visibility_settings': data.get('visibility_settings', {
                'show_email': True,
                'show_location': True,
                'show_education': True,
                'show_gender': True
            }),
            
            # Timestamp
            'updatedAt': firestore.SERVER_TIMESTAMP
        }
        
        # Update in Firestore
        db.collection('users').document(user_id).set(update_data, merge=True)
        
        return jsonify({
            'status': 'success', 
            'message': 'Profile updated successfully'
        })
        
    except Exception as e:
        print(f"Error saving extended profile: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# NEW ROUTE: Get user data for AJAX requests
@main.route('/api/user-data')
def api_user_data():
    """Get user data for AJAX requests"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
        
        user_doc = db.collection('users').document(user_id).get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            user_data['user_id'] = user_id
            user_data['uid'] = user_id
            user_data['photo_url'] = get_avatar_url(
                user_data.get('photo_url'),
                user_data.get('name', 'User'),
                user_data.get('email', '')
            )
            return jsonify({
                'status': 'success',
                'data': user_data
            })
        else:
            return jsonify({
                'status': 'success',
                'data': {
                    'user_id': user_id,
                    'uid': user_id,
                    'name': 'User',
                    'photo_url': get_avatar_url('', 'User', '')
                }
            })
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Existing route - keep unchanged
@main.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    """Edit user profile - OLD VERSION (keep for backward compatibility)"""
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('main.login'))
    
    if request.method == 'POST':
        # Handle profile update
        name = request.form.get('name')
        offered_skills = request.form.get('offeredSkill', '').split(',')
        requested_skills = request.form.get('requestedSkill', '').split(',')
        location = request.form.get('location', '')
        city = request.form.get('city', '')
        state = request.form.get('state', '')
        availability = request.form.get('availability', '')
        profile_visibility = request.form.get('profileVisibility', 'Public')
        
        # Clean up skills (remove empty strings and strip whitespace)
        offered_skills = [skill.strip() for skill in offered_skills if skill.strip()]
        requested_skills = [skill.strip() for skill in requested_skills if skill.strip()]
        
        update_data = {
            'name': name,
            'offeredSkill': offered_skills,
            'requestedSkill': requested_skills,
            'location': location,
            'city': city,
            'state': state,
            'availability': availability,
            'profileVisibility': profile_visibility,
            'updatedAt': firestore.SERVER_TIMESTAMP
        }
        
        # Update in Firestore
        db.collection('users').document(user_id).update(update_data)
        
        return redirect(url_for('main.profile'))
    
    # GET request - load current user data
    user_doc = db.collection('users').document(user_id).get()
    user_data = user_doc.to_dict() if user_doc.exists else {}
    
    return render_template('edit_profile.html', user_data=user_data)

# ------------------ Helper Functions for Swaps ------------------
def generate_swap_id():
    """Generate unique sequential swap ID"""
    try:
        counter_ref = db.collection('swap_counters').document('swap_counter')
        
        # Get current counter value
        counter = counter_ref.get()
        if counter.exists:
            new_count = counter.get('count', 0) + 1
        else:
            new_count = 1
        
        # Update counter
        counter_ref.set({
            'count': new_count,
            'lastUpdated': firestore.SERVER_TIMESTAMP
        })
        
        return f"SWP{new_count:06d}"
        
    except Exception as e:
        # Fallback to UUID if transaction fails
        print(f"Error generating sequential ID: {str(e)}")
        return f"SWP{uuid.uuid4().hex[:8].upper()}"

def format_swap_timestamp(timestamp):
    """Format Firestore timestamp to human-readable format"""
    if not timestamp:
        return "Recently"
    
    try:
        # Handle Firestore timestamp
        if hasattr(timestamp, 'to_date'):
            dt = timestamp.to_date()
        elif hasattr(timestamp, 'seconds'):
            dt = datetime.fromtimestamp(timestamp.seconds)
        elif isinstance(timestamp, datetime):
            dt = timestamp
        else:
            return "Recently"
        
        # Format: "Dec 4, 2025 at 3:33 AM"
        return dt.strftime('%b %d, %Y at %I:%M %p')
        
    except Exception as e:
        print(f"Error formatting timestamp: {str(e)}")
        return "Recently"

def get_relative_time(dt):
    """Convert datetime to relative time string"""
    from datetime import datetime
    now = datetime.now()
    
    # If dt is a Firestore timestamp, convert to datetime
    if hasattr(dt, 'to_date'):
        dt = dt.to_date()
    
    diff = now - dt
    
    seconds = diff.total_seconds()
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    
    if days > 365:
        years = int(days // 365)
        return f"{years} year{'s' if years > 1 else ''} ago"
    elif days > 30:
        months = int(days // 30)
        return f"{months} month{'s' if months > 1 else ''} ago"
    elif days > 0:
        return f"{int(days)} day{'s' if days > 1 else ''} ago"
    elif hours > 0:
        return f"{int(hours)} hour{'s' if hours > 1 else ''} ago"
    elif minutes > 0:
        return f"{int(minutes)} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "just now"

# ------------------ Swap Routes ------------------
@main.route('/request_swap/<target_user_id>', methods=['GET', 'POST'])
def request_swap(target_user_id):
    """Request a skill swap with another user"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return redirect(url_for('main.login'))

    try:
        current_user_doc = db.collection('users').document(current_user_id).get()
        current_user_data = current_user_doc.to_dict() if current_user_doc.exists else {}

        target_user_doc = db.collection('users').document(target_user_id).get()
        target_user_data = target_user_doc.to_dict() if target_user_doc.exists else {}

        if not target_user_data:
            return jsonify({'status': 'error', 'message': 'User not found'}), 404

        if request.method == 'POST':
            # Get form data
            if request.is_json:
                data = request.get_json()
                your_skill = data.get('your_skill', '')
                their_skill = data.get('their_skill', '')
                message = data.get('message', '')
            else:
                your_skill = request.form.get('your_skill', '')
                their_skill = request.form.get('their_skill', '')
                message = request.form.get('message', '')
            
            if not your_skill or not their_skill:
                if request.is_json:
                    return jsonify({'status': 'error', 'message': 'Please select both skills'}), 400
                return redirect(url_for('main.request_swap', target_user_id=target_user_id))

            # Generate swap ID
            swap_id = generate_swap_id()
            
            # Create swap document
            swap_data = {
                'swapId': swap_id,
                'fromUserId': current_user_id,
                'toUserId': target_user_id,
                'offeredSkill': your_skill,
                'requestedSkill': their_skill,
                'message': message,
                'status': 'pending',
                'createdAt': firestore.SERVER_TIMESTAMP,
                'updatedAt': firestore.SERVER_TIMESTAMP,
                'metadata': {
                    'fromUserName': current_user_data.get('name', 'Unknown'),
                    'fromUserPhoto': get_avatar_url(current_user_data.get('photo_url'), current_user_data.get('name', 'Unknown'), current_user_data.get('email', '')),
                    'toUserName': target_user_data.get('name', 'Unknown'),
                    'toUserPhoto': get_avatar_url(target_user_data.get('photo_url'), target_user_data.get('name', 'Unknown'), target_user_data.get('email', ''))
                }
            }
            
            # Create swap document
            swap_ref = db.collection('swaps').document()
            swap_ref.set(swap_data)
            
            # Update denormalized user_swaps collections
            # For sender
            sent_ref = db.collection('user_swaps').document(f"{current_user_id}_sent")
            sent_doc = sent_ref.get()
            
            if sent_doc.exists:
                sent_ref.update({
                    'swaps': firestore.ArrayUnion([swap_id]),
                    'updatedAt': firestore.SERVER_TIMESTAMP
                })
            else:
                sent_ref.set({
                    'userId': current_user_id,
                    'type': 'sent',
                    'swaps': [swap_id],
                    'createdAt': firestore.SERVER_TIMESTAMP,
                    'updatedAt': firestore.SERVER_TIMESTAMP
                })
            
            # For receiver
            received_ref = db.collection('user_swaps').document(f"{target_user_id}_received")
            received_doc = received_ref.get()
            
            if received_doc.exists:
                received_ref.update({
                    'swaps': firestore.ArrayUnion([swap_id]),
                    'updatedAt': firestore.SERVER_TIMESTAMP
                })
            else:
                received_ref.set({
                    'userId': target_user_id,
                    'type': 'received',
                    'swaps': [swap_id],
                    'createdAt': firestore.SERVER_TIMESTAMP,
                    'updatedAt': firestore.SERVER_TIMESTAMP
                })
            
            # Update user stats
            # Update sender stats
            sender_ref = db.collection('users').document(current_user_id)
            sender_ref.update({
                'swapCount': firestore.Increment(1),
                'updatedAt': firestore.SERVER_TIMESTAMP
            })
            
            # Update receiver stats
            receiver_ref = db.collection('users').document(target_user_id)
            receiver_ref.update({
                'pendingSwapCount': firestore.Increment(1),
                'updatedAt': firestore.SERVER_TIMESTAMP
            })
            
            if request.is_json:
                return jsonify({
                    'status': 'success',
                    'message': 'Swap request sent successfully!',
                    'swapId': swap_id
                })
            
            return redirect(url_for('main.see_request', view='my_requests'))

        # GET request - render form
        current_user_data['photo_url'] = get_avatar_url(
            current_user_data.get('photo_url'),
            current_user_data.get('name', 'User'),
            current_user_data.get('email', '')
        )
        target_user_data['photo_url'] = get_avatar_url(
            target_user_data.get('photo_url'),
            target_user_data.get('name', 'User'),
            target_user_data.get('email', '')
        )

        return render_template(
            'swap_request.html',
            current_user_skills=current_user_data.get('offeredSkill', []),
            target_user_requested_skills=target_user_data.get('requestedSkill', []),
            target_user_id=target_user_id,
            target_user_name=target_user_data.get('name', 'User'),
            target_user_data=target_user_data,
            current_user_data=current_user_data
        )

    except Exception as e:
        print(f"Error in swap request: {str(e)}")
        if request.is_json:
            return jsonify({'status': 'error', 'message': str(e)}), 500
        return redirect(url_for('main.app'))

@main.route('/swap/<user_id>', endpoint='view_swap_profile')
@main.route('/swap-profile/<user_id>', endpoint='swap_profile')
def view_swap_profile(user_id):
    """View another user's profile for swapping"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return redirect(url_for('main.login'))

    if user_id == current_user_id:
        return redirect(url_for('main.profile'))

    # Get current user data
    current_user_doc = db.collection('users').document(current_user_id).get()
    current_user_data = current_user_doc.to_dict() if current_user_doc.exists else {}

    # Get target user data
    target_user_doc = db.collection('users').document(user_id).get()
    user_data = target_user_doc.to_dict() if target_user_doc.exists else None

    if not user_data:
        return "<h2>User not found</h2>", 404

    # Initialize new fields for swap profile view
    default_fields = {
        'headline': '',
        'about': '',
        'education': [],
        'experience': [],
        'certifications': [],
        'projects': [],
        'achievements': [],
        'skills': [],
        'languages': []
    }
    
    for field, default_value in default_fields.items():
        if field not in user_data:
            user_data[field] = default_value

    return render_template(
        "swap_profile.html",
        user_data=user_data,
        target_user_id=user_id,
        current_user_data=current_user_data
    )

# ------------------ Swap Requests Management ------------------
@main.route('/see-request', methods=['GET'])
def see_request():
    """View swap requests - FIXED VERSION"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return redirect(url_for('main.login'))

    try:
        # Get current user data
        current_user_doc = db.collection('users').document(current_user_id).get()
        current_user_data = current_user_doc.to_dict() if current_user_doc.exists else {
            'name': 'User',
            'photo_url': '/static/default-profile.png'
        }
        current_user_data['photo_url'] = get_avatar_url(
            current_user_data.get('photo_url'),
            current_user_data.get('name', 'User'),
            current_user_data.get('email', '')
        )

        # Get view type and filters
        view_type = request.args.get('view', 'invitations')
        status_filter = request.args.get('status', 'all')
        search_query = request.args.get('q', '').lower()
        
        # Initialize empty results
        swap_requests = []
        
        # Determine query based on view type
        if view_type == 'invitations':
            # Get swaps where current user is receiver
            query = db.collection('swaps').where('toUserId', '==', current_user_id)
        else:
            # Get swaps where current user is sender
            query = db.collection('swaps').where('fromUserId', '==', current_user_id)
        
        # Execute query
        swaps_docs = query.stream()
        
        # Process each swap
        for doc in swaps_docs:
            swap_data = doc.to_dict()
            swap_data['firestore_id'] = doc.id
            
            # Apply status filter
            if status_filter != 'all' and swap_data.get('status', '').lower() != status_filter:
                continue
            
            # Determine which user info to show based on view
            if view_type == 'invitations':
                # For invitations: show sender's info (who sent the request)
                other_user_id = swap_data.get('fromUserId')
                user_name = swap_data.get('metadata', {}).get('fromUserName', 'Unknown')
                user_photo = swap_data.get('metadata', {}).get('fromUserPhoto', '/static/default-profile.png')
            else:
                # For my_requests: show receiver's info (who received the request)
                other_user_id = swap_data.get('toUserId')
                user_name = swap_data.get('metadata', {}).get('toUserName', 'Unknown')
                user_photo = swap_data.get('metadata', {}).get('toUserPhoto', '/static/default-profile.png')
            
            # Format timestamp
            created_at = swap_data.get('createdAt')
            created_at_formatted = format_swap_timestamp(created_at)
            
            # Get user data for additional info
            other_user_doc = db.collection('users').document(other_user_id).get()
            other_user_data = other_user_doc.to_dict() if other_user_doc.exists else {}
            
            # Prepare request data for template
            request_data = {
                'id': swap_data.get('swapId', doc.id),
                'firestore_id': doc.id,
                'swapId': swap_data.get('swapId', f"SWP{doc.id[:8].upper()}"),
                'userId': other_user_id,
                'userName': user_name,
                'userPhoto': user_photo,
                'offeredSkill': swap_data.get('offeredSkill', 'Not specified'),
                'requestedSkill': swap_data.get('requestedSkill', 'Not specified'),
                'message': swap_data.get('message', ''),
                'status': swap_data.get('status', 'pending').capitalize(),
                'createdAt_formatted': created_at_formatted,
                'rating': generate_random_rating(),
                'display_location': other_user_data.get('location', ''),
                'city': other_user_data.get('city', ''),
                'state': other_user_data.get('state', '')
            }
            
            # Apply search filter
            if search_query:
                searchable_fields = [
                    request_data['userName'].lower(),
                    request_data['offeredSkill'].lower(),
                    request_data['requestedSkill'].lower(),
                    request_data['swapId'].lower()
                ]
                if not any(search_query in field for field in searchable_fields):
                    continue
            
            swap_requests.append(request_data)
        
        # Sort by creation date (newest first)
        swap_requests.sort(key=lambda x: parse_timestamp_for_sort(x.get('createdAt_formatted', '')), reverse=True)
        
        # Calculate statistics
        stats = {
            'total': len(swap_requests),
            'pending': len([r for r in swap_requests if r['status'].lower() == 'pending']),
            'accepted': len([r for r in swap_requests if r['status'].lower() == 'accepted']),
            'completed': len([r for r in swap_requests if r['status'].lower() == 'completed']),
            'rejected': len([r for r in swap_requests if r['status'].lower() == 'rejected'])
        }
        
        return render_template(
            'seeRequest.html',
            swap_requests=swap_requests,
            selected_status=status_filter,
            current_user_data=current_user_data,
            view_type=view_type,
            stats=stats,
            search_query=search_query
        )
        
    except Exception as e:
        print(f"Error in see_request: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return empty but functional page
        return render_template(
            'seeRequest.html',
            swap_requests=[],
            selected_status='all',
            current_user_data={'name': 'User', 'photo_url': '/static/default-profile.png'},
            view_type=view_type if 'view_type' in locals() else 'invitations',
            stats={'total': 0, 'pending': 0, 'accepted': 0, 'completed': 0, 'rejected': 0}
        )

def parse_timestamp_for_sort(timestamp_str):
    """Parse timestamp string for sorting"""
    try:
        # Try to parse the formatted string
        return datetime.strptime(timestamp_str, '%b %d, %Y at %I:%M %p')
    except:
        return datetime.min

# ------------------ Update Status Route (FIXED) ------------------
@main.route('/update-status/<swap_id>', methods=['POST'])
def update_status(swap_id):
    """Update swap status - FIXED VERSION"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    try:
        action = request.form.get('action', '').lower()
        
        # Find swap by swapId
        swap_ref = None
        swap_data = None
        
        # First try to find by custom swapId
        swap_query = db.collection('swaps').where('swapId', '==', swap_id).limit(1).stream()
        for doc in swap_query:
            swap_ref = doc.reference
            swap_data = doc.to_dict()
            break
        
        # If not found, try as firestore document ID
        if not swap_ref:
            try:
                swap_ref = db.collection('swaps').document(swap_id)
                swap_doc = swap_ref.get()
                if swap_doc.exists:
                    swap_data = swap_doc.to_dict()
                else:
                    return jsonify({'status': 'error', 'message': 'Swap not found'}), 404
            except:
                return jsonify({'status': 'error', 'message': 'Swap not found'}), 404
        
        if not swap_data:
            return jsonify({'status': 'error', 'message': 'Swap not found'}), 404
        
        # Verify permissions
        is_receiver = swap_data.get('toUserId') == current_user_id
        is_sender = swap_data.get('fromUserId') == current_user_id
        
        # Define allowed actions
        allowed_actions = {
            'accepted': is_receiver and swap_data.get('status') == 'pending',
            'rejected': is_receiver and swap_data.get('status') == 'pending',
            'completed': (is_sender or is_receiver) and swap_data.get('status') == 'accepted',
            'cancelled': is_sender and swap_data.get('status') == 'pending'
        }
        
        if not allowed_actions.get(action, False):
            return jsonify({'status': 'error', 'message': 'Not authorized for this action'}), 403
        
        # Update the swap
        update_data = {
            'status': action,
            'updatedAt': firestore.SERVER_TIMESTAMP
        }
        
        swap_ref.update(update_data)
        
        # Update user stats if needed
        if action == 'accepted':
            # Decrease pending count for receiver
            receiver_ref = db.collection('users').document(swap_data['toUserId'])
            receiver_ref.update({
                'pendingSwapCount': firestore.Increment(-1),
                'activeSwapCount': firestore.Increment(1),
                'updatedAt': firestore.SERVER_TIMESTAMP
            })
        elif action == 'completed':
            # Increase completed count for both users
            from_user_ref = db.collection('users').document(swap_data['fromUserId'])
            to_user_ref = db.collection('users').document(swap_data['toUserId'])
            
            from_user_ref.update({
                'completedSwapCount': firestore.Increment(1),
                'activeSwapCount': firestore.Increment(-1),
                'updatedAt': firestore.SERVER_TIMESTAMP
            })
            
            to_user_ref.update({
                'completedSwapCount': firestore.Increment(1),
                'activeSwapCount': firestore.Increment(-1),
                'updatedAt': firestore.SERVER_TIMESTAMP
            })
        
        return jsonify({
            'status': 'success', 
            'message': f'Swap {action} successfully',
            'redirect': url_for('main.see_request')
        })
        
    except Exception as e:
        print(f"Error updating swap: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ------------------ API Endpoints ------------------
@main.route('/api/debug/swaps')
def debug_swaps():
    """Debug endpoint to check swap data"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        # Get all swaps for this user (sent and received)
        sent_swaps = db.collection('swaps').where('fromUserId', '==', current_user_id).stream()
        received_swaps = db.collection('swaps').where('toUserId', '==', current_user_id).stream()
        
        swaps_data = []
        
        # Process sent swaps
        for doc in sent_swaps:
            data = doc.to_dict()
            data['id'] = doc.id
            data['type'] = 'sent'
            swaps_data.append(data)
        
        # Process received swaps
        for doc in received_swaps:
            data = doc.to_dict()
            data['id'] = doc.id
            data['type'] = 'received'
            swaps_data.append(data)
        
        return jsonify({
            'user_id': current_user_id,
            'total_swaps': len(swaps_data),
            'swaps': swaps_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/api/swaps/<swap_id>', methods=['GET'])
def get_swap_details(swap_id):
    """Get detailed swap information"""
    try:
        swap_data = None
        doc_id = None
        
        # 1. Query by custom swapId
        swap_query = db.collection('swaps').where('swapId', '==', swap_id).limit(1).stream()
        for doc in swap_query:
            swap_data = doc.to_dict()
            doc_id = doc.id
            break

        # 2. Fallback to direct document id lookup
        if not swap_data:
            doc_ref = db.collection('swaps').document(swap_id)
            doc_snap = doc_ref.get()
            if doc_snap.exists:
                swap_data = doc_snap.to_dict()
                doc_id = doc_snap.id

        if swap_data:
            swap_data['id'] = doc_id
            from_uid = swap_data.get('fromUserId')
            to_uid = swap_data.get('toUserId')
            from_user = db.collection('users').document(from_uid).get() if from_uid else None
            to_user = db.collection('users').document(to_uid).get() if to_uid else None

            swap_data['fromUser'] = from_user.to_dict() if (from_user and from_user.exists) else {}
            swap_data['toUser'] = to_user.to_dict() if (to_user and to_user.exists) else {}

            return jsonify({'status': 'success', 'data': swap_data})

        return jsonify({'status': 'error', 'message': 'Swap not found'}), 404

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ------------------ Enhanced Search ------------------
@main.route('/api/enhanced-search', methods=['GET'])
def enhanced_search():
    """Enhanced search across all user fields"""
    try:
        query = request.args.get('q', '').strip().lower()
        users_ref = db.collection('users').stream()
        
        search_results = []
        
        for doc in users_ref:
            user = doc.to_dict()
            user_id = doc.id

            if user.get('profileVisibility', 'Public') != 'Public':
                continue

            # Search across multiple fields
            search_fields = [
                user.get('name', '').lower(),
                user.get('headline', '').lower(),
                user.get('about', '').lower(),
                ' '.join(user.get('offeredSkill', [])).lower(),
                ' '.join(user.get('requestedSkill', [])).lower(),
            ]
            
            # Check if query exists in any search field
            matches = False
            if not query:
                matches = True
            else:
                for field in search_fields:
                    if query in field:
                        matches = True
                        break
            
            if matches:
                # Get location
                city = user.get('city', '')
                state = user.get('state', '')
                if city and state:
                    display_location = f"{city}, {state}"
                elif city:
                    display_location = city
                else:
                    display_location = user.get('location', 'Location not specified')
                
                result = {
                    'name': user.get('name', 'Anonymous'),
                    'headline': user.get('headline', ''),
                    'photo_url': user.get('photo_url', '/static/default-profile.png'),
                    'offeredSkill': user.get('offeredSkill', []),
                    'requestedSkill': user.get('requestedSkill', []),
                    'rating': generate_random_rating(),
                    'user_id': user_id,
                    'display_location': display_location
                }
                
                search_results.append(result)
        
        return jsonify({
            'status': 'success',
            'count': len(search_results),
            'results': search_results[:20]  # Limit to 20 results
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# ------------------ Indian Colleges API ------------------
@main.route('/api/indian-colleges', methods=['GET'])
def get_indian_colleges():
    """API endpoint to fetch Indian colleges"""
    try:
        query = request.args.get('q', '').strip().lower()
        
        # Sample list of Indian colleges
        indian_colleges = [
            "Indian Institute of Technology Bombay",
            "Indian Institute of Technology Delhi",
            "Indian Institute of Technology Madras",
            "Indian Institute of Technology Kanpur",
            "Indian Institute of Technology Kharagpur",
            "Indian Institute of Technology Roorkee",
            "University of Delhi",
            "University of Mumbai",
            "University of Calcutta",
            "University of Madras",
            "Anna University",
            "Jawaharlal Nehru University",
            "Banaras Hindu University",
            "University of Hyderabad",
            "University of Pune",
            "National Institute of Technology Trichy",
            "Birla Institute of Technology and Science",
            "Indian Institute of Science",
            "All India Institute of Medical Sciences",
            "Indian Statistical Institute",
            "Indian Institute of Management Ahmedabad",
            "Indian Institute of Management Bangalore",
            "Indian Institute of Management Calcutta",
            "Indian Institute of Management Lucknow",
            "Indian Institute of Management Kozhikode",
            "Indian Institute of Management Indore",
            "Delhi Technological University",
            "Netaji Subhas University of Technology",
            "Jadavpur University",
            "University of Rajasthan",
            "University of Mysore",
            "University of Kerala",
            "University of Jammu",
            "University of Kashmir",
            "Guru Nanak Dev University",
            "Panjab University",
            "University of Calcutta",
            "University of Madras",
            "University of Mumbai",
            "University of Delhi"
        ]
        
        if query:
            filtered_colleges = [college for college in indian_colleges 
                               if query in college.lower()]
        else:
            filtered_colleges = indian_colleges[:20]
        
        return jsonify({
            'status': 'success',
            'colleges': filtered_colleges[:20]
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# ------------------ Save Profile ------------------
@main.route('/save-profile', methods=['POST'])
def save_profile():
    """Save profile data including enhanced project links"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
        
        data = request.get_json()
        
        # Process project links if they exist
        if 'projects' in data:
            for project in data['projects']:
                # Ensure links are properly formatted
                if 'links' in project:
                    # Filter out empty links
                    project['links'] = [link for link in project['links'] 
                                      if link.get('name') and link.get('url')]
        
        # Update in Firestore
        db.collection('users').document(user_id).set(data, merge=True)
        
        return jsonify({
            'status': 'success', 
            'message': 'Profile updated successfully'
        })
        
    except Exception as e:
        print(f"Error saving profile: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# User Profile Redirect 
@main.route('/user/<user_id>')
def view_user_profile(user_id):
    """Redirect to user profile page"""
    return redirect(url_for('main.view_swap_profile', user_id=user_id))

# ------------------ Message Routes ------------------
@main.route('/messages')
def messages():
    """Messages inbox page"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return redirect(url_for('main.login'))
    
    # Get current user data
    current_user_doc = db.collection('users').document(current_user_id).get()
    current_user_data = current_user_doc.to_dict() if current_user_doc.exists else {
        'name': 'User',
        'photo_url': '/static/default-profile.png'
    }
    current_user_data['photo_url'] = get_avatar_url(
        current_user_data.get('photo_url'),
        current_user_data.get('name', 'User'),
        current_user_data.get('email', '')
    )
    
    return render_template(
        'messages.html',
        current_user_data=current_user_data,
        current_user_id=current_user_id
    )

@main.route('/chat/<user_id>')
def chat(user_id):
    """Individual chat page"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return redirect(url_for('main.login'))
    
    # Get current user data
    current_user_doc = db.collection('users').document(current_user_id).get()
    current_user_data = current_user_doc.to_dict() if current_user_doc.exists else {
        'name': 'User',
        'photo_url': '/static/default-profile.png'
    }
    current_user_data['photo_url'] = get_avatar_url(
        current_user_data.get('photo_url'),
        current_user_data.get('name', 'User'),
        current_user_data.get('email', '')
    )
    
    # Get target user data
    target_user_doc = db.collection('users').document(user_id).get()
    target_user_data = target_user_doc.to_dict() if target_user_doc.exists else None
    
    if not target_user_data:
        return "<h2>User not found</h2>", 404
    
    return render_template(
        'chat.html',
        current_user_data=current_user_data,
        target_user_data=target_user_data,
        target_user_id=user_id,
        current_user_id=current_user_id
    )

@main.route('/api/conversations')
def api_conversations_v2():
    """Get all conversations for current user"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    try:
        # Get distinct conversations by querying messages
        sent_messages_ref = db.collection('messages').where('senderId', '==', current_user_id)
        received_messages_ref = db.collection('messages').where('receiverId', '==', current_user_id)
        
        sent_messages = sent_messages_ref.stream()
        received_messages = received_messages_ref.stream()
        
        # Dictionary to store conversations with other users
        conversations = {}
        
        # Process sent messages
        for msg in sent_messages:
            msg_data = msg.to_dict()
            receiver_id = msg_data.get('receiverId')
            
            if not receiver_id or receiver_id == current_user_id:
                continue
            
            # Get receiver info if not already fetched
            if receiver_id not in conversations:
                receiver_doc = db.collection('users').document(receiver_id).get()
                if receiver_doc.exists:
                    receiver_data = receiver_doc.to_dict()
                    
                    # Count unread messages
                    unread_query = db.collection('messages').where('senderId', '==', receiver_id)\
                                             .where('receiverId', '==', current_user_id)\
                                             .where('read', '==', False)\
                                             .stream()
                    unread_count = len(list(unread_query))
                    
                    rec_name = receiver_data.get('name', 'Unknown')
                    rec_email = receiver_data.get('email', '')
                    rec_photo = get_avatar_url(receiver_data.get('photo_url'), rec_name, rec_email)

                    conversations[receiver_id] = {
                        'user_id': receiver_id,
                        'user_name': rec_name,
                        'user_photo': rec_photo,
                        'last_message': msg_data.get('content', ''),
                        'timestamp': msg_data.get('timestamp'),
                        'is_sent_by_me': True,
                        'unread_count': unread_count
                    }
            else:
                # Update if this message is newer
                conv = conversations[receiver_id]
                msg_time = msg_data.get('timestamp')
                conv_time = conv.get('timestamp')
                
                if msg_time and conv_time:
                    if hasattr(msg_time, 'seconds') and hasattr(conv_time, 'seconds'):
                        if msg_time.seconds > conv_time.seconds:
                            conv['last_message'] = msg_data.get('content', '')
                            conv['timestamp'] = msg_time
                            conv['is_sent_by_me'] = True
        
        # Process received messages
        for msg in received_messages:
            msg_data = msg.to_dict()
            sender_id = msg_data.get('senderId')
            
            if not sender_id or sender_id == current_user_id:
                continue
            
            # Get sender info if not already fetched
            if sender_id not in conversations:
                sender_doc = db.collection('users').document(sender_id).get()
                if sender_doc.exists:
                    sender_data = sender_doc.to_dict()
                    
                    # Count unread messages for this conversation
                    unread_query = db.collection('messages').where('senderId', '==', sender_id)\
                                             .where('receiverId', '==', current_user_id)\
                                             .where('read', '==', False)\
                                             .stream()
                    unread_count = len(list(unread_query))
                    
                    send_name = sender_data.get('name', 'Unknown')
                    send_email = sender_data.get('email', '')
                    send_photo = get_avatar_url(sender_data.get('photo_url'), send_name, send_email)

                    conversations[sender_id] = {
                        'user_id': sender_id,
                        'user_name': send_name,
                        'user_photo': send_photo,
                        'last_message': msg_data.get('content', ''),
                        'timestamp': msg_data.get('timestamp'),
                        'is_sent_by_me': False,
                        'unread_count': unread_count
                    }
            else:
                # Update if this message is newer
                conv = conversations[sender_id]
                msg_time = msg_data.get('timestamp')
                conv_time = conv.get('timestamp')
                
                if msg_time and conv_time:
                    if hasattr(msg_time, 'seconds') and hasattr(conv_time, 'seconds'):
                        if msg_time.seconds > conv_time.seconds:
                            conv['last_message'] = msg_data.get('content', '')
                            conv['timestamp'] = msg_time
                            conv['is_sent_by_me'] = False
        
        # Convert to list and sort by timestamp
        conversations_list = list(conversations.values())
        
        # Format timestamps and sort
        for conv in conversations_list:
            timestamp = conv.get('timestamp')
            if timestamp:
                if hasattr(timestamp, 'to_date'):
                    dt = timestamp.to_date()
                elif hasattr(timestamp, 'seconds'):
                    dt = datetime.fromtimestamp(timestamp.seconds)
                else:
                    dt = datetime.now()
                
                # Store datetime for sorting
                conv['raw_timestamp'] = dt
                
                # Format for display
                now = datetime.now()
                time_diff = now - dt
                
                if time_diff.days == 0:
                    conv['timestamp_formatted'] = dt.strftime('%I:%M %p')
                elif time_diff.days == 1:
                    conv['timestamp_formatted'] = 'Yesterday'
                elif time_diff.days < 7:
                    conv['timestamp_formatted'] = dt.strftime('%A')
                else:
                    conv['timestamp_formatted'] = dt.strftime('%b %d')
            else:
                conv['raw_timestamp'] = datetime.now()
                conv['timestamp_formatted'] = 'Recently'
            
            # Truncate last message
            last_message = conv['last_message']
            if len(last_message) > 40:
                conv['last_message'] = last_message[:37] + '...'
        
        # Sort by timestamp (newest first)
        conversations_list.sort(key=lambda x: x.get('raw_timestamp', datetime.now()), reverse=True)
        
        return jsonify({
            'status': 'success',
            'conversations': conversations_list
        })
        
    except Exception as e:
        print(f"Error fetching conversations: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/api/messages/<user_id>')
def api_messages_v2(user_id):
    """Get messages between current user and target user"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    try:
        # Get messages where current user is sender and target is receiver OR vice versa
        messages_query = db.collection('messages')\
            .where('senderId', 'in', [current_user_id, user_id])\
            .where('receiverId', 'in', [current_user_id, user_id])\
            .order_by('timestamp', direction=firestore.Query.ASCENDING)\
            .stream()
        
        messages = []
        for doc in messages_query:
            message_data = doc.to_dict()
            message_data['id'] = doc.id
            
            # Convert timestamp for frontend
            timestamp = message_data.get('timestamp')
            if timestamp:
                if hasattr(timestamp, 'to_date'):
                    dt = timestamp.to_date()
                elif hasattr(timestamp, 'seconds'):
                    dt = datetime.fromtimestamp(timestamp.seconds)
                else:
                    dt = datetime.now()
                
                message_data['timestamp'] = dt.isoformat()
                message_data['time_formatted'] = dt.strftime('%I:%M %p')
                message_data['date_formatted'] = dt.strftime('%b %d, %Y')
                message_data['datetime'] = dt
            
            messages.append(message_data)
        
        # Mark messages as read
        unread_query = db.collection('messages')\
            .where('senderId', '==', user_id)\
            .where('receiverId', '==', current_user_id)\
            .where('read', '==', False)\
            .stream()
        
        batch = db.batch()
        for doc in unread_query:
            doc_ref = db.collection('messages').document(doc.id)
            batch.update(doc_ref, {
                'read': True,
                'readAt': firestore.SERVER_TIMESTAMP
            })
        
        if batch._write_pbs:  # Only commit if there are updates
            batch.commit()
        
        # Get user info
        user_doc = db.collection('users').document(user_id).get()
        user_data = user_doc.to_dict() if user_doc.exists else {}
        u_name = user_data.get('name', 'Unknown')
        u_email = user_data.get('email', '')
        u_photo = get_avatar_url(user_data.get('photo_url'), u_name, u_email)
        
        return jsonify({
            'status': 'success',
            'messages': messages,
            'user_info': {
                'name': u_name,
                'photo_url': u_photo,
                'user_id': user_id
            }
        })
        
    except Exception as e:
        print(f"Error fetching messages: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/api/send-message', methods=['POST'])
def api_send_message_v2():
    """Send a new message"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        receiver_id = data.get('receiverId')
        content = data.get('content', '').strip()
        
        if not receiver_id:
            return jsonify({'status': 'error', 'message': 'Receiver ID is required'}), 400
        
        if not content:
            return jsonify({'status': 'error', 'message': 'Message content is required'}), 400
        
        # Get sender info
        sender_doc = db.collection('users').document(current_user_id).get()
        sender_data = sender_doc.to_dict() if sender_doc.exists else {}
        
        # Get receiver info
        receiver_doc = db.collection('users').document(receiver_id).get()
        receiver_data = receiver_doc.to_dict() if receiver_doc.exists else {}
        
        # Create message document
        message_data = {
            'senderId': current_user_id,
            'receiverId': receiver_id,
            'content': content,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'read': False,
            'type': 'text',
            'senderName': sender_data.get('name', 'Unknown'),
            'receiverName': receiver_data.get('name', 'Unknown')
        }
        
        # Add to Firestore
        message_ref = db.collection('messages').document()
        message_ref.set(message_data)
        
        # Format timestamp for response
        timestamp = datetime.now()
        
        return jsonify({
            'status': 'success',
            'message': 'Message sent successfully',
            'messageId': message_ref.id,
            'senderName': sender_data.get('name', 'You'),
            'timestamp': timestamp.isoformat(),
            'time_formatted': timestamp.strftime('%I:%M %p')
        })
        
    except Exception as e:
        print(f"Error sending message: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/api/mark-read/<message_id>', methods=['POST'])
def api_mark_read(message_id):
    """Mark a message as read"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    try:
        message_ref = db.collection('messages').document(message_id)
        message_doc = message_ref.get()
        
        if not message_doc.exists:
            return jsonify({'status': 'error', 'message': 'Message not found'}), 404
        
        message_data = message_doc.to_dict()
        
        # Only mark as read if current user is the receiver
        if message_data.get('receiverId') == current_user_id:
            message_ref.update({
                'read': True,
                'readAt': firestore.SERVER_TIMESTAMP
            })
        
        return jsonify({'status': 'success', 'message': 'Message marked as read'})
        
    except Exception as e:
        print(f"Error marking message as read: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/api/delete-message/<message_id>', methods=['DELETE'])
def api_delete_message(message_id):
    """Delete a message"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    try:
        message_ref = db.collection('messages').document(message_id)
        message_doc = message_ref.get()
        
        if not message_doc.exists:
            return jsonify({'status': 'error', 'message': 'Message not found'}), 404
        
        message_data = message_doc.to_dict()
        
        # Only allow deletion if current user is the sender
        if message_data.get('senderId') != current_user_id:
            return jsonify({'status': 'error', 'message': 'Unauthorized to delete this message'}), 403
        
        # Delete the message
        message_ref.delete()
        
        return jsonify({'status': 'success', 'message': 'Message deleted successfully'})
        
    except Exception as e:
        print(f"Error deleting message: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/api/search-users', methods=['GET'])
def api_search_users_for_messages_v2():
    """Search users for starting new conversations"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    try:
        query = request.args.get('q', '').strip().lower()
        
        # Get all users
        users_ref = db.collection('users')
        all_users = users_ref.stream()
        
        search_results = []
        
        for doc in all_users:
            user = doc.to_dict()
            user_id = doc.id
            
            # Skip current user
            if user_id == current_user_id:
                continue
            
            # Skip private profiles
            if user.get('profileVisibility', 'Public') != 'Public':
                continue
            
            # Get user data for search
            user_name = user.get('name', '').lower()
            user_headline = user.get('headline', '').lower()
            offered_skills = [skill.lower() for skill in user.get('offeredSkill', [])]
            requested_skills = [skill.lower() for skill in user.get('requestedSkill', [])]
            
            # Check if matches search query
            matches = False
            if not query:
                matches = True  # Show all users if no query
            else:
                # Search in name
                if query in user_name:
                    matches = True
                # Search in headline
                elif query in user_headline:
                    matches = True
                # Search in skills
                elif any(query in skill for skill in offered_skills):
                    matches = True
                elif any(query in skill for skill in requested_skills):
                    matches = True
            
            if matches:
                # Get location
                city = user.get('city', '')
                state = user.get('state', '')
                location = ''
                if city and state:
                    location = f"{city}, {state}"
                elif city:
                    location = city
                elif state:
                    location = state
                
                search_results.append({
                    'user_id': user_id,
                    'name': user.get('name', 'Anonymous'),
                    'headline': user.get('headline', ''),
                    'photo_url': user.get('photo_url', '/static/default-profile.png'),
                    'location': location,
                    'offeredSkills': user.get('offeredSkill', [])[:3],
                    'requestedSkills': user.get('requestedSkill', [])[:3]
                })
        
        # Sort by name
        search_results.sort(key=lambda x: x['name'].lower())
        
        return jsonify({
            'status': 'success',
            'count': len(search_results),
            'results': search_results[:50]
        })
        
    except Exception as e:
        print(f"Error searching users: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/api/clear-chat/<user_id>', methods=['POST'])
def api_clear_chat(user_id):
    """Clear chat history with a user"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    try:
        # Delete all messages between current user and target user
        messages_query = db.collection('messages')\
            .where('senderId', 'in', [current_user_id, user_id])\
            .where('receiverId', 'in', [current_user_id, user_id])\
            .stream()
        
        batch = db.batch()
        message_count = 0
        
        for doc in messages_query:
            batch.delete(doc.reference)
            message_count += 1
            
            # Firestore batch limit is 500 operations
            if message_count >= 450:
                batch.commit()
                batch = db.batch()
                message_count = 0
        
        if message_count > 0:
            batch.commit()
        
        return jsonify({
            'status': 'success', 
            'message': f'Chat cleared successfully. Deleted {message_count} messages.'
        })
        
    except Exception as e:
        print(f"Error clearing chat: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ------------------ Get Unread Count ------------------
@main.route('/api/unread-count')
def api_unread_count():
    """Get total unread message count"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    try:
        unread_query = db.collection('messages')\
            .where('receiverId', '==', current_user_id)\
            .where('read', '==', False)\
            .stream()
        
        count = len(list(unread_query))
        
        return jsonify({
            'status': 'success',
            'count': count
        })
        
    except Exception as e:
        print(f"Error getting unread count: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500



# new 
# ------------------ Message Routes - FIXED VERSION ------------------

@main.route('/api/conversations')
def api_conversations():
    """Get all conversations for current user - FIXED VERSION"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    try:
        # Get all messages where current user is either sender or receiver
        messages_ref = db.collection('messages')
        
        # Get messages where user is sender
        sent_messages = messages_ref.where('senderId', '==', current_user_id).stream()
        # Get messages where user is receiver
        received_messages = messages_ref.where('receiverId', '==', current_user_id).stream()
        
        conversations_dict = {}
        
        # Process sent messages
        for msg in sent_messages:
            msg_data = msg.to_dict()
            other_user_id = msg_data.get('receiverId')
            
            if other_user_id == current_user_id:
                continue
                
            if other_user_id not in conversations_dict:
                # Get user info
                user_doc = db.collection('users').document(other_user_id).get()
                user_data = user_doc.to_dict() if user_doc.exists else {}
                
                conversations_dict[other_user_id] = {
                    'user_id': other_user_id,
                    'user_name': user_data.get('name', 'Unknown'),
                    'user_photo': user_data.get('photo_url', '/static/default-profile.png'),
                    'last_message': msg_data.get('content', ''),
                    'timestamp': msg_data.get('timestamp'),
                    'is_sent_by_me': True,
                    'unread_count': 0
                }
            else:
                # Update if newer message
                conv = conversations_dict[other_user_id]
                msg_time = msg_data.get('timestamp')
                conv_time = conv.get('timestamp')
                
                if msg_time and conv_time:
                    # Compare timestamps
                    msg_seconds = msg_time.seconds if hasattr(msg_time, 'seconds') else 0
                    conv_seconds = conv_time.seconds if hasattr(conv_time, 'seconds') else 0
                    
                    if msg_seconds > conv_seconds:
                        conv['last_message'] = msg_data.get('content', '')
                        conv['timestamp'] = msg_time
                        conv['is_sent_by_me'] = True
        
        # Process received messages
        for msg in received_messages:
            msg_data = msg.to_dict()
            other_user_id = msg_data.get('senderId')
            
            if other_user_id == current_user_id:
                continue
                
            if other_user_id not in conversations_dict:
                # Get user info
                user_doc = db.collection('users').document(other_user_id).get()
                user_data = user_doc.to_dict() if user_doc.exists else {}
                
                # Count unread messages
                unread_query = db.collection('messages')\
                    .where('senderId', '==', other_user_id)\
                    .where('receiverId', '==', current_user_id)\
                    .where('read', '==', False)\
                    .stream()
                unread_count = len(list(unread_query))
                
                conversations_dict[other_user_id] = {
                    'user_id': other_user_id,
                    'user_name': user_data.get('name', 'Unknown'),
                    'user_photo': user_data.get('photo_url', '/static/default-profile.png'),
                    'last_message': msg_data.get('content', ''),
                    'timestamp': msg_data.get('timestamp'),
                    'is_sent_by_me': False,
                    'unread_count': unread_count
                }
            else:
                # Update if newer message
                conv = conversations_dict[other_user_id]
                msg_time = msg_data.get('timestamp')
                conv_time = conv.get('timestamp')
                
                if msg_time and conv_time:
                    # Compare timestamps
                    msg_seconds = msg_time.seconds if hasattr(msg_time, 'seconds') else 0
                    conv_seconds = conv_time.seconds if hasattr(conv_time, 'seconds') else 0
                    
                    if msg_seconds > conv_seconds:
                        conv['last_message'] = msg_data.get('content', '')
                        conv['timestamp'] = msg_time
                        conv['is_sent_by_me'] = False
        
        # Convert to list and format
        conversations_list = []
        for conv in conversations_dict.values():
            # Format timestamp
            timestamp = conv.get('timestamp')
            if timestamp:
                if hasattr(timestamp, 'to_date'):
                    dt = timestamp.to_date()
                elif hasattr(timestamp, 'seconds'):
                    dt = datetime.fromtimestamp(timestamp.seconds)
                else:
                    dt = datetime.now()
                
                # Calculate relative time
                now = datetime.now()
                diff = now - dt
                
                if diff.days == 0:
                    conv['timestamp_formatted'] = dt.strftime('%I:%M %p')
                elif diff.days == 1:
                    conv['timestamp_formatted'] = 'Yesterday'
                elif diff.days < 7:
                    conv['timestamp_formatted'] = dt.strftime('%A')
                else:
                    conv['timestamp_formatted'] = dt.strftime('%b %d')
            else:
                conv['timestamp_formatted'] = 'Recently'
            
            conversations_list.append(conv)
        
        # Sort by timestamp (newest first)
        conversations_list.sort(key=lambda x: x.get('timestamp').seconds if hasattr(x.get('timestamp'), 'seconds') else 0, reverse=True)
        
        return jsonify({
            'status': 'success',
            'conversations': conversations_list
        })
        
    except Exception as e:
        print(f"Error fetching conversations: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/api/messages/<user_id>')
def api_messages(user_id):
    """Get messages between current user and target user - FIXED VERSION"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    try:
        # Get messages using two separate queries to avoid composite index issues
        messages = []
        
        # Get messages where current user is sender and target is receiver
        sent_query = db.collection('messages')\
            .where('senderId', '==', current_user_id)\
            .where('receiverId', '==', user_id)\
            .order_by('timestamp')
        
        sent_messages = sent_query.stream()
        for doc in sent_messages:
            msg_data = doc.to_dict()
            msg_data['id'] = doc.id
            messages.append(msg_data)
        
        # Get messages where current user is receiver and target is sender
        received_query = db.collection('messages')\
            .where('senderId', '==', user_id)\
            .where('receiverId', '==', current_user_id)\
            .order_by('timestamp')
        
        received_messages = received_query.stream()
        for doc in received_messages:
            msg_data = doc.to_dict()
            msg_data['id'] = doc.id
            messages.append(msg_data)
        
        # Sort all messages by timestamp
        messages.sort(key=lambda x: x.get('timestamp').seconds if hasattr(x.get('timestamp'), 'seconds') else 0)
        
        # Format messages for frontend
        formatted_messages = []
        for msg in messages:
            formatted_msg = msg.copy()
            
            # Convert timestamp
            timestamp = msg.get('timestamp')
            if timestamp:
                if hasattr(timestamp, 'to_date'):
                    dt = timestamp.to_date()
                elif hasattr(timestamp, 'seconds'):
                    dt = datetime.fromtimestamp(timestamp.seconds)
                else:
                    dt = datetime.now()
                
                formatted_msg['datetime'] = dt.isoformat()
                formatted_msg['timestamp'] = dt.isoformat()
            
            formatted_messages.append(formatted_msg)
        
        # Mark received messages as read
        unread_query = db.collection('messages')\
            .where('senderId', '==', user_id)\
            .where('receiverId', '==', current_user_id)\
            .where('read', '==', False)\
            .stream()
        
        batch = db.batch()
        for doc in unread_query:
            doc_ref = db.collection('messages').document(doc.id)
            batch.update(doc_ref, {
                'read': True,
                'readAt': firestore.SERVER_TIMESTAMP
            })
        
        if batch._write_pbs:  # Only commit if there are updates
            batch.commit()
        
        # Get user info
        user_doc = db.collection('users').document(user_id).get()
        user_data = user_doc.to_dict() if user_doc.exists else {}
        
        return jsonify({
            'status': 'success',
            'messages': formatted_messages,
            'user_info': {
                'name': user_data.get('name', 'User'),
                'photo_url': user_data.get('photo_url', '/static/default-profile.png'),
                'user_id': user_id
            }
        })
        
    except Exception as e:
        print(f"Error fetching messages: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/api/send-message', methods=['POST'])
def api_send_message():
    """Send a new message - FIXED VERSION"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        receiver_id = data.get('receiverId')
        content = data.get('content', '').strip()
        
        if not receiver_id:
            return jsonify({'status': 'error', 'message': 'Receiver ID is required'}), 400
        
        if not content:
            return jsonify({'status': 'error', 'message': 'Message content is required'}), 400
        
        # Get sender info
        sender_doc = db.collection('users').document(current_user_id).get()
        sender_data = sender_doc.to_dict() if sender_doc.exists else {}
        
        # Get receiver info
        receiver_doc = db.collection('users').document(receiver_id).get()
        receiver_data = receiver_doc.to_dict() if receiver_doc.exists else {}
        
        # Create message document
        message_data = {
            'senderId': current_user_id,
            'receiverId': receiver_id,
            'content': content,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'read': False,
            'type': 'text',
            'senderName': sender_data.get('name', 'Unknown'),
            'receiverName': receiver_data.get('name', 'Unknown')
        }
        
        # Add to Firestore
        message_ref = db.collection('messages').document()
        message_ref.set(message_data)
        
        return jsonify({
            'status': 'success',
            'message': 'Message sent successfully',
            'messageId': message_ref.id
        })
        
    except Exception as e:
        print(f"Error sending message: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/api/search-users', methods=['GET'])
def api_search_users_for_messages():
    """Search users for starting new conversations - FIXED VERSION"""
    current_user_id = session.get('user_id')
    if not current_user_id:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    try:
        query = request.args.get('q', '').strip().lower()
        
        # Get all users
        users_ref = db.collection('users')
        users_query = users_ref.where('profileVisibility', '==', 'Public').stream()
        
        search_results = []
        
        for doc in users_query:
            user = doc.to_dict()
            user_id = doc.id
            
            # Skip current user
            if user_id == current_user_id:
                continue
            
            # Get user data for search
            user_name = user.get('name', '').lower()
            user_headline = user.get('headline', '').lower()
            offered_skills = [skill.lower() for skill in user.get('offeredSkill', [])]
            
            # Check if matches search query
            matches = False
            if not query:
                matches = True  # Show all users if no query
            else:
                # Search in name
                if query in user_name:
                    matches = True
                # Search in headline
                elif query in user_headline:
                    matches = True
                # Search in skills
                elif any(query in skill for skill in offered_skills):
                    matches = True
            
            if matches:
                search_results.append({
                    'user_id': user_id,
                    'name': user.get('name', 'Anonymous'),
                    'headline': user.get('headline', ''),
                    'photo_url': user.get('photo_url', '/static/default-profile.png'),
                    'offeredSkills': user.get('offeredSkill', [])[:3]
                })
        
        # Sort by name
        search_results.sort(key=lambda x: x['name'].lower())
        
        return jsonify({
            'status': 'success',
            'count': len(search_results),
            'results': search_results[:20]
        })
        
    except Exception as e:
        print(f"Error searching users: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ==============================================================================
# FEATURE 1: SMART SKILL MATCHING (Deterministic Algorithm & Reciprocal Ranking)
# ==============================================================================
@main.route('/smart-matches')
def smart_matches_page():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('main.login'))
    return render_template('smart_matches.html')

@main.route('/api/smart-matches', methods=['GET'])
def api_smart_matches():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'Authentication required'}), 401

        current_user_doc = db.collection('users').document(user_id).get()
        if not current_user_doc.exists:
            return jsonify({'status': 'error', 'message': 'Current user profile not found'}), 404

        me = current_user_doc.to_dict()
        my_offered = [s.strip().lower() for s in (me.get('offeredSkill') or []) if s.strip()]
        my_wanted = [s.strip().lower() for s in (me.get('requestedSkill') or me.get('wantedSkill') or []) if s.strip()]
        my_avail = me.get('availability', '')

        # Query filters
        cat_filter = request.args.get('category', '').strip().lower()
        avail_filter = request.args.get('availability', '').strip().lower()

        all_users = db.collection('users').stream()
        matches = []

        for doc in all_users:
            if doc.id == user_id:
                continue
            u = doc.to_dict()
            if u.get('profileVisibility', 'Public') != 'Public':
                continue

            u_offered = [s.strip().lower() for s in (u.get('offeredSkill') or []) if s.strip()]
            u_wanted = [s.strip().lower() for s in (u.get('requestedSkill') or u.get('wantedSkill') or []) if s.strip()]
            u_avail = u.get('availability', '')

            # Availability filter
            if avail_filter and avail_filter != 'all':
                if avail_filter not in str(u_avail).lower():
                    continue

            # Check overlap
            direct_matches = [skill for skill in u_offered if skill in my_wanted]
            reverse_matches = [skill for skill in my_offered if skill in u_wanted]

            if not direct_matches and not reverse_matches:
                continue

            # Deterministic compatibility score
            # Direct match (they teach what I want): 40 pts per skill (max 80)
            # Reverse match (I teach what they want - Reciprocal!): 50 pts per skill (max 100)
            # Same availability bonus: 20 pts
            score = 0
            score += len(direct_matches) * 40
            score += len(reverse_matches) * 50
            if my_avail and u_avail and (str(my_avail).lower() in str(u_avail).lower() or str(u_avail).lower() in str(my_avail).lower()):
                score += 20

            # Normalize to 0-100%
            normalized_score = min(100, max(15, score))

            # Generate match explanation
            reasons = []
            if direct_matches and reverse_matches:
                reasons.append(f"⭐ Perfect Reciprocal Swap! Can teach you {', '.join(direct_matches[:2])} and wants your {', '.join(reverse_matches[:2])}.")
            elif direct_matches:
                reasons.append(f"Teaches skills on your wishlist: {', '.join(direct_matches[:2])}.")
            elif reverse_matches:
                reasons.append(f"Looking for your expertise in: {', '.join(reverse_matches[:2])}.")

            if my_avail and u_avail and my_avail.lower() == u_avail.lower():
                reasons.append(f"Matching availability ({u_avail}).")

            m_name = u.get('name') or u.get('fullName') or 'Skill Enthusiast'
            matches.append({
                'user_id': doc.id,
                'name': m_name,
                'headline': u.get('headline') or u.get('title') or '',
                'photo_url': get_avatar_url(u.get('photo_url'), m_name, u.get('email', '')),
                'location': u.get('city') or u.get('location') or 'Remote',
                'availability': u_avail or 'Flexible',
                'offered_skills': u.get('offeredSkill') or [],
                'wanted_skills': u.get('requestedSkill') or u.get('wantedSkill') or [],
                'compatibility_score': normalized_score,
                'is_reciprocal': bool(direct_matches and reverse_matches),
                'direct_matches': direct_matches,
                'reverse_matches': reverse_matches,
                'explanations': reasons
            })

        # Rank: Reciprocal swaps first, then highest compatibility score
        matches.sort(key=lambda x: (x['is_reciprocal'], x['compatibility_score']), reverse=True)

        return jsonify({
            'status': 'success',
            'count': len(matches),
            'matches': matches
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ==============================================================================
# FEATURE 2: LEARNING SESSION SCHEDULER
# ==============================================================================
@main.route('/sessions')
def sessions_dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('main.login'))
    return render_template('sessions.html')

@main.route('/api/sessions', methods=['GET', 'POST'])
def api_sessions():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Authentication required'}), 401

    if request.method == 'GET':
        # Retrieve all public sessions, study groups, or sessions user participates in
        store_sessions = db.collection('learning_sessions').stream()
        results = []
        for doc in store_sessions:
            s_data = doc.to_dict()
            s_data['id'] = doc.id
            is_host = s_data.get('hostUserId') == user_id
            is_participant = s_data.get('participantUserId') == user_id
            is_public = s_data.get('isPublic', True)

            # Show if user is part of it OR if it's public / study group
            if is_host or is_participant or is_public:
                other_id = s_data.get('participantUserId') if is_host else s_data.get('hostUserId')
                if other_id:
                    other_doc = db.collection('users').document(other_id).get()
                    s_data['otherUser'] = other_doc.to_dict() if other_doc.exists else {'name': 'Member'}
                else:
                    s_data['otherUser'] = {'name': 'Open Community Study Group' if s_data.get('isStudyGroup') else 'Public Session'}

                # Attach host details
                host_doc = db.collection('users').document(s_data.get('hostUserId', '')).get()
                s_data['hostName'] = host_doc.get('name') if host_doc.exists else 'Host'
                results.append(s_data)
        
        # Sort by sessionDate ascending
        results.sort(key=lambda s: s.get('sessionDate', ''))
        return jsonify({'status': 'success', 'sessions': results})

    # POST: Schedule a session or create a study group
    try:
        data = request.get_json() or {}
        swap_id = data.get('swapId', '')
        is_private = bool(data.get('isPrivate', False))
        is_study_group = bool(data.get('isStudyGroup', False))
        is_public = not is_private
        participant_id = data.get('participantUserId', '').strip() or None
        
        title = data.get('title', 'Community Study Group' if is_study_group else 'Skill Exchange Session')
        meeting_url = data.get('meetingUrl', '')
        session_date = data.get('sessionDate')
        start_time = data.get('startTime')
        end_time = data.get('endTime')
        notes = data.get('notes', '')
        send_to_chat = bool(data.get('sendToChat', False))

        if not session_date or not start_time or not end_time or not title:
            return jsonify({'status': 'error', 'message': 'Missing title, date, or timeslot'}), 400

        # Validate conflict check for private 1-on-1 sessions
        if is_private and participant_id:
            existing = db.collection('learning_sessions').where('sessionDate', '==', session_date).stream()
            for doc in existing:
                ex = doc.to_dict()
                if ex.get('status') == 'cancelled':
                    continue
                if ex.get('hostUserId') in (user_id, participant_id) or ex.get('participantUserId') in (user_id, participant_id):
                    if not (end_time <= ex.get('startTime') or start_time >= ex.get('endTime')):
                        return jsonify({'status': 'error', 'message': 'Time conflict: A session is already scheduled for that timeslot!'}), 409

        session_id = str(uuid.uuid4())
        session_obj = {
            'id': session_id,
            'swapId': swap_id,
            'hostUserId': user_id,
            'participantUserId': participant_id,
            'title': title,
            'meetingUrl': meeting_url,
            'sessionDate': session_date,
            'startTime': start_time,
            'endTime': end_time,
            'isPublic': is_public,
            'isPrivate': is_private,
            'isStudyGroup': is_study_group,
            'status': 'scheduled',
            'notes': notes,
            'created_at': datetime.utcnow().isoformat()
        }
        db.collection('learning_sessions').document(session_id).set(session_obj)

        # Optionally post invitation message to user chat or swap thread
        if send_to_chat and participant_id:
            msg_id = str(uuid.uuid4())
            invite_text = f"📅 I've scheduled a session: '{title}' on {session_date} from {start_time} to {end_time}."
            if meeting_url:
                invite_text += f" Meeting link: {meeting_url}"
            db.collection('messages').document(msg_id).set({
                'id': msg_id,
                'senderId': user_id,
                'receiverId': participant_id,
                'swapId': swap_id,
                'content': invite_text,
                'timestamp': datetime.utcnow().isoformat(),
                'isRead': False
            })

        return jsonify({'status': 'success', 'message': 'Session scheduled successfully!', 'session': session_obj})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/api/sessions/<session_id>', methods=['PUT'])
def api_edit_session(session_id):
    """Edit an existing learning session or study group"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Authentication required'}), 401
    
    data = request.get_json() or {}
    doc_ref = db.collection('learning_sessions').document(session_id)
    doc = doc_ref.get()
    if not doc.exists:
        return jsonify({'status': 'error', 'message': 'Session not found'}), 404
        
    s_data = doc.to_dict()
    if s_data.get('hostUserId') != user_id and s_data.get('participantUserId') != user_id:
        return jsonify({'status': 'error', 'message': 'Only session organizers can edit this session'}), 403
        
    updates = {}
    for field in ('title', 'sessionDate', 'startTime', 'endTime', 'meetingUrl', 'notes', 'status'):
        if field in data:
            updates[field] = data[field]
    if 'isPrivate' in data:
        updates['isPrivate'] = bool(data['isPrivate'])
        updates['isPublic'] = not updates['isPrivate']
        
    updates['updated_at'] = datetime.utcnow().isoformat()
    doc_ref.update(updates)
    return jsonify({'status': 'success', 'message': 'Session updated successfully!'})

@main.route('/api/sessions/<session_id>', methods=['DELETE'])
def api_delete_session(session_id):
    """Delete a single session from history/calendar"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Authentication required'}), 401
        
    doc_ref = db.collection('learning_sessions').document(session_id)
    doc = doc_ref.get()
    if not doc.exists:
        return jsonify({'status': 'error', 'message': 'Session not found'}), 404
        
    s_data = doc.to_dict()
    if s_data.get('hostUserId') != user_id and s_data.get('participantUserId') != user_id:
        return jsonify({'status': 'error', 'message': 'Unauthorized to delete this session'}), 403
        
    doc_ref.delete()
    return jsonify({'status': 'success', 'message': 'Session deleted successfully'})

@main.route('/api/sessions/batch-delete', methods=['POST'])
def api_batch_delete_sessions():
    """Delete selected sessions or completed/cancelled history in bulk"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Authentication required'}), 401
        
    data = request.get_json() or {}
    session_ids = data.get('session_ids', [])
    delete_history = bool(data.get('delete_history', False))
    
    deleted_count = 0
    if delete_history:
        # Delete all completed or cancelled sessions for this user
        all_sessions = db.collection('learning_sessions').stream()
        for doc in all_sessions:
            s_data = doc.to_dict()
            if s_data.get('status') in ('completed', 'cancelled'):
                if s_data.get('hostUserId') == user_id or s_data.get('participantUserId') == user_id:
                    db.collection('learning_sessions').document(doc.id).delete()
                    deleted_count += 1
    elif session_ids:
        for sid in session_ids:
            doc_ref = db.collection('learning_sessions').document(sid)
            doc = doc_ref.get()
            if doc.exists:
                s_data = doc.to_dict()
                if s_data.get('hostUserId') == user_id or s_data.get('participantUserId') == user_id:
                    doc_ref.delete()
                    deleted_count += 1
                    
    return jsonify({'status': 'success', 'deleted_count': deleted_count, 'message': f'Deleted {deleted_count} session(s)'})

@main.route('/api/sessions/<session_id>/status', methods=['POST'])
def api_update_session_status(session_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Authentication required'}), 401
    
    data = request.get_json() or {}
    new_status = data.get('status')  # 'completed', 'cancelled', 'missed'
    if new_status not in ('completed', 'cancelled', 'missed', 'scheduled'):
        return jsonify({'status': 'error', 'message': 'Invalid status'}), 400

    doc_ref = db.collection('learning_sessions').document(session_id)
    doc = doc_ref.get()
    if not doc.exists:
        return jsonify({'status': 'error', 'message': 'Session not found'}), 404

    s_data = doc.to_dict()
    if user_id not in (s_data.get('hostUserId'), s_data.get('participantUserId')):
        return jsonify({'status': 'error', 'message': 'Unauthorized to modify this session'}), 403

    doc_ref.update({'status': new_status})
    return jsonify({'status': 'success', 'message': f'Session status updated to {new_status}'})


# ==============================================================================
# FEATURE 3: LIBRARY RESOURCE HUB (File Uploads & Learning Materials)
# ==============================================================================
@main.route('/library')
def library_page():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('main.login'))
    return render_template('library.html')

@main.route('/api/library', methods=['GET', 'POST'])
def api_library():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Authentication required'}), 401

    if request.method == 'GET':
        category = request.args.get('category')
        query = request.args.get('q', '').strip().lower()

        docs = db.collection('library_resources').stream()
        results = []
        for doc in docs:
            r = doc.to_dict()
            r['id'] = doc.id
            if category and category.lower() != 'all' and r.get('category', '').lower() != category.lower():
                continue
            if query:
                title = r.get('title', '').lower()
                desc = r.get('description', '').lower()
                skill = r.get('skillTag', '').lower()
                if query not in title and query not in desc and query not in skill:
                    continue

            # Fetch uploader name
            up_doc = db.collection('users').document(r.get('uploaderId', '')).get()
            r['uploaderName'] = up_doc.get('name') if up_doc.exists else 'Community Member'
            results.append(r)

        results.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return jsonify({'status': 'success', 'resources': results})

    # POST: Upload Resource or link
    from werkzeug.utils import secure_filename
    from flask import current_app

    title = request.form.get('title')
    description = request.form.get('description', '')
    category = request.form.get('category', 'General')
    skill_tag = request.form.get('skillTag', '')
    resource_type = request.form.get('resourceType', 'file')
    external_link = request.form.get('link', '')

    if not title:
        return jsonify({'status': 'error', 'message': 'Title is required'}), 400

    file_url = external_link
    file_name = None
    file_size = 0

    if resource_type == 'file' and 'file' in request.files:
        uploaded_file = request.files['file']
        if uploaded_file and uploaded_file.filename != '':
            raw_filename = secure_filename(uploaded_file.filename)
            unique_name = f"{uuid.uuid4().hex[:8]}_{raw_filename}"
            save_path = os.path.join(current_app.config['LIBRARY_UPLOAD_FOLDER'], unique_name)
            uploaded_file.save(save_path)
            file_url = f"/static/uploads/library/{unique_name}"
            file_name = raw_filename
            file_size = os.path.getsize(save_path)

    resource_id = str(uuid.uuid4())
    resource_data = {
        'id': resource_id,
        'uploaderId': user_id,
        'title': title,
        'description': description,
        'category': category,
        'skillTag': skill_tag,
        'resourceType': resource_type,
        'fileUrl': file_url,
        'fileName': file_name,
        'fileSizeBytes': file_size,
        'downloadsCount': 0,
        'created_at': datetime.utcnow().isoformat()
    }
    db.collection('library_resources').document(resource_id).set(resource_data)
    return jsonify({'status': 'success', 'message': 'Resource added to Library!', 'resource': resource_data})