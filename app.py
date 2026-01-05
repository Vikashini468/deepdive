from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
import whisper
import PyPDF2
from io import BytesIO
import requests
from typing import List
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'

# Add JSON filter for Jinja2
@app.template_filter('from_json')
def from_json_filter(value):
    try:
        return json.loads(value) if value else []
    except:
        return []

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Ollama configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"
TIMEOUT = 60

# Remove Whisper - use browser speech recognition
# whisper_model = whisper.load_model("base")

def init_db():
    conn = sqlite3.connect('interviewer.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL)''')
    
    # Interview sessions table
    c.execute('''CREATE TABLE IF NOT EXISTS interviews
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  resume_text TEXT,
                  branch TEXT,
                  skills TEXT,
                  intro_score INTEGER,
                  q1_score INTEGER DEFAULT 0,
                  q2_score INTEGER DEFAULT 0,
                  q3_score INTEGER DEFAULT 0,
                  q4_score INTEGER DEFAULT 0,
                  q5_score INTEGER DEFAULT 0,
                  total_score INTEGER DEFAULT 0,
                  strengths TEXT,
                  weaknesses TEXT,
                  completed BOOLEAN DEFAULT FALSE,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    conn.commit()
    conn.close()

import os
from groq import Groq

# Groq configuration
client = Groq(api_key=os.getenv('GROQ_API_KEY'))

def _call_ollama(prompt: str) -> str:
    try:
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1024
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"Groq call failed: {e}")

def evaluate_intro_with_llm(intro_text: str, resume_text: str, branch: str, skills: List[str]) -> str:
    prompt = f"""
You are a strict technical interviewer.

Candidate branch: {branch}
Candidate skills: {', '.join(skills)}

Resume:
{resume_text}

Candidate introduction:
{intro_text}

Evaluate the introduction.

Rules:
- Give concise feedback
- Mention relevance, clarity, and missing points
- No greeting
- No questions
- Output ONLY feedback text
"""
    return _call_ollama(prompt)

def generate_branch_question(branch: str, skills: List[str], level: str) -> str:
    prompt = f"""
You are a strict technical interviewer for {branch} field.

Candidate's Field: {branch}
Candidate's Skills: {', '.join(skills)}
Difficulty Level: {level}

IMPORTANT RULES:
- Ask ONLY questions related to {branch} field
- For ECE/Electronics: Ask about circuits, signals, communication, embedded systems
- For Mechanical: Ask about thermodynamics, mechanics, manufacturing
- For Civil: Ask about structures, materials, construction
- For Chemical: Ask about processes, reactions, unit operations
- DO NOT ask computer science questions unless the field is Computer Science
- Question must be conceptual and answerable verbally
- Difficulty: {level}
- Output ONLY the question

Generate one {branch}-specific question now:
"""
    return _call_ollama(prompt)

def evaluate_answer_with_llm(question: str, answer: str, branch: str, level: str) -> str:
    prompt = f"""
You are a strict technical interviewer.

Branch: {branch}
Difficulty: {level}

Question:
{question}

Candidate answer:
{answer}

Scoring guide (MANDATORY — follow exactly):
- 0/10 → No relation to the question
- 4/10 → Mentions key terms but shows incorrect understanding
- 6/10 → Partially correct but missing important aspects
- 8/10 → Mostly correct with minor gaps
- 10/10 → Fully correct and appropriately deep

Evaluation rules:
- Choose ONLY one score from: 0, 4, 6, 8, 10
- If the answer has ANY meaningful relevance, score MUST be at least 4
- Do NOT invent new scores
- Do NOT explain the scoring guide

Feedback rules:
- Briefly mention correctness
- Mention depth relative to the given difficulty
- Give EXACTLY ONE improvement suggestion
- Do NOT reveal the correct answer
- No greetings
- No follow-up questions

Output format (STRICT — no extra text):
Score: X/10
Feedback: <text>
"""
    return _call_ollama(prompt)

def generate_strengths_weaknesses(total_score: int, branch: str, skills: List[str]) -> tuple:
    """Generate strengths and weaknesses using Ollama"""
    prompt = f"""
Based on interview performance, generate analysis:

Score: {total_score}/50
Branch: {branch}
Skills: {', '.join(skills)}

Generate exactly 5 strengths and 5 weaknesses as bullet points.

Output format (STRICT):
Strengths:
• [strength 1]
• [strength 2]
• [strength 3]
• [strength 4]
• [strength 5]

Weaknesses:
• [weakness 1]
• [weakness 2]
• [weakness 3]
• [weakness 4]
• [weakness 5]
"""
    
    response = _call_ollama(prompt)
    
    # Parse response
    lines = response.strip().split('\n')
    strengths = []
    weaknesses = []
    current_section = None
    
    for line in lines:
        line = line.strip()
        if line.startswith('Strengths:'):
            current_section = 'strengths'
        elif line.startswith('Weaknesses:'):
            current_section = 'weaknesses'
        elif line.startswith('•') and current_section:
            text = line[1:].strip()
            if current_section == 'strengths' and len(strengths) < 5:
                strengths.append(text)
            elif current_section == 'weaknesses' and len(weaknesses) < 5:
                weaknesses.append(text)
    
    return strengths, weaknesses

def extract_skills_and_branch(resume_text: str) -> tuple:
    """Extract skills and branch from resume using Ollama"""
    prompt = f"""
Analyze this resume and identify the candidate's engineering field and technical skills.

Resume:
{resume_text}

IMPORTANT:
- Identify the correct engineering branch (ECE/Electronics, Mechanical, Civil, Chemical, Computer Science, etc.)
- Extract skills relevant to that specific field
- For ECE: Include circuit design, signal processing, communication systems, embedded systems, VLSI, etc.
- For Mechanical: Include CAD, manufacturing, thermodynamics, mechanics, etc.
- For Civil: Include structural analysis, construction, materials, surveying, etc.

Output format (STRICT):
Branch: <exact_field_name>
Skills: <skill1>, <skill2>, <skill3>, ...
"""
    
    response = _call_ollama(prompt)
    
    # Parse response
    lines = response.strip().split('\n')
    branch = "General"
    skills = []
    
    for line in lines:
        if line.startswith('Branch:'):
            branch = line.split(':', 1)[1].strip()
        elif line.startswith('Skills:'):
            skills_str = line.split(':', 1)[1].strip()
            skills = [skill.strip() for skill in skills_str.split(',') if skill.strip()]
    
    return branch, skills

def extract_text_from_pdf(file):
    pdf_reader = PyPDF2.PdfReader(BytesIO(file.read()))
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        conn = sqlite3.connect('interviewer.db')
        c = conn.cursor()
        
        try:
            c.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                     (username, email, generate_password_hash(password)))
            conn.commit()
            flash('Registration successful!')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists!')
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('interviewer.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('upload_resume'))
        else:
            flash('Invalid credentials!')
    
    return render_template('login.html')

@app.route('/upload_resume', methods=['GET', 'POST'])
def upload_resume():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        file = request.files['resume']
        
        if file and file.filename.endswith('.pdf'):
            resume_text = extract_text_from_pdf(file)
            
            # Extract skills and branch using AI
            branch, skills = extract_skills_and_branch(resume_text)
            
            conn = sqlite3.connect('interviewer.db')
            c = conn.cursor()
            c.execute("INSERT INTO interviews (user_id, resume_text, branch, skills) VALUES (?, ?, ?, ?)",
                     (session['user_id'], resume_text, branch, json.dumps(skills)))
            interview_id = c.lastrowid
            conn.commit()
            conn.close()
            
            session['interview_id'] = interview_id
            return redirect(url_for('chat'))
        else:
            flash('Please upload a valid PDF file!')
    
    return render_template('upload_resume.html')

@app.route('/chat')
def chat():
    if 'user_id' not in session or 'interview_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('interviewer.db')
    c = conn.cursor()
    c.execute("SELECT * FROM interviews WHERE id = ?", (session['interview_id'],))
    interview = c.fetchone()
    conn.close()
    
    return render_template('chat.html', interview=interview)

@app.route('/process_audio', methods=['POST'])
def process_audio():
    # Use browser speech recognition instead
    return jsonify({'error': 'Use browser speech recognition'}), 400

@app.route('/evaluate_intro', methods=['POST'])
def evaluate_intro():
    data = request.json
    intro_text = data['intro_text']
    
    conn = sqlite3.connect('interviewer.db')
    c = conn.cursor()
    c.execute("SELECT resume_text, branch, skills FROM interviews WHERE id = ?", (session['interview_id'],))
    interview = c.fetchone()
    
    if interview:
        resume_text, branch, skills = interview
        skills_list = json.loads(skills)
        
        feedback = evaluate_intro_with_llm(intro_text, resume_text, branch, skills_list)
        
        # Generate first technical question (easy)
        question = generate_branch_question(branch, skills_list, "easy")
        
        return jsonify({
            'feedback': feedback,
            'next_question': question,
            'question_number': 1,
            'difficulty': 'easy'
        })
    
    conn.close()
    return jsonify({'error': 'Interview not found'}), 404

@app.route('/evaluate_answer', methods=['POST'])
def evaluate_answer():
    data = request.json
    question = data['question']
    answer = data['answer']
    question_number = data['question_number']
    difficulty = data['difficulty']
    
    conn = sqlite3.connect('interviewer.db')
    c = conn.cursor()
    c.execute("SELECT branch, skills FROM interviews WHERE id = ?", (session['interview_id'],))
    interview = c.fetchone()
    
    if interview:
        branch, skills = interview
        skills_list = json.loads(skills)
        
        evaluation = evaluate_answer_with_llm(question, answer, branch, difficulty)
        
        # Extract score from evaluation
        score_line = [line for line in evaluation.split('\n') if line.startswith('Score:')]
        score = 0
        if score_line:
            score = int(score_line[0].split('/')[0].split(':')[1].strip())
        
        # Update database with score
        c.execute(f"UPDATE interviews SET q{question_number}_score = ? WHERE id = ?", 
                 (score, session['interview_id']))
        conn.commit()
        
        # Generate next question or finish
        if question_number < 5:
            next_difficulty = ['easy', 'easy', 'medium', 'medium', 'hard'][question_number]
            next_question = generate_branch_question(branch, skills_list, next_difficulty)
            
            conn.close()
            return jsonify({
                'evaluation': evaluation,
                'score': score,
                'next_question': next_question,
                'question_number': question_number + 1,
                'difficulty': next_difficulty
            })
        else:
            # Calculate final results
            c.execute("SELECT q1_score, q2_score, q3_score, q4_score, q5_score FROM interviews WHERE id = ?", 
                     (session['interview_id'],))
            scores = c.fetchone()
            total_score = sum(scores)
            
            # Get interview details for analysis
            c.execute("SELECT branch, skills FROM interviews WHERE id = ?", (session['interview_id'],))
            interview_data = c.fetchone()
            branch, skills_json = interview_data
            skills = json.loads(skills_json)
            
            # Generate strengths and weaknesses using AI
            strengths, weaknesses = generate_strengths_weaknesses(total_score, branch, skills)
            
            c.execute("UPDATE interviews SET total_score = ?, strengths = ?, weaknesses = ?, completed = TRUE WHERE id = ?",
                     (total_score, json.dumps(strengths), json.dumps(weaknesses), session['interview_id']))
            conn.commit()
            conn.close()
            
            return jsonify({
                'evaluation': evaluation,
                'score': score,
                'finished': True
            })
    
    conn.close()
    return jsonify({'error': 'Interview not found'}), 404

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('interviewer.db')
    c = conn.cursor()
    c.execute("SELECT id, user_id, resume_text, branch, skills, intro_score, q1_score, q2_score, q3_score, q4_score, q5_score, total_score, strengths, weaknesses, completed FROM interviews WHERE user_id = ? AND completed = TRUE ORDER BY id DESC", 
             (session['user_id'],))
    interviews = c.fetchall()
    conn.close()
    
    return render_template('dashboard.html', interviews=interviews)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)