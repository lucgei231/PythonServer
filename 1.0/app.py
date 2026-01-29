import os
import json
import random
import datetime
import re
import sys
import threading

from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_file

from flask_socketio import SocketIO, emit, join_room, leave_room

from non_static.quiz import read_quiz, get_random_question, validate_answer  # adjust imports as needed

from non_static.utils import read_uploaded_json, write_uploaded_json

app = Flask(__name__, template_folder="templates")
app.secret_key = "your_random_secret_key_here"

socketio = SocketIO(app, async_mode='gevent')
from werkzeug.utils import secure_filename

# Configuration for file uploads
ALLOWED_EXTENSIONS = {'.png', '.webp', '.jpg', '.jpeg'}
MAX_IMAGES_PER_QUIZ = 20
from werkzeug.utils import secure_filename

# Configuration for file uploads
ALLOWED_EXTENSIONS = {'.png', '.webp', '.jpg', '.jpeg'}
MAX_FILE_SIZE = 300 * 1024 * 1024  # 300MB
MAX_IMAGES_PER_QUIZ = 20
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "UploadedImages")

# Create uploads folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
print(datetime.datetime.now(), "Logs directory set up at", logs_dir)

# Use a fixed filename for all print() output.
# log_filename = os.path.join(os.path.dirname(__file__), "logs", "print.txt")

class Logger(object):
    def __init__(self, logfile):
        self.terminal = sys.stdout
        self.log = open(logfile, "a", encoding="utf-8")
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()
    def flush(self):
        self.terminal.flush()
        self.log.flush()

# sys.stdout = Logger(log_filename)
print(datetime.datetime.now(), "Starting Server with logger.")

def get_client_ip():
    forwarded_for = request.headers.get('X-Forwarded-For')
    return forwarded_for.split(",")[0].strip() if forwarded_for else request.remote_addr

def is_mobile():
    user_agent = request.headers.get('User-Agent', '').lower()
    mobile_keywords = ['mobile', 'android', 'iphone', 'ipad', 'ipod', 'blackberry', 'windows phone']
    return any(keyword in user_agent for keyword in mobile_keywords)

@app.before_request
def log_connection():
    ip = get_client_ip()
    # Optional: Add connection logging here


@app.after_request
def log_disconnection(response):
    ip = get_client_ip()
    # Optional: Add disconnection logging here
    print(datetime.datetime.now(), ip, "connection closed.")
    return response

# Ensure the data directory exists.
data_dir = os.path.join(os.path.dirname(__file__), "data")
if not os.path.exists(data_dir):
    os.makedirs(data_dir)
banned_file = os.path.join(data_dir, "banned.txt")

def load_banned_ips():
    banned = {}
    if os.path.exists(banned_file):
        with open(banned_file, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(' ', 1)
                if len(parts) == 2:
                    banned_ip, reason = parts
                    banned[banned_ip.strip()] = reason.strip()
    return banned

def save_banned_ips(banned):
    with open(banned_file, "w", encoding="utf-8") as f:
        for ip, reason in banned.items():
            f.write(f"{ip.strip()} {reason}\n")

# Global dictionary to track banned IPs.
banned_ips = load_banned_ips()

# Global dictionary for Kahoot-style sessions: code -> {'host_sid': sid, 'players': [sids], 'quiz_name': name, 'questions': [], 'current_q': 0}
sessions = {}
control_to_game = {}



@app.before_request
def check_banned_ip():
    ip = get_client_ip()
    print(datetime.datetime.now(), ip, "accessing", request.path)
    # Allow log-related endpoints even if banned.
    allowed_paths = ['/logs', '/logs-content', '/unban-ip', '/log-command']
    if request.path in allowed_paths:
        print(datetime.datetime.now(), ip, "request path", request.path, "is allowed even if banned.")
        return
    if ip in banned_ips:
        reason = banned_ips[ip]
        print(datetime.datetime.now(), ip, "is banned for reason:", reason)
        return render_template("error.html", message=f"IP {ip} banned: {reason}"), 403


@app.route('/ban-ip', methods=['GET', 'POST'])
def ban_ip():
    ip = get_client_ip()
    print(datetime.datetime.now(), ip, "entered /ban-ip route with method", request.method)
    if request.method == "GET":
        protocol = request.environ.get("SERVER_PROTOCOL", "HTTP/1.1")
        message = f"GET {request.path} {protocol} Not Allowed: Use POST"
        print(datetime.datetime.now(), ip, "GET request at /ban-ip; returning error message:", message)
        return render_template("error.html", message=message), 405
    data = request.get_json()
    print(datetime.datetime.now(), ip, "received data in ban-ip:", data)
    ip_to_ban = data.get('ip', '').strip()   # <<-- Trim here
    reason = data.get('reason', 'No reason provided.')
    if ip_to_ban:
        banned_ips[ip_to_ban] = reason
        save_banned_ips(banned_ips)
        print(datetime.datetime.now(), ip, "banned IP", ip_to_ban, "for reason:", reason)
        return render_template("error.html", message=f"IP {ip_to_ban} banned: {reason}")
    else:
        print(datetime.datetime.now(), ip, "no IP provided in ban-ip request.")
    return jsonify({'error': 'No IP provided.'}), 400

@app.route('/unban-ip', methods=['GET', 'POST'])
def unban_ip():
    ip = get_client_ip()
    print(datetime.datetime.now(), ip, "entered /unban-ip route with method", request.method)
    if request.method == "GET":
        protocol = request.environ.get("SERVER_PROTOCOL", "HTTP/1.1")
        message = f"GET {request.path} {protocol} Not Allowed: Use POST"
        print(datetime.datetime.now(), ip, "GET request at /unban-ip; returning error message:", message)
        return render_template("error.html", message=message), 405
    data = request.get_json() or {}
    print(datetime.datetime.now(), ip, "received data in unban-ip:", data)
    ip_to_unban = data.get('ip', '').strip()  # <<-- Also trim here
    print(datetime.datetime.now(), ip, "attempting to unban IP:", repr(ip_to_unban))
    print(datetime.datetime.now(), ip, "banned IPs currently:", list(banned_ips.keys()))
    if ip_to_unban in banned_ips:
        del banned_ips[ip_to_unban]
        save_banned_ips(banned_ips)
        print(datetime.datetime.now(), ip, "unbanned IP:", ip_to_unban)
        return jsonify({'status': f'IP {ip_to_unban} unbanned.'})
    else:
        print(datetime.datetime.now(), ip, "IP", repr(ip_to_unban), "not found in banned list.")
        return jsonify({'error': 'IP not found in banned list.'}), 404

@app.route('/log-command', methods=['GET', 'POST'])
def log_command():
    ip = get_client_ip()
    print(datetime.datetime.now(), ip, "entered /log-command with method", request.method)
    if request.method == "GET":
        protocol = request.environ.get("SERVER_PROTOCOL", "HTTP/1.1")
        message = f"GET {request.path} {protocol} Not Allowed: Use POST"
        print(datetime.datetime.now(), ip, "GET request at /log-command; returning error message:", message)
        return render_template("error.html", message=message), 405
    data = request.get_json()
    print(datetime.datetime.now(), ip, "data received in /log-command:", data)
    command = data.get('command', '').strip()
    if command:
        print(datetime.datetime.now(), ip, "logging command:", "> " + command)
        sys.stdout.flush()
    return jsonify({'status': 'logged'})

@app.route('/kick', methods=['POST', 'GET'])
def kick():
    if request.method == 'GET':
        return render_template("error.html", message="Error: Use POST"), 405
    
    data = request.get_json() or {}
    target_ip = data.get("ip", "").strip()
    if not target_ip:
        return jsonify({'error': 'Target IP must be provided.'}), 400
    reason = data.get('reason', 'Kicked for 5 seconds.')
    banned_ips[target_ip] = reason
    save_banned_ips(banned_ips)
    print(datetime.datetime.now(), target_ip, f"Kicked for 5 seconds: {reason}")
    
    # Schedule to unban the target IP after 5 seconds.
    def unban_after_kick():
        if target_ip in banned_ips and banned_ips[target_ip] == reason:
            del banned_ips[target_ip]
            save_banned_ips(banned_ips)
            print(datetime.datetime.now(), target_ip, "automatically unbanned after kick.")
    timer = threading.Timer(5.0, unban_after_kick)
    timer.start()
    
    return jsonify({'status': f'IP {target_ip} kicked for 5 seconds.'})

@app.route('/')
def home():
    print("DEBUG:", datetime.datetime.now(), "Entered home route.")
    try:
        quiz_dir = os.path.join(os.path.dirname(__file__), "non_static", "quiz")
        quizzes = []
        if os.path.exists(quiz_dir):
            for file in os.listdir(quiz_dir):
                if file.endswith(".txt"):
                    quiz_name = os.path.splitext(file)[0]
                    quizzes.append(quiz_name)
                    print("DEBUG: Found quiz:", quiz_name)
        # Load uploaded quizzes for current IP
        uploaded_file = os.path.join(os.path.dirname(__file__), "data", "uploaded.json")
        user_uploaded = []
        ip = get_client_ip()
        if os.path.exists(uploaded_file):
            with open(uploaded_file, "r", encoding="utf-8") as f:
                uploaded_data = json.load(f)
            user_uploaded = uploaded_data.get(ip, [])
            print("DEBUG: Uploaded quizzes for IP", ip, ":", user_uploaded)
        # Special case: 127.0.0.1 has full access to all quizzes
        if ip == "127.0.0.1":
            user_uploaded = quizzes
        return render_template('home.html', quizzes=quizzes, user_uploaded=user_uploaded), 200
    except Exception as e:
        print("DEBUG: Error in home route:", str(e))
        return f"Error in home route: {str(e)}", 500

@app.route('/robots.txt')
def robots():
    return '''<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            font-family: Arial, sans-serif;
        }
        h1 {
            font-size: 15rem;
            color: white;
            text-shadow: 5px 5px 20px rgba(0,0,0,0.5);
            margin: 0;
            text-align: center;
        }
    </style>
</head>
<body>
    <h1>LOL BOT</h1>
</body>
</html>''', 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/get_avatars', methods=['GET'])
def get_avatars():
    avatars_dir = os.path.join(os.path.dirname(__file__), "data", "avatars")
    avatars = []
    if os.path.exists(avatars_dir):
        for file in os.listdir(avatars_dir):
            if file.lower().endswith('.png'):
                avatar_name = os.path.splitext(file)[0]
                avatars.append(avatar_name)
    return jsonify({'avatars': sorted(avatars)})

@app.route('/data/avatars/<avatar_name>.png')
def get_avatar_image(avatar_name):
    avatars_dir = os.path.join(os.path.dirname(__file__), "data", "avatars")
    avatar_file = os.path.join(avatars_dir, f"{avatar_name}.png")
    if os.path.exists(avatar_file):
        return send_file(avatar_file, mimetype='image/png')
    else:
        return "Avatar not found", 404

@app.route('/data/icon.png')
def get_icon():
    icon_file = os.path.join(os.path.dirname(__file__), "data", "icon.png")
    if os.path.exists(icon_file):
        return send_file(icon_file, mimetype='image/png')
    else:
        return "Icon not found", 404

@app.route('/deletequiz', methods=['GET', 'POST'])
def deletequiz():
    ip = get_client_ip()
    if request.method == "GET":
        # Expect the quiz name as a query parameter: ?quiz=quizname
        quiz = request.args.get("quiz")
        if not quiz:
            return redirect(url_for("home"))
        print( ip, " is confirming if they want to delete", quiz)
        # Check if the quiz exists in the uploaded quizzes for this IP.
        return render_template("deletequiz_confirm.html", quiz=quiz)
    
    # POST: actually delete the quiz.
    quiz_to_delete = request.form.get("quiz")
    print(ip, " is deleting", quiz_to_delete)
    uploaded_file = os.path.join(os.path.dirname(__file__), "data", "uploaded.json")
    if os.path.exists(uploaded_file):
        with open(uploaded_file, "r", encoding="utf-8") as f:
            uploaded_data = json.load(f)
    else:
        uploaded_data = {}
    user_uploaded = uploaded_data.get(ip, [])
    
    print(ip, " is confirming if they want to delete", quiz_to_delete)
    # Check if the quiz exists in the uploaded quizzes for this IP.
    if quiz_to_delete in user_uploaded:
        print(ip, " is deleting", quiz_to_delete)
        quiz_dir = os.path.join(os.path.dirname(__file__), "non_static", "quiz")
        quiz_file = os.path.join(quiz_dir, quiz_to_delete + ".txt")
        if os.path.exists(quiz_file):
            os.remove(quiz_file)
        user_uploaded.remove(quiz_to_delete)
        uploaded_data[ip] = user_uploaded
        with open(uploaded_file, "w", encoding="utf-8") as f:
            json.dump(uploaded_data, f)
    
    # Redirect to home page after deletion.
    print(ip, " is redirecting to home after deleting", quiz_to_delete)
    return redirect(url_for("home"))

@app.route('/addquiz', methods=['GET', 'POST'])
def addquiz():
    client_ip = get_client_ip()
    if request.method == 'POST':
        uploaded_file = request.files.get("quiz_file")
        if uploaded_file:
            content = uploaded_file.read().decode("utf-8")
            # Validate and save the file
            quiz_dir = os.path.join(os.path.dirname(__file__), "non_static", "quiz")
            if not os.path.exists(quiz_dir):
                os.makedirs(quiz_dir)
            file_path = os.path.join(quiz_dir, uploaded_file.filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            # Update uploaded.json
            uploaded_data = read_uploaded_json()
            if client_ip not in uploaded_data:
                uploaded_data[client_ip] = []
            if uploaded_file.filename not in uploaded_data[client_ip]:
                uploaded_data[client_ip].append(uploaded_file.filename)
            write_uploaded_json(uploaded_data)
            
            return render_template("addquiz.html", message="Quiz uploaded successfully!")
    return render_template("addquiz.html")

    @app.route('/upload_quiz_image/<quiz_name>', methods=['POST'])
    def upload_quiz_image(quiz_name):
        """Upload image for a quiz with validation"""
        client_ip = get_client_ip()
    
        try:
            # Check if file is in request
            if 'image' not in request.files:
                return jsonify({'error': 'No image file provided'}), 400
        
            image_file = request.files['image']
        
            if image_file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
        
            # Get file extension
            filename = secure_filename(image_file.filename)
            file_ext = os.path.splitext(filename)[1].lower()
        
            # Validate file extension
            if file_ext not in ALLOWED_EXTENSIONS:
                return jsonify({'error': f'File type not allowed. Only {", ".join(ALLOWED_EXTENSIONS)} are supported'}), 400
        
            # Check file size before saving
            image_file.seek(0, os.SEEK_END)
            file_size = image_file.tell()
            image_file.seek(0)
        
            if file_size > MAX_FILE_SIZE:
                return jsonify({'error': f'File too large. Maximum size is 300MB'}), 400
        
            # Create quiz-specific directory
            quiz_image_dir = os.path.join(UPLOAD_FOLDER, secure_filename(quiz_name))
            if not os.path.exists(quiz_image_dir):
                os.makedirs(quiz_image_dir)
        
            # Check image count
            existing_images = os.listdir(quiz_image_dir)
            if len(existing_images) >= MAX_IMAGES_PER_QUIZ:
                return jsonify({'error': f'Maximum {MAX_IMAGES_PER_QUIZ} images per quiz reached'}), 400
        
            # Generate unique filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            new_filename = f"{timestamp}{file_ext}"
            file_path = os.path.join(quiz_image_dir, new_filename)
        
            # Save file
            image_file.save(file_path)

            # Update per-question images metadata if question_index provided
            images_meta_dir = os.path.join(os.path.dirname(__file__), "non_static", "question")
            if not os.path.exists(images_meta_dir):
                os.makedirs(images_meta_dir)
            images_meta_file = os.path.join(images_meta_dir, f"{quiz_name}_images.json")

            question_index = request.form.get('question_index')
            try:
                if os.path.exists(images_meta_file):
                    with open(images_meta_file, 'r', encoding='utf-8') as mf:
                        images_meta = json.load(mf)
                else:
                    images_meta = {}
            except Exception:
                images_meta = {}

            if question_index is not None and question_index != '':
                key = str(int(question_index))
                images_meta.setdefault(key, [])
                images_meta[key].append(new_filename)
                try:
                    with open(images_meta_file, 'w', encoding='utf-8') as mf:
                        json.dump(images_meta, mf)
                except Exception as e:
                    print(datetime.datetime.now(), client_ip, f"Failed to update images metadata: {e}")

            # Return image URL
            image_url = f"/UploadedImages/{secure_filename(quiz_name)}/{new_filename}"
            print(datetime.datetime.now(), client_ip, f"Uploaded image for quiz '{quiz_name}': {new_filename}")

            return jsonify({
                'success': True,
                'url': image_url,
                'filename': new_filename
            }), 200
    
        except Exception as e:
            print(datetime.datetime.now(), client_ip, f"Error uploading image: {str(e)}")
            return jsonify({'error': f'Upload failed: {str(e)}'}), 500

    @app.route('/UploadedImages/<path:filepath>')
    def serve_uploaded_image(filepath):
        """Serve uploaded images"""
        try:
            file_path = os.path.join(UPLOAD_FOLDER, filepath)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                return send_file(file_path)
            return jsonify({'error': 'Image not found'}), 404
        except Exception as e:
            return jsonify({'error': 'Failed to serve image'}), 500

@app.route('/quiz/<quiz_name>', methods=['GET'])
def get_quiz_json(quiz_name):
    # quiz_name is defined from the URL.
    session['quiz_name'] = quiz_name
    client_ip = get_client_ip()
    print(client_ip, "is playing", quiz_name)
    
    try:
        questions = read_quiz(quiz_name)
    except Exception as e:
        print(client_ip, "error reading quiz:", str(e))
        return f"Error reading quiz: {str(e)}", 500

    if not questions:
        return "No questions available.", 404

    # Load current index for this client.
    question_file = os.path.join(os.path.dirname(__file__), "non_static", "question", f"{quiz_name}.json")
    try:
        with open(question_file, "r", encoding="utf-8") as f:
            question_data = json.load(f)
    except Exception as e:
        question_data = {}
    if not isinstance(question_data, dict):
        question_data = {}

    current_index = question_data.get(client_ip, 0)
    
    # If the current question index is out-of-range, render finish.html
    if current_index >= len(questions):
        print(client_ip, f"Quiz '{quiz_name}' finished for client {client_ip}. Rendering finish.html.")
        return render_template("finish.html", quiz_name=quiz_name)
    
    # Otherwise, show the current question.
    question = questions[current_index]
    # Attach any images for this question (by index) if present
    images_meta_file = os.path.join(os.path.dirname(__file__), "non_static", "question", f"{quiz_name}_images.json")
    try:
        if os.path.exists(images_meta_file):
            with open(images_meta_file, 'r', encoding='utf-8') as mf:
                images_meta = json.load(mf)
        else:
            images_meta = {}
    except Exception:
        images_meta = {}
    imgs = images_meta.get(str(current_index), [])
    if imgs:
        question['images'] = [f"/UploadedImages/{quiz_name}/{fname}" for fname in imgs]
    display_index = current_index + 1
    quiz_total = len(questions)
    session['current_question_name'] = question.get('question', 'Unknown Question')
    
    return render_template("quiz.html",
                           quiz_name=quiz_name,
                           question=question,
                           question_index=display_index,
                           quiz_total=quiz_total)

@app.route('/api/quiz/<quiz_name>', methods=['GET'])
def get_quiz_data(quiz_name):
    try:
        questions = read_quiz(quiz_name)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    # Attach images metadata to each question if available
    images_meta_file = os.path.join(os.path.dirname(__file__), "non_static", "question", f"{quiz_name}_images.json")
    try:
        if os.path.exists(images_meta_file):
            with open(images_meta_file, 'r', encoding='utf-8') as mf:
                images_meta = json.load(mf)
        else:
            images_meta = {}
    except Exception:
        images_meta = {}

    for idx, q in enumerate(questions):
        imgs = images_meta.get(str(idx), [])
        if imgs:
            q['images'] = [f"/UploadedImages/{quiz_name}/{fname}" for fname in imgs]

    return jsonify(questions)

@app.route('/editquiz/<quiz_name>', methods=['GET', 'POST'])
def edit_quiz(quiz_name):
    client_ip = get_client_ip()
    quiz_file = os.path.join(os.path.dirname(__file__), "non_static", "quiz", f"{quiz_name}.txt")
    question_file = os.path.join(os.path.dirname(__file__), "non_static", "question", f"{quiz_name}.json")
    
    if request.method == 'GET':
        # Read quiz text content.
        print(client_ip, "is currently editing", quiz_name)
        try:
            with open(quiz_file, "r", encoding="utf-8") as f:
                quiz_content = f.read()
        except Exception as e:
            quiz_content = ""
            print(client_ip, "Got an error while reading the quiz: ", str(e)) 

        return render_template("editquiz.html", quiz_name=quiz_name, quiz_content=quiz_content)
    else:
        # POST: update the quiz text and/or rename
        print(client_ip, "is saving their edits to", quiz_name)
        new_content = request.form.get("quiz_content", "")
        new_quiz_name = request.form.get("new_quiz_name", "").strip()
        use_legacy = request.form.get("use_legacy", "false") == "true"
        
        # Handle rename
        if new_quiz_name and new_quiz_name != quiz_name:
            new_quiz_file = os.path.join(os.path.dirname(__file__), "non_static", "quiz", f"{new_quiz_name}.txt")
            new_question_file = os.path.join(os.path.dirname(__file__), "non_static", "question", f"{new_quiz_name}.json")
            
            try:
                # Rename quiz file
                if os.path.exists(quiz_file):
                    os.rename(quiz_file, new_quiz_file)
                # Rename question file if it exists
                if os.path.exists(question_file):
                    os.rename(question_file, new_question_file)
                # Rename images metadata file if exists
                old_images_meta = os.path.join(os.path.dirname(__file__), "non_static", "question", f"{quiz_name}_images.json")
                new_images_meta = os.path.join(os.path.dirname(__file__), "non_static", "question", f"{new_quiz_name}_images.json")
                if os.path.exists(old_images_meta):
                    os.rename(old_images_meta, new_images_meta)
                # Rename UploadedImages directory for this quiz
                old_images_dir = os.path.join(UPLOAD_FOLDER, secure_filename(quiz_name))
                new_images_dir = os.path.join(UPLOAD_FOLDER, secure_filename(new_quiz_name))
                if os.path.exists(old_images_dir):
                    try:
                        os.rename(old_images_dir, new_images_dir)
                    except Exception as e:
                        print(datetime.datetime.now(), client_ip, f"Failed to rename images dir: {e}")
                
                # Update uploaded.json if needed
                uploaded_data = read_uploaded_json()
                if client_ip in uploaded_data and quiz_name in uploaded_data[client_ip]:
                    uploaded_data[client_ip].remove(quiz_name)
                    if new_quiz_name not in uploaded_data[client_ip]:
                        uploaded_data[client_ip].append(new_quiz_name)
                    write_uploaded_json(uploaded_data)
                
                quiz_name = new_quiz_name
                quiz_file = new_quiz_file
                question_file = new_question_file
                print(client_ip, "Renamed quiz to", quiz_name)
            except Exception as e:
                return f"Error renaming quiz: {str(e)}", 500
        
        # Write updated quiz text
        try:
            with open(quiz_file, "w", encoding="utf-8") as f:
                f.write(new_content)
                print(client_ip, "Saved edits to", quiz_name, " successfully.")
            message = "Quiz updated successfully."
        except Exception as e:
            return f"Error updating quiz text: {str(e)}", 500

        return render_template("editquiz.html", quiz_name=quiz_name, quiz_content=new_content, message=message)

@app.route('/quiz/<quiz_name>/quiz/validate', methods=['POST', 'GET'])
def quiz_validate(quiz_name):
    if request.method == 'GET':
        return render_template("error.html", message="Error: Use POST"), 405
    
    answer = request.json.get('answer', '')
    try:
        print(f"Reading quiz {quiz_name}")
        questions = read_quiz(quiz_name)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    if not questions:
        return jsonify({'error': 'No questions found.'}), 404
    print(f"Loading question file for {quiz_name}")
    question_file = os.path.join(os.path.dirname(__file__), "non_static", "question", f"{quiz_name}.json")
    try:
        with open(question_file, "r", encoding="utf-8") as f:
            question_data = json.load(f)
    except Exception as e:
        question_data = {}
    if not isinstance(question_data, dict):
        question_data = {}
    client_ip = get_client_ip()
    print(f"Got ip of {client_ip}")
    current_index = question_data.get(client_ip, 0)
    if current_index >= len(questions):
        current_index = 0
    q = questions[current_index]
    # Convert answer to int for MC questions
    if q['type'] == 'mc':
        try:
            answer = int(answer)
        except ValueError:
            answer = None
    is_correct = validate_answer(q, answer)
    if is_correct:
        new_index = current_index + 1
        if new_index >= len(questions):
            # Signal finish; client-side JS should redirect accordingly.
            return jsonify({'redirect': url_for('finish_quiz', quiz_name=quiz_name)})
        else:
            question_data[client_ip] = new_index
            try:
                print(f"dumping question file")
                with open(question_file, "w", encoding="utf-8") as f:
                    json.dump(question_data, f)
                    print("done dumping question file")
            except Exception as e:
                return jsonify({'error': 'Failed to update question index.'}), 500
            return jsonify({'is_correct': True})
    return jsonify({'is_correct': is_correct})

@app.route('/makequiz', methods=['GET', 'POST'])
def makequiz():
    client_ip = get_client_ip()
    if request.method == 'POST':
        filename = request.form.get("filename")
        quiz_content = request.form.get("quiz_content")
        # Check if it's JSON from modern editor
        try:
            questions = json.loads(quiz_content)
            # Convert to text format
            text_content = ""
            for q in questions:
                text_content += q['question'] + "\n\n"
                if q['type'] == 'mc':
                    for i, ans in enumerate(q['answers']):
                        if i == q['correctIndex']:
                            text_content += "*" + ans + "\n"
                        else:
                            text_content += ans + "\n"
                else:  # typein
                    text_content += q['answers'][0] + "\n"
                text_content += "\n"
            quiz_content = text_content.strip()
        except json.JSONDecodeError:
            # It's legacy text
            pass
        # Save the quiz
        quiz_dir = os.path.join(os.path.dirname(__file__), "non_static", "quiz")
        if not os.path.exists(quiz_dir):
            os.makedirs(quiz_dir)
        quiz_file = os.path.join(quiz_dir, f"{filename}.txt")
        with open(quiz_file, "w", encoding="utf-8") as f:
            f.write(quiz_content)
        
        # Update uploaded.json
        uploaded_data = read_uploaded_json()
        if client_ip not in uploaded_data:
            uploaded_data[client_ip] = []
        if filename not in uploaded_data[client_ip]:
            uploaded_data[client_ip].append(filename)
        write_uploaded_json(uploaded_data)
        
        return render_template("makequiz.html", message="Quiz created successfully!")
    return render_template("makequiz.html")

@app.route('/logs')
def view_logs():
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    logs_content = ""
    # if os.path.exists(logs_dir):
    #     # Get files sorted by name.
    #     files = sorted(os.listdir(logs_dir))
    #     for filename in files:
    #         file_path = os.path.join(logs_dir, filename)
    #         try:
    #             with open(file_path, "r", encoding="utf-8") as f:
    #                 file_content = f.read()
    #             if filename == "print.txt":
    #                 logs_content += file_content + "\n\n"
    #             else:
    #                 # Only show nonempty files.
    #                 if file_content.strip() != "":
    #                     logs_content += f"--- {filename} ---\n{file_content}\n\n"
    #         except Exception as e:
    #             logs_content += f"--- {filename} ---\nError reading file: {str(e)}\n\n"
    # else:
    #     logs_content = "No logs found."
    # print("Detected IP", get_client_ip(), "on /logs")
    return render_template("logs.html", logs_content=logs_content)

@app.route('/logs-content')
def logs_content():
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    logs_text = ""
    # if os.path.exists(logs_dir):
    #     files = sorted(os.listdir(logs_dir))
    #     for filename in files:
    #         file_path = os.path.join(logs_dir, filename)
    #         try:
    #             with open(file_path, "r", encoding="utf-8") as f:
    #                 file_content = f.read()
    #             if filename == "print.txt":
    #                 logs_text += file_content + "\n\n"
    #             else:
    #                 if file_content.strip() != "":
    #                     logs_text += f"--- {filename} ---\n{file_content}\n\n"
    #         except Exception as e:
    #             logs_text += f"--- {filename} ---\nError reading file: {str(e)}\n\n"
    # else:
    #     logs_text = "No logs found."
    return logs_text

@app.route('/quiz/<quiz_name>/answer', methods=['POST', 'GET'])
def submit_answer(quiz_name):
    if request.method == 'GET':
        return render_template("error.html", message="Error: Use POST"), 405
    client_ip = get_client_ip()
    time_taken = request.form.get('time_elapsed', '0')
    question_name = session.get('current_question_name', "Unknown Question")
    
    # (Your code to update the time.txt file goes here)
    # ...

    # Load quiz questions and the JSON tracking file.
    questions = read_quiz(quiz_name)
    question_file = os.path.join(os.path.dirname(__file__), "non_static", "question", f"{quiz_name}.json")
    try:
        with open(question_file, "r", encoding="utf-8") as f:
            question_data = json.load(f)
    except Exception as e:
        question_data = {}
    if not isinstance(question_data, dict):
        question_data = {}

    current_index = question_data.get(client_ip, 0)
    question = questions[current_index]
    answer = request.form.get('answer')
    if question.type == 'mc':
        try:
            answer = int(answer)
        except:
            answer = None
    is_correct = validate_answer(question, answer)
    if not is_correct:
        return redirect(url_for('get_quiz_json', quiz_name=quiz_name) + '?error=incorrect')
    
    new_index = current_index + 1

    print(datetime.datetime.now(), client_ip, f"Quiz '{quiz_name}': current_index={current_index}, new_index={new_index}, total_questions={len(questions)}")
    
    # When the new_index is equal to or exceeds the total questions,
    # redirect to the finish quiz page instead of updating the current index.
    if new_index >= len(questions):
        print(datetime.datetime.now(), client_ip, f"Finished quiz '{quiz_name}'")
        return redirect(url_for('finish_quiz', quiz_name=quiz_name))
    else:
        # Update the question index normally.
        question_data[client_ip] = new_index
        try:
            with open(question_file, "w", encoding="utf-8") as f:
                json.dump(question_data, f)
        except Exception as e:
            print(datetime.datetime.now(), client_ip, "failed to update question index:", str(e))
            return jsonify({'error': 'Failed to update question index.'}), 500
        return redirect(url_for('get_quiz_json', quiz_name=quiz_name))

@app.route('/quiz/<quiz_name>/results')
def quiz_results(quiz_name):
    client_ip = get_client_ip()
    time_file = os.path.join(os.path.dirname(__file__), "data", "time.txt")
    # Parse the time.txt file for the current client's entries for this quiz.
    results = []
    current_ip = None
    current_quiz = None
    if os.path.exists(time_file):
        with open(time_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                # If this line does not start with four spaces, it is either an IP or a quiz name.
                if not line.startswith("    "):
                    # If line is an IP, update current_ip.
                    if re.match(r'\d+\.\d+\.\d+\.\d+', line):
                        current_ip = line
                    else:
                        # Otherwise, it's assumed to be a quiz name.
                        current_quiz = line
                else:
                    # Question line.
                    if current_ip == client_ip and current_quiz == quiz_name:
                        # Remove leading spaces.
                        q_line = line.strip()
                        # Expect the format: "<question text> <time_taken>"
                        results.append(q_line)
    return render_template("results.html", quiz_name=quiz_name, results=results)

@app.route('/quiz/<quiz_name>/save_time', methods=['POST', 'GET'])
def save_time(quiz_name):
    if request.method == 'GET':
        return render_template("error.html", message="Error: Use POST"), 405
    if not quiz_name or quiz_name.strip() == "":
        print(datetime.datetime.now(), "Error: Quiz name is missing in the URL.")
        return jsonify({'error': 'Quiz name is required in the URL.'}), 400
    print("Save time")
    client_ip = get_client_ip()
    print(f"IP: {client_ip}")
    print("request.json")
    if request.is_json:
        time_taken = request.json.get('time_elapsed', '0')
    else:
        time_taken = request.form.get('time_elapsed', '0')
    question_name = session.get('current_question_name', "Unknown Question")
    print(datetime.datetime.now(), client_ip, f"Saving time for quiz '{quiz_name}': {question_name} {time_taken} sec")
    
    time_file = os.path.join(os.path.dirname(__file__), "data", "time.txt")
    data = {}  # structure: {client_ip: {quiz_name: {question_name: time_taken}}}
    
    # Read existing file and parse into dictionary.
    if os.path.exists(time_file):
        with open(time_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        current_ip = None
        current_quiz = None
        for line in lines:
            line = line.rstrip("\n")
            if not line.startswith("    "):
                if current_ip is None or (current_ip and current_quiz):
                    current_ip = line
                    data.setdefault(current_ip, {})
                    current_quiz = None
                else:
                    current_quiz = line
                    data[current_ip].setdefault(current_quiz, {})
            else:
                if current_ip is not None and current_quiz is not None:
                    entry = line.strip()
                    parts = entry.rsplit(" ", 1)
                    if len(parts) == 2:
                        q_name, q_time = parts
                        data[current_ip][current_quiz][q_name] = q_time

    data.setdefault(client_ip, {})
    data[client_ip].setdefault(quiz_name, {})
    data[client_ip][quiz_name][question_name] = time_taken
    print(datetime.datetime.now(), client_ip, f"Updated time for {question_name} in quiz '{quiz_name}' to {time_taken} sec")

    with open(time_file, "w", encoding="utf-8") as f:
        for ip, quizzes in data.items():
            f.write(f"{ip}\n")
            for quiz, questions in quizzes.items():
                f.write(f"{quiz}\n")
                for q, t in questions.items():
                    f.write(f"    {q} {t}\n")
    return jsonify({'status': 'ok', 'quiz_name': quiz_name})

@app.route('/quiz/<quiz_name>/finish')
def finish_quiz(quiz_name):
    # Optionally perform any finalization tasks here.
    print(datetime.datetime.now(), get_client_ip(), f"Finished quiz '{quiz_name}'")
    return render_template("finish.html", quiz_name=quiz_name)
    print(datetime.datetime.now(), get_client_ip(), f"Successfully rendered finish.html for quiz '{quiz_name}'")

@app.route('/quiz/<quiz_name>/reset')
def reset_quiz(quiz_name):
    client_ip = get_client_ip()
    print(datetime.datetime.now(), client_ip, f"Resetting quiz '{quiz_name}'")
    question_file = os.path.join(os.path.dirname(__file__), "non_static", "question", f"{quiz_name}.json")
    try:
        print(datetime.datetime.now(), client_ip, "attempting to read question file:", question_file)
        with open(question_file, "r", encoding="utf-8") as f:
            question_data = json.load(f)
    except Exception as e:
        question_data = {}
        print(datetime.datetime.now(), client_ip, "failed to read question file:", str(e))
    if not isinstance(question_data, dict):
        question_data = {}
    # Reset the current index to 0 for this client.
    question_data[client_ip] = 0
    print(datetime.datetime.now(), client_ip, "resetting question index to 0")
    # Write the updated question data back to the file.
    try:
        with open(question_file, "w", encoding="utf-8") as f:
            json.dump(question_data, f)
        print(datetime.datetime.now(), client_ip, "successfully reset question index to 0")
    except Exception as e:
        print(datetime.datetime.now(), client_ip, "failed to reset question index:", str(e))
        return jsonify({'error': 'Failed to reset question index.'}), 500
    return redirect(url_for("get_quiz_json", quiz_name=quiz_name))

@app.route('/view_times')
def view_times():
    time_file = os.path.join(os.path.dirname(__file__), "data", "time.txt")
    return send_file(time_file, mimetype="text/plain")

@app.route('/view_times_file')
def view_times_file():
    time_file = os.path.join(os.path.dirname(__file__), "data", "time.txt")
    return send_file(time_file, mimetype="text/plain")

{
  "INAPPROPRIATE_WORDS": [
    "badword1",
    "badword2",
    "inappropriate",
    "poop",
    "pee",
    "stupid",
    "dumb",
    "idiot",
    "ugly",
    "hate",
    "loser",
    "fool",
    "nonsense",
    "trash",
    "garbage",
    "moron",
    "jerk",
    "creep",
    "weirdo",
    "lame",
    "gross",
    "pathetic",
    "annoying",
    "lazy",
    "worthless"
  ]
}  # Add more words as needed

@app.route('/host/<quiz_name>')
def host_quiz(quiz_name):
    import random
    code = str(random.randint(1000, 9999))  # 4-digit code
    while code in sessions:
        code = str(random.randint(1000, 9999))
    control_code = str(random.randint(1000, 9999))
    while control_code in sessions or control_code == code:
        control_code = str(random.randint(1000, 9999))
    # Load questions and attach per-question images if present
    questions = read_quiz(quiz_name)
    images_meta_file = os.path.join(os.path.dirname(__file__), "non_static", "question", f"{quiz_name}_images.json")
    try:
        if os.path.exists(images_meta_file):
            with open(images_meta_file, 'r', encoding='utf-8') as mf:
                images_meta = json.load(mf)
        else:
            images_meta = {}
    except Exception:
        images_meta = {}
    for idx, q in enumerate(questions):
        imgs = images_meta.get(str(idx), [])
        if imgs:
            q['images'] = [f"/UploadedImages/{quiz_name}/{fname}" for fname in imgs]

    sessions[code] = {'host_sid': None, 'control_sids': [], 'players': [], 'quiz_name': quiz_name, 'questions': questions, 'current_q': 0, 'scores': {}, 'answers': [], 'last_correct': {}, 'state': 'lobby', 'control_code': control_code}
    control_to_game[control_code] = code
    return render_template('host.html', code=code, quiz_name=quiz_name, control_code=control_code, is_mobile=is_mobile())

@app.route('/control/<code>')
def control_quiz(code):
    if code in control_to_game:
        game_code = control_to_game[code]
        return render_template('control.html', code=game_code, quiz_name=sessions[game_code]['quiz_name'], is_mobile=is_mobile())
    else:
        return "Invalid control code", 404

@app.route('/join')
def join_game():
    return render_template('join.html', is_mobile=is_mobile())

@socketio.on('join_game')
def handle_join_game(data):
    code = data['code']
    player_name = data.get('name', 'Anonymous')
    avatar = data.get('avatar', '')
    if code in sessions:
        join_room(code)
        sessions[code]['players'].append({'sid': request.sid, 'name': player_name, 'avatar': avatar})
        sessions[code]['scores'][player_name] = 0
        sessions[code]['last_correct'][player_name] = None
        emit('player_joined', {'name': player_name, 'avatar': avatar}, room=code, skip_sid=request.sid)
        emit('joined', {'code': code, 'quiz_name': sessions[code]['quiz_name']})
        # Send current state to late joiner
        state = sessions[code]['state']
        if state == 'question':
            q_index = sessions[code]['current_q'] - 1
            if q_index >= 0:
                q_obj = sessions[code]['questions'][q_index]
                payload = {'question': q_obj.get('question')}
                if q_obj.get('type') == 'mc':
                    payload.update({'answers': q_obj.get('answers', []), 'type': 'mc'})
                else:
                    payload.update({'type': 'type'})
                if q_obj.get('images'):
                    payload['images'] = q_obj.get('images')
                emit('new_question', payload)
        elif state == 'leaderboard':
            leaderboard = []
            for name, score in sorted(sessions[code]['scores'].items(), key=lambda x: x[1], reverse=True):
                last_correct = sessions[code]['last_correct'].get(name)
                # Find avatar for this player
                avatar = ''
                for player in sessions[code]['players']:
                    if player['name'] == name:
                        avatar = player.get('avatar', '')
                        break
                leaderboard.append({'name': name, 'score': score, 'last_correct': last_correct, 'avatar': avatar})
            submitted_answers = {ans['name']: ans['answer_text'] for ans in sessions[code]['answers']} if sessions[code]['answers'] else {}
            correct_answer_text = ''
            q_index = sessions[code]['current_q'] - 1
            q = sessions[code]['questions'][q_index] if q_index >= 0 and q_index < len(sessions[code]['questions']) else None
            if q:
                if q['type'] == 'mc':
                    correct_answer_text = ', '.join(q['answers'][i] for i in q['correct_indices'])
                else:
                    correct_answer_text = q['answer']
            emit('leaderboard', {'leaderboard': leaderboard, 'correct_answer': correct_answer_text, 'submitted_answers': submitted_answers})
        elif state == 'finished':
            leaderboard = []
            for name, score in sorted(sessions[code]['scores'].items(), key=lambda x: x[1], reverse=True):
                # Find avatar for this player
                avatar = ''
                for player in sessions[code]['players']:
                    if player['name'] == name:
                        avatar = player.get('avatar', '')
                        break
                leaderboard.append({'name': name, 'score': score, 'avatar': avatar})
            emit('final_leaderboard', {'leaderboard': leaderboard})
    else:
        emit('error', {'message': 'Invalid code'})

@socketio.on('host_join')
def handle_host_join(data):
    code = data['code']
    if code in sessions:
        sessions[code]['host_sid'] = request.sid
        join_room(code)

@socketio.on('control_join')
def handle_control_join(data):
    code = data['code']
    if code in sessions:
        join_room(code)
        sessions[code]['control_sids'].append(request.sid)
        # Sync current state
        state = sessions[code]['state']
        if state == 'question':
            q_index = sessions[code]['current_q'] - 1
            if q_index >= 0 and q_index < len(sessions[code]['questions']):
                q_obj = sessions[code]['questions'][q_index]
                payload = {'question': q_obj.get('question')}
                if q_obj.get('type') == 'mc':
                    payload.update({'answers': q_obj.get('answers', []), 'type': 'mc'})
                else:
                    payload.update({'type': 'type'})
                if q_obj.get('images'):
                    payload['images'] = q_obj.get('images')
                emit('new_question', payload)
        elif state == 'leaderboard':
            leaderboard = sorted(sessions[code]['scores'].items(), key=lambda x: x[1], reverse=True)
            leaderboard_items = []
            for name, score in leaderboard:
                avatar = ''
                for player in sessions[code]['players']:
                    if player['name'] == name:
                        avatar = player.get('avatar', '')
                        break
                leaderboard_items.append({'name': name, 'score': score, 'last_correct': sessions[code]['last_correct'].get(name), 'avatar': avatar})
            emit('leaderboard', {'leaderboard': leaderboard_items})
        elif state == 'finished':
            leaderboard = sorted(sessions[code]['scores'].items(), key=lambda x: x[1], reverse=True)
            emit('final_leaderboard', {'leaderboard': leaderboard})

@socketio.on('start_round')
def handle_start_round(data):
    code = data['code']
    if code in sessions and (sessions[code]['host_sid'] == request.sid or request.sid in sessions[code]['control_sids']):
        q_index = sessions[code]['current_q']
        if q_index < len(sessions[code]['questions']):
            q_obj = sessions[code]['questions'][q_index]
            sessions[code]['answers'] = []
            sessions[code]['state'] = 'question'
            payload = {'question': q_obj.get('question')}
            if q_obj.get('type') == 'mc':
                payload.update({'answers': q_obj.get('answers', []), 'type': 'mc'})
            else:
                payload.update({'type': 'type'})
            if q_obj.get('images'):
                payload['images'] = q_obj.get('images')
            emit('new_question', payload, room=code)
            sessions[code]['current_q'] += 1
        else:
            sessions[code]['state'] = 'finished'
            leaderboard = [{'name': name, 'score': score} for name, score in sorted(sessions[code]['scores'].items(), key=lambda x: x[1], reverse=True)]
            emit('final_leaderboard', {'leaderboard': leaderboard}, room=code)

@socketio.on('submit_answer')
def handle_submit_answer(data):
    code = data['code']
    answer = data['answer']
    time_taken = data.get('time_taken', 0)
    if code in sessions:
        q_index = sessions[code]['current_q'] - 1
        q = sessions[code]['questions'][q_index] if q_index >= 0 and q_index < len(sessions[code]['questions']) else None
        # Convert answer to text for display
        answer_text = answer
        if q and q['type'] == 'mc' and isinstance(answer, int):
            answer_text = q['answers'][answer] if answer < len(q['answers']) else str(answer)
        # Find player
        for player in sessions[code]['players']:
            if player['sid'] == request.sid:
                sessions[code]['answers'].append({'name': player['name'], 'answer': answer, 'answer_text': answer_text, 'time_taken': time_taken})
                emit('answer_received', {'name': player['name'], 'answer': answer_text}, room=code, skip_sid=request.sid)
                # Check if all players have submitted
                if len(sessions[code]['answers']) == len(sessions[code]['players']):
                    # Auto-reveal answers
                    for ans in sessions[code]['answers']:
                        name = ans['name']
                        time_taken = ans['time_taken']
                        correct = validate_answer(q, ans['answer']) if q else False
                        sessions[code]['last_correct'][name] = correct
                        if correct:
                            points = max(0, round(1000 - time_taken * 50))
                            sessions[code]['scores'][name] += points
                        # Emit to specific player
                        correct_answer_text = ''
                        if q:
                            if q['type'] == 'mc':
                                correct_answer_text = ', '.join(q['answers'][i] for i in q['correct_indices'])
                            else:
                                correct_answer_text = q['answer']
                        for player in sessions[code]['players']:
                            if player['name'] == ans['name']:
                                emit('answer_revealed', {'correct': correct, 'correct_answer': correct_answer_text}, room=player['sid'])
                                break
                    # Emit leaderboard
                        # Emit leaderboard
                        leaderboard = []
                        for name, score in sorted(sessions[code]['scores'].items(), key=lambda x: x[1], reverse=True):
                            last_correct = sessions[code]['last_correct'].get(name)
                            avatar = ''
                            for player in sessions[code]['players']:
                                if player['name'] == name:
                                    avatar = player.get('avatar', '')
                                    break
                            leaderboard.append({'name': name, 'score': score, 'last_correct': last_correct, 'avatar': avatar})
                        submitted_answers = {ans['name']: ans['answer_text'] for ans in sessions[code]['answers']}
                        emit('answers_revealed', {'correct_answer': correct_answer_text}, room=code)
                        sessions[code]['state'] = 'leaderboard'
                        emit('leaderboard', {'leaderboard': leaderboard, 'correct_answer': correct_answer_text, 'submitted_answers': submitted_answers}, room=code)
                break

@socketio.on('reveal_answers')
def handle_reveal_answers(data):
    code = data['code']
    if code in sessions and (sessions[code]['host_sid'] == request.sid or request.sid in sessions[code]['control_sids']):
        q_index = sessions[code]['current_q'] - 1
        q = sessions[code]['questions'][q_index] if q_index >= 0 and q_index < len(sessions[code]['questions']) else None
        correct_answer_text = ''
        if q:
            if q['type'] == 'mc':
                correct_answer_text = ', '.join(q['answers'][i] for i in q['correct_indices'])
            else:
                correct_answer_text = q['answer']
        for ans in sessions[code]['answers']:
            name = ans['name']
            time_taken = ans['time_taken']
            correct = validate_answer(q, ans['answer']) if q else False
            sessions[code]['last_correct'][name] = correct
            if correct:
                points = max(0, round(1000 - time_taken * 50))  # 50 points per second deducted
                sessions[code]['scores'][name] += points
            # Emit to specific player
            for player in sessions[code]['players']:
                if player['name'] == ans['name']:
                    emit('answer_revealed', {'correct': correct, 'correct_answer': correct_answer_text}, room=player['sid'])
                    break
        # Emit leaderboard
        leaderboard = []
        for name, score in sorted(sessions[code]['scores'].items(), key=lambda x: x[1], reverse=True):
            last_correct = sessions[code]['last_correct'].get(name)
            avatar = ''
            for player in sessions[code]['players']:
                if player['name'] == name:
                    avatar = player.get('avatar', '')
                    break
            leaderboard.append({'name': name, 'score': score, 'last_correct': last_correct, 'avatar': avatar})
        submitted_answers = {ans['name']: ans['answer_text'] for ans in sessions[code]['answers']}
        emit('answers_revealed', {'correct_answer': correct_answer_text}, room=code)
        sessions[code]['state'] = 'leaderboard'
        emit('leaderboard', {'leaderboard': leaderboard, 'correct_answer': correct_answer_text, 'submitted_answers': submitted_answers}, room=code)

@socketio.on('disconnect')
def handle_disconnect():
    # Remove player from all sessions
    for code in list(sessions.keys()):
        # Find and remove the player
        for player in sessions[code]['players'][:]:  # Create a copy to iterate
            if player['sid'] == request.sid:
                player_name = player['name']
                sessions[code]['players'].remove(player)
                
                # Remove from scores and last_correct
                if player_name in sessions[code]['scores']:
                    del sessions[code]['scores'][player_name]
                if player_name in sessions[code]['last_correct']:
                    del sessions[code]['last_correct'][player_name]
                
                # Remove from answers list
                sessions[code]['answers'] = [ans for ans in sessions[code]['answers'] if ans['name'] != player_name]
                
                print(datetime.datetime.now(), f"Player '{player_name}' disconnected from game {code}")
                
                # Notify all players in the room that this player left using socketio.emit
                socketio.emit('player_left', {'name': player_name}, room=code)
                
                # Update and broadcast the current leaderboard to all remaining players/host
                if sessions[code]['state'] == 'leaderboard' and sessions[code]['scores']:
                    leaderboard = []
                    for name, score in sorted(sessions[code]['scores'].items(), key=lambda x: x[1], reverse=True):
                        last_correct = sessions[code]['last_correct'].get(name)
                        avatar = ''
                        for player in sessions[code]['players']:
                            if player['name'] == name:
                                avatar = player.get('avatar', '')
                                break
                        leaderboard.append({'name': name, 'score': score, 'last_correct': last_correct, 'avatar': avatar})
                    submitted_answers = {ans['name']: ans['answer_text'] for ans in sessions[code]['answers']}
                    q_index = sessions[code]['current_q'] - 1
                    q = sessions[code]['questions'][q_index] if q_index >= 0 and q_index < len(sessions[code]['questions']) else None
                    correct_answer_text = ''
                    if q:
                        if q['type'] == 'mc':
                            correct_answer_text = ', '.join(q['answers'][i] for i in q['correct_indices'])
                        else:
                            correct_answer_text = q['answer']
                    socketio.emit('leaderboard', {'leaderboard': leaderboard, 'correct_answer': correct_answer_text, 'submitted_answers': submitted_answers}, room=code)
                
                break

if __name__ == '__main__':
    print(datetime.datetime.now(), "Server is not running. Starting Server...")
    # Production: Use debug=False and recommend gunicorn with socketio
    socketio.run(app, debug=False, host="0.0.0.0", port=5710)
    print(datetime.datetime.now(), "Server Error. Stopping Server...")
    # Optional: Add any cleanup code here if needed.
    print(datetime.datetime.now(), "Server stopped.")
