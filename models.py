import sqlite3
import json
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

DB_PATH = os.path.join('database', 'quiz.db')
os.makedirs('database', exist_ok=True)

def get_db():
    """Get database connection with WAL mode and timeout"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def init_db():
    """Initialize database with all tables and sample data"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Users table with is_admin column
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            google_id TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_score INTEGER DEFAULT 0,
            total_quizzes INTEGER DEFAULT 0,
            total_correct INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0
        )
    ''')
    
    # Questions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            question_text TEXT NOT NULL,
            option1 TEXT NOT NULL,
            option2 TEXT NOT NULL,
            option3 TEXT NOT NULL,
            option4 TEXT NOT NULL,
            correct_option INTEGER NOT NULL,
            difficulty INTEGER DEFAULT 1
        )
    ''')
    
    # Quiz attempts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            answers_json TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    
    # Insert sample questions if none exist
    cursor.execute("SELECT COUNT(*) FROM questions")
    if cursor.fetchone()[0] == 0:
        insert_sample_questions(cursor)
        conn.commit()
    
    # Insert admin user if not exists
    admin_email = "admin@quizmaster.com"
    admin_pass_hash = generate_password_hash("admin123")
    cursor.execute("SELECT id FROM users WHERE email = ?", (admin_email,))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, is_admin, total_quizzes, total_correct)
            VALUES (?, ?, ?, 1, 0, 0)
        ''', ("Admin", admin_email, admin_pass_hash))
        conn.commit()
    
    conn.close()

def insert_sample_questions(cursor):
    """Insert 40+ questions across 4 topics"""
    questions = [
        # Theory of Computation (10 questions)
        ("Theory of Computation", "What is the language accepted by a Finite Automaton?", "Regular Language", "Context-Free Language", "Context-Sensitive Language", "Recursively Enumerable Language", 1, 2),
        ("Theory of Computation", "Which of the following is not a type of Turing Machine?", "Multi-tape", "Deterministic", "Non-deterministic", "Quantum Turing Machine", 4, 3),
        ("Theory of Computation", "The pumping lemma is used to prove that a language is:", "Regular", "Context-free", "Not regular", "Decidable", 3, 3),
        ("Theory of Computation", "Which automaton has the most computational power?", "DFA", "NFA", "PDA", "Turing Machine", 4, 1),
        ("Theory of Computation", "A language is decidable if:", "There exists a TM that halts on all inputs", "There exists a TM that accepts it", "It is regular", "It is context-free", 1, 2),
        ("Theory of Computation", "Which of these is a context-free language?", "a^n b^n", "a^n b^n c^n", "ww", "a^n b^m", 1, 2),
        ("Theory of Computation", "The class P contains problems that are:", "Solvable in polynomial time", "Solvable in exponential time", "Undecidable", "NP-complete", 1, 2),
        ("Theory of Computation", "Which is true about NP-Complete problems?", "All are in P", "None are in NP", "If one is solved in P, then P=NP", "They are all decidable", 3, 3),
        ("Theory of Computation", "A DFA can have how many transitions per state per input symbol?", "Exactly one", "Zero or more", "At most one", "Exactly two", 1, 1),
        ("Theory of Computation", "Which language is accepted by a Pushdown Automaton?", "Regular", "Context-free", "Context-sensitive", "Recursive", 2, 2),
        
        # Advance Java (10 questions)
        ("Advance Java", "Which package contains the JDBC classes?", "java.jdbc", "javax.sql", "java.sql", "java.db", 3, 1),
        ("Advance Java", "What does JSP stand for?", "Java Server Pages", "Java Script Pages", "Java Servlet Pages", "Java System Pages", 1, 1),
        ("Advance Java", "Which method is used to start a thread in Java?", "start()", "run()", "init()", "begin()", 1, 1),
        ("Advance Java", "What is the default scope of a bean in Spring?", "Singleton", "Prototype", "Request", "Session", 1, 2),
        ("Advance Java", "Which annotation is used for dependency injection in Spring?", "@Inject", "@Autowired", "@Resource", "@Component", 2, 2),
        ("Advance Java", "Which interface is the root of the collection hierarchy?", "Collection", "List", "Set", "Map", 1, 1),
        ("Advance Java", "What does JPA stand for?", "Java Persistence API", "Java Programming API", "Java Process Automation", "Java Protocol Adapter", 1, 2),
        ("Advance Java", "Which method is used to execute a query in JDBC?", "executeQuery()", "runQuery()", "doQuery()", "query()", 1, 1),
        ("Advance Java", "What is the purpose of the 'synchronized' keyword?", "Thread safety", "Memory management", "Exception handling", "Garbage collection", 1, 2),
        ("Advance Java", "Which framework is used for building REST APIs in Java?", "JAX-RS", "JPA", "JSF", "JMS", 1, 2),
        
        # Python (10 questions)
        ("Python", "What is the output of type([])?", "list", "tuple", "array", "dict", 1, 1),
        ("Python", "Which keyword is used to define a function?", "def", "func", "define", "function", 1, 1),
        ("Python", "What is the correct way to create a virtual environment?", "python -m venv env", "virtualenv env", "py venv env", "python venv env", 1, 1),
        ("Python", "Which library is used for data analysis?", "pandas", "numpy", "matplotlib", "scipy", 1, 2),
        ("Python", "What is PEP 8?", "Style guide", "Package manager", "Version control", "Testing framework", 1, 1),
        ("Python", "Which data structure is immutable?", "tuple", "list", "dict", "set", 1, 1),
        ("Python", "What does lambda create?", "Anonymous function", "Loop", "Variable", "Class", 1, 2),
        ("Python", "Which method is used to add an element to a list?", "append()", "add()", "insert()", "push()", 1, 1),
        ("Python", "What is the output of 2**3?", "8", "6", "9", "5", 1, 1),
        ("Python", "Which framework is used for web development in Python?", "Django", "Spring", "Rails", "Laravel", 1, 1),
        
        # AI (10 questions)
        ("AI", "What does AI stand for?", "Artificial Intelligence", "Automated Intelligence", "Augmented Intelligence", "Algorithmic Intelligence", 1, 1),
        ("AI", "Which algorithm is used for supervised learning?", "Linear Regression", "K-means", "Apriori", "DBSCAN", 1, 2),
        ("AI", "What is a neural network inspired by?", "Human brain", "Computer circuits", "Genetic algorithms", "Fuzzy logic", 1, 1),
        ("AI", "Which library is popular for deep learning?", "TensorFlow", "Scikit-learn", "Pandas", "Matplotlib", 1, 2),
        ("AI", "What is the purpose of backpropagation?", "Update weights", "Forward pass", "Data normalization", "Feature extraction", 1, 3),
        ("AI", "Which is an example of unsupervised learning?", "K-means clustering", "Decision tree", "SVM", "Logistic regression", 1, 2),
        ("AI", "What is a heuristic function used for?", "Search optimization", "Data storage", "Network routing", "Memory allocation", 1, 2),
        ("AI", "Which technique is used for natural language processing?", "RNN", "CNN", "GAN", "VAE", 1, 3),
        ("AI", "What is reinforcement learning based on?", "Rewards and punishments", "Labeled data", "Unlabeled data", "Rules", 1, 2),
        ("AI", "Which search algorithm is optimal and complete?", "A*", "BFS", "DFS", "Hill Climbing", 1, 3),
    ]
    
    for q in questions:
        cursor.execute('''
            INSERT INTO questions (topic, question_text, option1, option2, option3, option4, correct_option, difficulty)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', q)