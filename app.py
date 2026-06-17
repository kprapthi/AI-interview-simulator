import os
import uuid
import re
import json
import sqlite3
import numpy as np
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from database import init_db, get_db_connection
# Initialize Database
init_db()
app = Flask(__name__)
app.secret_key = "ai_interview_secret_2026"
CORS(app)
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Dictionary to hold resume-generated questions for active sessions in memory
# to avoid database clutter for temporary resume sessions
RESUME_QUESTIONS_CACHE = {}
# Standard English stop words to filter for keyword matching and fallback NLP
STOP_WORDS = {
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', "you're", "you've", "you'll", "you'd",
    'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', "she's", 'her', 'hers',
    'herself', 'it', "it's", 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which',
    'who', 'whom', 'this', 'that', "that'll", 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if',
    'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between',
    'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out',
    'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why',
    'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
    'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 'don', "don't", 'should',
    "should've", 'now', 'd', 'll', 'm', 'o', 're', 've', 'y', 'ain', 'aren', "aren't", 'couldn', "couldn't",
    'didn', "didn't", 'doesn', "doesn't", 'hadn', "hadn't", 'hasn', "hasn't", 'haven', "haven't", 'isn', "isn't",
    'ma', 'mightn', "mightn't", 'mustn', "mustn't", 'needn', "needn't", 'shan', "shan't", 'shouldn', "shouldn't",
    'wasn', "wasn't", 'weren', "weren't", 'won', "won't", 'wouldn', "wouldn't"
}
# --- NLP Evaluation Engine ---
class NLPEvaluator:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(stop_words='english')
    def calculate_similarity(self, candidate_answer, ideal_answer):
        if not candidate_answer or len(candidate_answer.strip()) < 5:
            return 0.0
        
        try:
            tfidf_matrix = self.vectorizer.fit_transform([candidate_answer, ideal_answer])
            sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(sim)
        except Exception:
            # Fallback if TF-IDF fails (e.g. all stop words)
            cand_words = set(re.findall(r'\w+', candidate_answer.lower()))
            ideal_words = set(re.findall(r'\w+', ideal_answer.lower()))
            intersection = cand_words.intersection(ideal_words)
            union = cand_words.union(ideal_words)
            if not union:
                return 0.0
            return len(intersection) / len(union)
    def evaluate(self, candidate, ideal, keywords_list):
        if not candidate or len(candidate.strip()) < 3:
            return {
                "correctness": 0.0,
                "relevance": 0.0,
                "completeness": 0.0,
                "feedback": "Answer was too brief or empty. Please provide a more detailed explanation."
            }
        
        # Calculate semantic similarity
        semantic_sim = self.calculate_similarity(candidate, ideal)
        
        # Keyword check
        candidate_lower = candidate.lower()
        matched_keywords = []
        missing_keywords = []
        for kw in keywords_list:
            kw_clean = kw.strip().lower()
            if not kw_clean:
                continue
            # Match word boundary or substring
            if re.search(r'\b' + re.escape(kw_clean) + r'\b', candidate_lower):
                matched_keywords.append(kw)
            else:
                missing_keywords.append(kw)
                
        # Calculate completeness based on keywords matched
        total_kws = len(keywords_list)
        completeness = len(matched_keywords) / total_kws if total_kws > 0 else 1.0
        
        # Calculate relevance
        # Relevance checks how much the answer overlaps with ideal topics and keywords
        relevance = (semantic_sim * 0.6) + (completeness * 0.4)
        
        # Correctness is a blend of semantic similarity and length validation
        correctness = min(1.0, semantic_sim * 1.2) # Give a slight boost for matching concepts
        
        # Scale to 0-100
        correctness_score = round(correctness * 100, 1)
        relevance_score = round(relevance * 100, 1)
        completeness_score = round(completeness * 100, 1)
        
        # Generate Feedback
        feedback_points = []
        if correctness_score >= 80:
            feedback_points.append("Excellent understanding! Your explanation aligns perfectly with key technical concepts.")
        elif correctness_score >= 50:
            feedback_points.append("Good start, but you could explain the concepts with more precision.")
        else:
            feedback_points.append("Your response lacks core technical depth or might be off-topic.")
            
        if missing_keywords:
            feedback_points.append(f"Consider including key terms like: {', '.join(missing_keywords[:3])}.")
        else:
            feedback_points.append("Great job covering all critical keywords!")
            
        if len(candidate.split()) < 20:
            feedback_points.append("Try expanding your answer with more details or real-world examples.")
            
        feedback = " ".join(feedback_points)
        
        return {
            "correctness": correctness_score,
            "relevance": relevance_score,
            "completeness": completeness_score,
            "feedback": feedback
        }
nlp_evaluator = NLPEvaluator()
# --- Resume Parsing Helpers ---
def extract_skills_and_projects(text):
    # Standard keywords to scan
    known_skills = [
        "python", "javascript", "java", "c\\+\\+", "c#", "html", "css", "sql", "react", "angular", "vue",
        "node\\.js", "flask", "django", "spring", "docker", "kubernetes", "aws", "git", "machine learning",
        "deep learning", "nlp", "computer vision", "tensorflow", "pytorch", "pandas", "numpy", "scikit-learn",
        "data science", "tableau", "powerbi", "excel", "agile", "scrum", "rest api"
    ]
    
    found_skills = []
    text_lower = text.lower()
    for skill in known_skills:
        if re.search(r'\b' + skill + r'\b', text_lower):
            # Format display skill
            found_skills.append(skill.replace("\\", ""))
            
    # Extract projects (heuristics: look for sentences containing 'project', 'developed', 'built')
    projects = []
    project_matches = re.findall(r'(?:project|developed|built|created)\b([^.\n]+)', text, re.IGNORECASE)
    for match in project_matches:
        match_clean = match.strip()
        if len(match_clean) > 10 and len(match_clean) < 60:
            projects.append(match_clean)
            
    return {
        "skills": list(set(found_skills))[:6], # limit to top 6
        "projects": list(set(projects))[:3]    # limit to top 3
    }
def generate_questions_from_resume(skills, projects):
    custom_questions = []
    
    # Advanced Skill-specific realistic questions dictionary
    SKILL_QUESTIONS = {
        "python": {
            "question": "You've listed Python on your resume. If you had to optimize a CPU-bound data parsing script that is running slowly, what concurrency models or profiling libraries would you first employ to identify and resolve the bottleneck?",
            "ideal": "To optimize a CPU-bound script in Python, use the multiprocessing module to bypass the Global Interpreter Lock (GIL) and run tasks on multiple CPU cores. Profile the code using cProfile or line_profiler to locate hotspots. Minimize execution overhead by optimizing loops, using built-in functions, or compiling critical sections with Cython or PyPy.",
            "keywords": "multiprocessing,GIL,profiling,cProfile,bottleneck,cores,concurrency"
        },
        "javascript": {
            "question": "Regarding Javascript, how do you handle asynchronous operations at scale? Explain the differences in execution flow and error handling between using Promises and async/await.",
            "ideal": "Asynchronous JavaScript relies on the event loop, web APIs, and a callback queue. Promises allow chaining of callbacks via .then() and catching errors using .catch(). Async/await provides synchronous-looking syntax on top of Promises, improving readability and allowing errors to be handled cleanly using standard try-catch blocks.",
            "keywords": "event loop,Promises,async/await,non-blocking,try-catch,callback,asynchronous"
        },
        "java": {
            "question": "I see Java on your resume. How does the JVM garbage collection mechanism function, and what profiling tools or JVM tuning flags would you use to diagnose a memory leak?",
            "ideal": "The JVM garbage collector automatically reclaims heap memory by identifying unreferenced objects, dividing them into young and old generations. A memory leak happens when unused objects retain references. Diagnose using profiling tools like JProfiler, VisualVM, or Eclipse Memory Analyzer (MAT), and analyze heap dumps generated with -XX:+HeapDumpOnOutOfMemoryError.",
            "keywords": "JVM,garbage collection,heap,memory leak,JProfiler,VisualVM,references,generation"
        },
        "react": {
            "question": "Since you have experience with React, how do you manage global state scaling in a large application? What are the architectural differences or trade-offs between React Context and Redux?",
            "ideal": "For global state in React, Context is built-in and suited for low-frequency updates (e.g. themes, auth), but can trigger full sub-tree re-renders when state changes. Redux provides a centralized store with actions and reducers, optimizing performance through selectors that trigger re-renders only in subscribed components, making it better for high-frequency, complex state updates.",
            "keywords": "Redux,Context,re-renders,reducers,global state,store,selectors,state management"
        },
        "sql": {
            "question": "You've listed SQL. Explain how you would optimize a slow-running query that involves multiple table joins and millions of rows. How do database indexes help?",
            "ideal": "Optimize slow queries by checking the execution plan using EXPLAIN. Ensure appropriate indexes are created on join and filtering columns to avoid full table scans. Optimize the query by avoiding SELECT *, filtering rows early with WHERE, reducing nested subqueries, and using database partitioning or caching.",
            "keywords": "EXPLAIN,indexing,table scans,join,query optimization,partitioning,filter"
        },
        "docker": {
            "question": "For containerization with Docker, how do you optimize Docker images for production to minimize size and build time? Explain multi-stage builds.",
            "ideal": "Minimize Docker image size by using lightweight base images (like Alpine), grouping RUN instructions to reduce layers, and using .dockerignore to exclude files. Multi-stage builds compile code in a temporary build environment and copy only the final executable into a minimal runtime environment, reducing the production image size significantly.",
            "keywords": "multi-stage,Alpine,layers,runtime,base image,caching,dockerignore"
        },
        "kubernetes": {
            "question": "Regarding Kubernetes, explain how you would configure pod resource requests and limits to prevent Out-Of-Memory (OOM) kills and ensure cluster stability.",
            "ideal": "Resource requests define the minimum CPU/memory a container needs to schedule, while limits define the maximum it can consume. If a pod exceeds its memory limit, the Linux kernel terminates it with an Out-of-Memory (OOM) kill. Configure requests close to actual usage and set limits to prevent a single pod from starving other workloads on the node.",
            "keywords": "requests,limits,OOM,resources,scheduling,kernel,starvation"
        },
        "aws": {
            "question": "You have listed AWS on your resume. If you were designing a highly available, secure web application architecture on AWS, which key services and VPC components would you use?",
            "ideal": "A highly available AWS architecture deploys servers across multiple Availability Zones inside a VPC. Use private subnets for application servers, public subnets with Internet Gateways for NAT and Application Load Balancers, Route 53 for DNS routing, RDS with Multi-AZ for the database, Auto Scaling groups, and IAM policies for secure, least-privilege access.",
            "keywords": "VPC,load balancer,autoscaling,subnets,RDS,IAM,Availability Zones,Internet Gateway"
        },
        "machine learning": {
            "question": "Since you work with Machine Learning, how do you validate your models to prevent data leakage? Explain the importance of cross-validation.",
            "ideal": "Validate ML models by splitting data into independent train, validation, and test sets. Data leakage occurs when test information is inadvertently exposed during preprocessing. Prevent leakage by fitting scalers and encoders only on training data, and use k-fold cross-validation to assess how the model generalizes across different data subsets.",
            "keywords": "data leakage,cross-validation,fit,validation,preprocessing,generalize,split"
        },
        "git": {
            "question": "For version control with Git, how do you resolve complex merge conflicts, and what are the trade-offs between merging and rebasing when working with a team?",
            "ideal": "Resolve merge conflicts by identifying conflict markers in code and manually merging changes. Git merge creates a merge commit, preserving the historical timeline, but cluttering the graph. Git rebase moves your local commits to the tip of the target branch, keeping a clean, linear commit history, but rewriting history which is dangerous for shared branches.",
            "keywords": "rebase,merge,conflict,commit history,linear,rewrite,git merge"
        }
    }
    # 1. Generate project questions (Trade-offs & Scalability focus)
    for proj in projects:
        custom_questions.append({
            "id": 900 + len(custom_questions),
            "domain": "resume",
            "difficulty": "medium",
            "question_text": f"Walk me through the technical architecture of your project where you worked on '{proj}'. What were the most significant database or design trade-offs you made, and how would you scale it to handle 10,000 concurrent requests?",
            "ideal_answer": "In the project, architectural decisions involved selecting a matching database schema, setting up authentication, and defining APIs. Scalability trade-offs include implementing database caching (e.g. Redis), setting up load balancers, optimizing database queries, and utilizing asynchronous background workers to handle heavy processing.",
            "keywords": "architecture,trade-offs,scalability,load,caching,database,Redis,load balancer"
        })
        
    # 2. Generate skill questions (Realistic technical deep dives)
    for skill in skills:
        skill_clean = skill.strip().lower()
        if skill_clean in SKILL_QUESTIONS:
            sq = SKILL_QUESTIONS[skill_clean]
            custom_questions.append({
                "id": 1000 + len(custom_questions),
                "domain": "resume",
                "difficulty": "medium",
                "question_text": sq["question"],
                "ideal_answer": sq["ideal"],
                "keywords": sq["keywords"]
            })
        else:
            skill_name = skill.capitalize()
            custom_questions.append({
                "id": 1000 + len(custom_questions),
                "domain": "resume",
                "difficulty": "medium",
                "question_text": f"I see you listed {skill_name} on your resume. If you were tasked with training a junior developer on the best practices of {skill_name}, what key architectural principles or common pitfalls would you emphasize?",
                "ideal_answer": f"When using {skill_name}, it is critical to adhere to standard code quality metrics, documentation standards, and follow recommended design patterns to ensure the code remains maintainable, scalable, and secure.",
                "keywords": f"{skill_name.lower()},best practices,pitfalls,maintainable,architecture,design patterns"
            })
        
    # Standard fallbacks if resume extraction yields nothing
    if not custom_questions:
        custom_questions.append({
            "id": 999,
            "domain": "resume",
            "difficulty": "easy",
            "question_text": "Walk me through the most significant engineering challenge you have faced in your projects. Describe the trade-offs in your solution and how you verified its success.",
            "ideal_answer": "A significant technical challenge required analyzing system requirements, troubleshooting issues like memory constraints or network latency, selecting a resolution pattern, and validating it using testing framework logs.",
            "keywords": "challenge,trade-offs,solution,logs,troubleshooting,latency,verification"
        })
        
    return custom_questions
# --- Flask Web Server Routes ---
@app.route('/')
def index_route():
    if "user_id" not in session:
        return redirect('/login')

    return render_template(
        'index.html',
        username=session.get("username")
    )
@app.route('/interview')
def interview_route():

    if "user_id" not in session:
        return redirect('/login')

    return render_template('interview.html')
@app.route('/dashboard')
def dashboard_route():

    if "user_id" not in session:
        return redirect('/login')

    return render_template('dashboard.html')

# --- API Endpoints ---
@app.route('/api/register', methods=['POST'])
def register_user():

    data = request.json

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    if not username or not email or not password:
        return jsonify({
        "error": "All fields are required"
    }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE email=?",
        (email,)
    )

    existing = cursor.fetchone()

    if existing:
        conn.close()
        return jsonify({
            "error": "Email already registered"
        }), 400

    hashed_password = generate_password_hash(password)

    cursor.execute(
    """
    INSERT INTO users(username,email,password_hash)
    VALUES(?,?,?)
    """,
    (username,email,hashed_password)
)

    conn.commit()

    user_id = cursor.lastrowid

    session["user_id"] = user_id
    session["username"] = username

    conn.close()

    return jsonify({
        "message":"Registration successful"
    })
@app.route('/api/login', methods=['POST'])


def login_user():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE email=?",
        (email,)
    )

    user = cursor.fetchone()

    conn.close()

    if not user:
        return jsonify({
            "error":"User not found"
        }), 401

    if not check_password_hash(
        user["password_hash"],
        password
    ):
        return jsonify({
            "error":"Incorrect password"
        }), 401

    session["user_id"] = user["id"]
    session["username"] = user["username"]

    return jsonify({
        "message":"Login successful"
    })
@app.route('/logout')


def logout():

    session.clear()

    return redirect('/login')

@app.route('/api/upload-resume', methods=['POST'])
def upload_resume():
    if 'resume' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['resume']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    if file:
        filename = f"{uuid.uuid4()}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Read text file (support UTF-8 and latin-1 fallback)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(filepath, 'r', encoding='latin-1') as f:
                    content = f.read()
            except Exception as e:
                return jsonify({"error": f"Failed to parse text file: {str(e)}"}), 500
        except Exception as e:
            return jsonify({"error": f"Error reading file: {str(e)}"}), 500
            
        # Extract skills and projects
        extracted = extract_skills_and_projects(content)
        questions = generate_questions_from_resume(extracted['skills'], extracted['projects'])
        
        # Cache questions for later retrieval during session initialization
        resume_id = str(uuid.uuid4())
        RESUME_QUESTIONS_CACHE[resume_id] = {
            "questions": questions,
            "text": content
        }
        
        return jsonify({
            "resume_id": resume_id,
            "skills": extracted['skills'],
            "projects": extracted['projects'],
            "questions_count": len(questions)
        })
@app.route('/api/start-session', methods=['POST'])


def start_session():
    data = request.json or {}
    domain = data.get('domain', 'software_development')
    stress_mode = data.get('stress_mode', 0)
    coach_mode = data.get('coach_mode', 0)
    resume_id = data.get('resume_id', None)
    
    session_id = str(uuid.uuid4())
    resume_text = ""
    
    # Handle Resume Setup
    session_questions = []
    if resume_id and resume_id in RESUME_QUESTIONS_CACHE:
        session_questions = RESUME_QUESTIONS_CACHE[resume_id]["questions"]
        resume_text = RESUME_QUESTIONS_CACHE[resume_id]["text"]
        # Save custom questions in session scope or keep them associated with this session_id
        RESUME_QUESTIONS_CACHE[session_id] = {
            "questions": session_questions,
            "current_index": 0
        }
    
    # Create DB entry
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sessions (session_id, domain, stress_mode, coach_mode, resume_text)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, domain, stress_mode, coach_mode, resume_text))
    conn.commit()
    conn.close()
    
    # Get first question
    first_question = None
    if session_questions:
        first_question = session_questions[0]
        q_text = first_question["question_text"]
        q_id = first_question["id"]
        difficulty = first_question["difficulty"]
    else:
        # Get random easy question from domain
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM questions 
            WHERE domain = ? AND difficulty = 'easy'
            ORDER BY RANDOM() LIMIT 1
        """, (domain,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({"error": "No questions found for the selected domain."}), 404
            
        q_text = row["question_text"]
        q_id = row["id"]
        difficulty = row["difficulty"]
        
    return jsonify({
        "session_id": session_id,
        "question_id": q_id,
        "question_text": q_text,
        "difficulty": difficulty,
        "question_number": 1,
        "total_questions": 5 # standard 5-question interview
    })
@app.route('/api/evaluate-answer', methods=['POST'])


def evaluate_answer():
    data = request.json or {}
    session_id = data.get('session_id')
    question_id = data.get('question_id')
    candidate_answer = data.get('candidate_answer', '')
    eye_contact_score = data.get('eye_contact_score', 100.0)
    speaking_speed = data.get('speaking_speed', 120.0)
    filler_words_count = data.get('filler_words_count', 0)
    stress_score = data.get('stress_score', 0.0)
    question_number = data.get('question_number', 1)
    
    if not session_id or not question_id:
        return jsonify({"error": "Missing session_id or question_id"}), 400
        
    # Get session details
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
    session = cursor.fetchone()
    
    if not session:
        conn.close()
        return jsonify({"error": "Session not found"}), 404
        
    domain = session["domain"]
    stress_mode = session["stress_mode"]
    
    # Get Question Details
    ideal_answer = ""
    keywords = ""
    question_text = ""
    difficulty = "easy"
    
    # Check if resume-generated question
    is_resume_q = int(question_id) >= 900
    if is_resume_q and session_id in RESUME_QUESTIONS_CACHE:
        questions = RESUME_QUESTIONS_CACHE[session_id]["questions"]
        q_item = next((q for q in questions if q["id"] == int(question_id)), None)
        if q_item:
            ideal_answer = q_item["ideal_answer"]
            keywords = q_item["keywords"]
            question_text = q_item["question_text"]
            difficulty = q_item["difficulty"]
    else:
        cursor.execute("SELECT * FROM questions WHERE id = ?", (question_id,))
        q_row = cursor.fetchone()
        if q_row:
            ideal_answer = q_row["ideal_answer"]
            keywords = q_row["keywords"]
            question_text = q_row["question_text"]
            difficulty = q_row["difficulty"]
            
    if not ideal_answer:
        conn.close()
        return jsonify({"error": "Question not found"}), 404
        
    # 1. Run NLP Evaluation
    keywords_list = [k.strip() for k in keywords.split(',') if k.strip()]
    eval_result = nlp_evaluator.evaluate(candidate_answer, ideal_answer, keywords_list)
    
    # 2. Save Response to Database
    cursor.execute("""
        INSERT INTO responses (
            session_id, question_id, candidate_answer, correctness_score, 
            relevance_score, completeness_score, feedback, eye_contact_score, 
            speaking_speed, filler_words_count, stress_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id, question_id, candidate_answer, eval_result["correctness"],
        eval_result["relevance"], eval_result["completeness"], eval_result["feedback"],
        eye_contact_score, speaking_speed, filler_words_count, stress_score
    ))
    conn.commit()
    conn.close()
    
    # Check if interview is finished (5 questions total)
    total_questions = 5
    finished = (question_number >= total_questions)
    
    next_question_text = ""
    next_question_id = None
    next_difficulty = "easy"
    
    if not finished:
        # Determine next difficulty based on Adaptive Stress Mode
        if stress_mode == 1:
            # If doing well (correctness > 70%), make it harder
            if eval_result["correctness"] >= 70.0:
                if difficulty == "easy":
                    next_difficulty = "medium"
                else:
                    next_difficulty = "hard"
            # If struggling (correctness < 45% or stress_score > 60%), make it easier
            elif eval_result["correctness"] < 45.0 or stress_score > 60.0:
                if difficulty == "hard":
                    next_difficulty = "medium"
                else:
                    next_difficulty = "easy"
            else:
                next_difficulty = difficulty # Keep same
        else:
            # Standard incremental progression: 1 easy, 2 medium, 2 hard
            if question_number == 1:
                next_difficulty = "medium"
            elif question_number == 2:
                next_difficulty = "medium"
            else:
                next_difficulty = "hard"
                
        # Fetch Next Question
        if session_id in RESUME_QUESTIONS_CACHE:
            # Get next resume question
            RESUME_QUESTIONS_CACHE[session_id]["current_index"] += 1
            idx = RESUME_QUESTIONS_CACHE[session_id]["current_index"]
            r_questions = RESUME_QUESTIONS_CACHE[session_id]["questions"]
            
            if idx < len(r_questions):
                next_q = r_questions[idx]
                next_question_text = next_q["question_text"]
                next_question_id = next_q["id"]
                next_difficulty = next_q["difficulty"]
            else:
                # Fallback to general database if we run out of resume questions
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM questions 
                    WHERE domain = ? AND difficulty = ?
                    ORDER BY RANDOM() LIMIT 1
                """, (domain, next_difficulty))
                row = cursor.fetchone()
                conn.close()
                if row:
                    next_question_text = row["question_text"]
                    next_question_id = row["id"]
                else:
                    finished = True
        else:
            # Standard database question fetch
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Prevent showing the same question in the current session
            cursor.execute("""
                SELECT question_id FROM responses WHERE session_id = ?
            """, (session_id,))
            asked_ids = [r["question_id"] for r in cursor.fetchall()]
            
            # Find a question not yet asked
            if asked_ids:
                placeholders = ','.join('?' for _ in asked_ids)
                cursor.execute(f"""
                    SELECT * FROM questions 
                    WHERE domain = ? AND difficulty = ? AND id NOT IN ({placeholders})
                    ORDER BY RANDOM() LIMIT 1
                """, (domain, next_difficulty, *asked_ids))
            else:
                cursor.execute("""
                    SELECT * FROM questions 
                    WHERE domain = ? AND difficulty = ?
                    ORDER BY RANDOM() LIMIT 1
                """, (domain, next_difficulty))
                
            row = cursor.fetchone()
            
            # Fallback if no question matching that exact difficulty
            if not row:
                cursor.execute("""
                    SELECT * FROM questions 
                    WHERE domain = ? AND id NOT IN ({})
                    ORDER BY RANDOM() LIMIT 1
                """.format(','.join('?' for _ in asked_ids) if asked_ids else '0'), (domain, *asked_ids) if asked_ids else ())
                row = cursor.fetchone()
                
            conn.close()
            
            if row:
                next_question_text = row["question_text"]
                next_question_id = row["id"]
                next_difficulty = row["difficulty"]
            else:
                finished = True
                
    # Update session overall score if finished
    if finished:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT AVG(correctness_score) FROM responses WHERE session_id = ?", (session_id,))
        avg_score = cursor.fetchone()[0] or 0.0
        cursor.execute("UPDATE sessions SET overall_score = ? WHERE session_id = ?", (round(avg_score, 1), session_id))
        conn.commit()
        conn.close()
        
    return jsonify({
        "finished": finished,
        "evaluation": eval_result,
        "next_question_text": next_question_text,
        "next_question_id": next_question_id,
        "next_difficulty": next_difficulty,
        "question_number": question_number + 1
    })
@app.route('/api/get-session-results/<session_id>', methods=['GET'])


def get_session_results(session_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get session details
    cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
    session_row = cursor.fetchone()
    
    if not session_row:
        conn.close()
        return jsonify({"error": "Session not found"}), 404
        
    # Get response details
    cursor.execute("""
        SELECT r.*, q.question_text, q.ideal_answer, q.domain
        FROM responses r
        LEFT JOIN questions q ON r.question_id = q.id
        WHERE r.session_id = ?
        ORDER BY r.id ASC
    """, (session_id,))
    response_rows = cursor.fetchall()
    conn.close()
    
    responses = []
    
    # Summarize scores
    correctness_scores = []
    relevance_scores = []
    eye_contact_scores = []
    speaking_speeds = []
    filler_words = []
    stress_scores = []
    
    for row in response_rows:
        # Handle resume question text fallback
        q_text = row["question_text"]
        ideal_ans = row["ideal_answer"]
        
        # Check if custom resume question text was cached
        if not q_text and session_id in RESUME_QUESTIONS_CACHE:
            r_questions = RESUME_QUESTIONS_CACHE[session_id]["questions"]
            q_item = next((q for q in r_questions if q["id"] == row["question_id"]), None)
            if q_item:
                q_text = q_item["question_text"]
                ideal_ans = q_item["ideal_answer"]
                
        r_data = {
            "question_text": q_text or "Resume Specific Question",
            "ideal_answer": ideal_ans or "Ideal response describing experience.",
            "candidate_answer": row["candidate_answer"],
            "correctness_score": row["correctness_score"],
            "relevance_score": row["relevance_score"],
            "completeness_score": row["completeness_score"],
            "feedback": row["feedback"],
            "eye_contact_score": row["eye_contact_score"],
            "speaking_speed": row["speaking_speed"],
            "filler_words_count": row["filler_words_count"],
            "stress_score": row["stress_score"]
        }
        responses.append(r_data)
        
        correctness_scores.append(row["correctness_score"])
        relevance_scores.append(row["relevance_score"])
        eye_contact_scores.append(row["eye_contact_score"])
        speaking_speeds.append(row["speaking_speed"])
        filler_words.append(row["filler_words_count"])
        stress_scores.append(row["stress_score"])
        
    if not responses:
        return jsonify({"error": "No responses found for this session."}), 400
        
    # Calculate metrics
    tech_score = round(np.mean(correctness_scores), 1)
    eye_contact_avg = round(np.mean(eye_contact_scores), 1)
    stress_avg = round(np.mean(stress_scores), 1)
    
    # Communication score: penalize excessive filler words and extreme speeds
    # Ideal speed: 120-150 WPM. Penalize if < 90 or > 180.
    avg_speed = np.mean(speaking_speeds)
    speed_penalty = 0.0
    if avg_speed < 90:
        speed_penalty = (90 - avg_speed) * 0.8
    elif avg_speed > 160:
        speed_penalty = (avg_speed - 160) * 0.8
        
    total_fillers = sum(filler_words)
    filler_penalty = min(25.0, total_fillers * 2.5) # 2.5% penalty per filler word, capped at 25%
    
    comm_score = max(0.0, round(100.0 - speed_penalty - filler_penalty, 1))
    
    # Overall score calculation:
    # 40% Technical Knowledge, 25% Communication, 20% Eye Contact, 15% Stress Management
    overall_score = round((tech_score * 0.4) + (comm_score * 0.25) + (eye_contact_avg * 0.20) + (max(0, 100 - stress_avg) * 0.15), 1)
    
    # Recommendation insights
    recommendations = []
    if tech_score < 70:
        recommendations.append("Enhance technical vocabulary. Study key architectural patterns and terms relevant to your domain.")
    if comm_score < 75:
        recommendations.append("Practice structural pacing. Use pause techniques to reduce the frequency of filler words (like 'um' and 'like').")
    if eye_contact_avg < 75:
        recommendations.append("Improve eye contact. Position your camera at eye level and look directly at it when speaking.")
    if stress_avg > 50:
        recommendations.append("Work on stress handling. Take a deliberate 2-second pause before answering to lower response hesitation.")
        
    if not recommendations:
        recommendations.append("Fantastic performance! Keep maintaining this high level of posture and technical depth.")
        
    return jsonify({
        "session_id": session_id,
        "domain": session_row["domain"],
        "stress_mode": session_row["stress_mode"],
        "coach_mode": session_row["coach_mode"],
        "created_at": session_row["created_at"],
        "overall_score": overall_score,
        "metrics": {
            "technical": tech_score,
            "communication": comm_score,
            "behavioral": eye_contact_avg,
            "stress_handling": round(max(0, 100 - stress_avg), 1),
            "speaking_speed_avg": round(avg_speed, 1),
            "total_filler_words": total_fillers
        },
        "responses": responses,
        "recommendations": recommendations
    })
@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/login')
def login_page():
    return render_template('login.html')
@app.route('/test123')
def test123():
    return "TEST ROUTE WORKS"
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)