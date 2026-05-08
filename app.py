from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_session import Session
from authlib.integrations.flask_client import OAuth
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
import random
import json
import sqlite3
import requests
from datetime import datetime
from dotenv import load_dotenv
import models
from flask_session import Session

load_dotenv()

app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'supersecretkey')

app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True

# Testing ke liye False rakho
app.config['SESSION_COOKIE_SECURE'] = False

Session(app)
# Initialize OAuth
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

# Initialize database
models.init_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'warning')
            return redirect(url_for('login'))
        
        conn = models.get_db()
        user = conn.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        conn.close()
        
        if not user or not user['is_admin']:
            flash('Admin access required', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def get_user(user_id):
    conn = models.get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return user

def update_user_stats(user_id):
    conn = models.get_db()
    attempts = conn.execute(
        'SELECT SUM(score) as total_correct, COUNT(*) as total_quizzes FROM quiz_attempts WHERE user_id = ?',
        (user_id,)
    ).fetchone()
    
    total_correct = attempts['total_correct'] or 0
    total_quizzes = attempts['total_quizzes'] or 0
    
    conn.execute(
        'UPDATE users SET total_correct = ?, total_quizzes = ? WHERE id = ?',
        (total_correct, total_quizzes, user_id)
    )
    conn.commit()
    conn.close()

# ==================== AUTH ROUTES ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = models.get_db()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user and user['password_hash'] and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = bool(user['is_admin'])
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        
        try:
            conn = models.get_db()
            conn.execute(
                'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                (username, email, hashed_password)
            )
            conn.commit()
            user_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            conn.close()
            
            session['user_id'] = user_id
            session['username'] = username
            session['is_admin'] = False
            flash('Registration successful!', 'success')
            return redirect(url_for('dashboard'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists', 'danger')
    
    return render_template('register.html')

@app.route('/google-login')
def google_login():
    redirect_uri = url_for('google_auth', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/google-auth')
def google_auth():
    try:
        # Get the access token from Google
        token = google.authorize_access_token()
        
        # Method 1: Try to get user info directly from token (newer Authlib versions)
        user_info = token.get('userinfo')
        
        # Method 2: If not present, fetch manually using access token
        if not user_info:
            import requests
            response = requests.get(
                'https://www.googleapis.com/oauth2/v3/userinfo',
                headers={'Authorization': f'Bearer {token["access_token"]}'}
            )
            if response.status_code != 200:
                flash('Failed to fetch user info from Google', 'danger')
                return redirect(url_for('login'))
            user_info = response.json()
        
        email = user_info.get('email')
        if not email:
            flash('No email provided by Google', 'danger')
            return redirect(url_for('login'))
        
        username = user_info.get('name', email.split('@')[0])
        google_id = user_info.get('sub')
        
        conn = models.get_db()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        
        if not user:
            # Create new user
            cursor = conn.execute(
                'INSERT INTO users (username, email, google_id) VALUES (?, ?, ?)',
                (username, email, google_id)
            )
            user_id = cursor.lastrowid
            is_admin = False
        else:
            user_id = user['id']
            is_admin = bool(user['is_admin'])
            # If user exists but google_id not set (e.g., registered via email), update it
            if not user['google_id']:
                conn.execute('UPDATE users SET google_id = ? WHERE id = ?', (google_id, user_id))
                conn.commit()
        
        conn.close()
        
        # Set session variables
        session['user_id'] = user_id
        session['username'] = username
        session['is_admin'] = is_admin
        
        flash('Google login successful!', 'success')
        return redirect(url_for('dashboard'))
    
    except Exception as e:
        print(f"Google auth error: {e}")
        flash(f'Login failed: {str(e)}', 'danger')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

# ==================== MAIN ROUTES ====================

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_user(session['user_id'])
    conn = models.get_db()
    
    recent_attempts = conn.execute(
        'SELECT * FROM quiz_attempts WHERE user_id = ? ORDER BY timestamp DESC LIMIT 5',
        (session['user_id'],)
    ).fetchall()
    
    topics = ['Theory of Computation', 'Advance Java', 'Python', 'AI']
    topic_performance = []
    for topic in topics:
        stats = conn.execute(
            'SELECT AVG(score * 100.0 / total_questions) as avg_score, COUNT(*) as count FROM quiz_attempts WHERE user_id = ? AND topic = ?',
            (session['user_id'], topic)
        ).fetchone()
        topic_performance.append({
            'topic': topic,
            'avg_score': round(stats['avg_score'] or 0, 1),
            'count': stats['count']
        })
    
    conn.close()
    return render_template('dashboard.html', user=user, recent_attempts=recent_attempts, topic_performance=topic_performance)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = get_user(session['user_id'])
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        
        conn = models.get_db()
        try:
            conn.execute('UPDATE users SET username = ?, email = ? WHERE id = ?', (username, email, session['user_id']))
            conn.commit()
            session['username'] = username
            flash('Profile updated successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Username or email already taken', 'danger')
        finally:
            conn.close()
        
        return redirect(url_for('profile'))
    
    return render_template('profile.html', user=user)

@app.route('/leaderboard')
def leaderboard():
    conn = models.get_db()
    leaders = conn.execute('''
        SELECT id, username, total_correct, total_quizzes,
               CASE WHEN total_quizzes > 0 THEN ROUND(total_correct * 100.0 / (total_quizzes * 5), 1) ELSE 0 END as avg_score
        FROM users 
        WHERE total_quizzes > 0
        ORDER BY total_correct DESC, avg_score DESC
        LIMIT 20
    ''').fetchall()
    conn.close()
    return render_template('leaderboard.html', leaders=leaders)

@app.route('/history')
@login_required
def history():
    topic_filter = request.args.get('topic', '')
    conn = models.get_db()
    
    query = 'SELECT * FROM quiz_attempts WHERE user_id = ?'
    params = [session['user_id']]
    
    if topic_filter:
        query += ' AND topic = ?'
        params.append(topic_filter)
    
    query += ' ORDER BY timestamp DESC'
    
    attempts = conn.execute(query, params).fetchall()
    conn.close()
    
    topics = ['Theory of Computation', 'Advance Java', 'Python', 'AI']
    return render_template('history.html', attempts=attempts, topics=topics, current_filter=topic_filter)

@app.route('/quiz')
@login_required
def quiz():
    return render_template('quiz.html')

# ==================== QUIZ API ROUTES ====================

@app.route('/api/topics')
def get_topics():
    conn = models.get_db()
    topics = conn.execute('SELECT DISTINCT topic, COUNT(*) as count FROM questions GROUP BY topic').fetchall()
    conn.close()
    return jsonify([{'name': t['topic'], 'count': t['count']} for t in topics])

@app.route('/api/quiz/start', methods=['POST'])
@login_required
def start_quiz():
    data = request.get_json()
    topic = data.get('topic')
    num_questions = min(int(data.get('num_questions', 5)), 10)
    
    conn = models.get_db()
    if topic == 'all':
        questions = conn.execute('SELECT * FROM questions ORDER BY RANDOM() LIMIT ?', (num_questions,)).fetchall()
    else:
        questions = conn.execute('SELECT * FROM questions WHERE topic = ? ORDER BY RANDOM() LIMIT ?', (topic, num_questions)).fetchall()
    conn.close()
    
    if not questions:
        return jsonify({'error': 'No questions available'}), 400
    
    quiz_data = {
        'questions': [dict(q) for q in questions],
        'current_index': 0,
        'answers': [],
        'topic': topic if topic != 'all' else 'Mixed',
        'start_time': datetime.now().isoformat()
    }
    session['current_quiz'] = quiz_data
    
    first_q = quiz_data['questions'][0]
    return jsonify({
        'question_id': first_q['id'],
        'question_text': first_q['question_text'],
        'options': [first_q['option1'], first_q['option2'], first_q['option3'], first_q['option4']],
        'current': 1,
        'total': len(questions),
        'topic': quiz_data['topic']
    })

@app.route('/api/quiz/answer', methods=['POST'])
@login_required
def submit_answer():
    if 'current_quiz' not in session:
        return jsonify({'error': 'No active quiz'}), 400
    
    quiz_data = session['current_quiz']
    data = request.get_json()
    selected_option = data.get('selected_option', 0)
    time_taken = data.get('time_taken', 0)
    
    current_q = quiz_data['questions'][quiz_data['current_index']]
    is_correct = (selected_option == current_q['correct_option'])
    
    quiz_data['answers'].append({
        'question_id': current_q['id'],
        'selected': selected_option,
        'correct': is_correct,
        'time_taken': time_taken
    })
    
    quiz_data['current_index'] += 1
    
    if quiz_data['current_index'] >= len(quiz_data['questions']):
        score = sum(1 for a in quiz_data['answers'] if a['correct'])
        total = len(quiz_data['answers'])
        
        conn = models.get_db()
        conn.execute('''
            INSERT INTO quiz_attempts (user_id, topic, score, total_questions, answers_json)
            VALUES (?, ?, ?, ?, ?)
        ''', (session['user_id'], quiz_data['topic'], score, total, json.dumps(quiz_data['answers'])))
        conn.commit()
        conn.close()
        
        update_user_stats(session['user_id'])
        session.pop('current_quiz', None)
        
        return jsonify({'completed': True, 'score': score, 'total': total, 'percentage': round(score * 100 / total, 1)})
    
    next_q = quiz_data['questions'][quiz_data['current_index']]
    session['current_quiz'] = quiz_data
    
    return jsonify({
        'completed': False,
        'question_id': next_q['id'],
        'question_text': next_q['question_text'],
        'options': [next_q['option1'], next_q['option2'], next_q['option3'], next_q['option4']],
        'current': quiz_data['current_index'] + 1,
        'total': len(quiz_data['questions']),
        'topic': quiz_data['topic']
    })

# ==================== ADMIN ROUTES ====================

@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = models.get_db()
    total_users = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
    total_quizzes = conn.execute('SELECT COUNT(*) as count FROM quiz_attempts').fetchone()['count']
    total_questions = conn.execute('SELECT COUNT(*) as count FROM questions').fetchone()['count']
    conn.close()
    return render_template('admin/dashboard.html', total_users=total_users, total_quizzes=total_quizzes, total_questions=total_questions)

@app.route('/admin/users')
@admin_required
def admin_users():
    conn = models.get_db()
    users = conn.execute('SELECT id, username, email, total_quizzes, total_correct, is_admin, created_at FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('admin/users.html', users=users)

@app.route('/admin/user/delete/<int:user_id>')
@admin_required
def admin_delete_user(user_id):
    if user_id == session['user_id']:
        flash('You cannot delete yourself', 'danger')
        return redirect(url_for('admin_users'))
    conn = models.get_db()
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.execute('DELETE FROM quiz_attempts WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('User deleted successfully', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/make_admin/<int:user_id>')
@admin_required
def admin_make_admin(user_id):
    conn = models.get_db()
    conn.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('User is now admin', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/questions')
@admin_required
def admin_questions():
    conn = models.get_db()
    questions = conn.execute('SELECT * FROM questions ORDER BY id DESC').fetchall()
    topics = conn.execute('SELECT DISTINCT topic FROM questions').fetchall()
    conn.close()
    return render_template('admin/questions.html', questions=questions, topics=topics)

@app.route('/admin/question/add', methods=['GET', 'POST'])
@admin_required
def admin_add_question():
    if request.method == 'POST':
        topic = request.form['topic']
        question_text = request.form['question_text']
        option1 = request.form['option1']
        option2 = request.form['option2']
        option3 = request.form['option3']
        option4 = request.form['option4']
        correct_option = int(request.form['correct_option'])
        difficulty = int(request.form['difficulty'])
        
        conn = models.get_db()
        conn.execute('''
            INSERT INTO questions (topic, question_text, option1, option2, option3, option4, correct_option, difficulty)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (topic, question_text, option1, option2, option3, option4, correct_option, difficulty))
        conn.commit()
        conn.close()
        flash('Question added successfully', 'success')
        return redirect(url_for('admin_questions'))
    return render_template('admin/add_question.html')

@app.route('/admin/question/delete/<int:qid>')
@admin_required
def admin_delete_question(qid):
    conn = models.get_db()
    conn.execute('DELETE FROM questions WHERE id = ?', (qid,))
    conn.commit()
    conn.close()
    flash('Question deleted', 'success')
    return redirect(url_for('admin_questions'))

@app.route('/admin/attempts')
@admin_required
def admin_attempts():
    conn = models.get_db()
    attempts = conn.execute('''
        SELECT qa.*, u.username 
        FROM quiz_attempts qa 
        JOIN users u ON qa.user_id = u.id 
        ORDER BY qa.timestamp DESC 
        LIMIT 50
    ''').fetchall()
    conn.close()
    return render_template('admin/attempts.html', attempts=attempts)

if __name__ == '__main__':
    app.run(debug=True, port=5000)