import os
import json
import random
import datetime
import re
import sys
import threading

from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_file

from non_static.quiz import read_quiz, get_random_question, validate_answer  # adjust imports as needed

from non_static.utils import read_uploaded_json, write_uploaded_json

app = Flask(__name__, template_folder="templates")
app.secret_key = "your_random_secret_key_here"

# Ensure the logs directory exists.
logs_dir = os.path.join(os.path.dirname(__file__), "logs")
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)
print(datetime.datetime.now(), "Logs directory set up at", logs_dir)

# Use a fixed filename for all print() output.
log_filename = os.path.join(os.path.dirname(__file__), "logs", "print.txt")

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

sys.stdout = Logger(log_filename)
print(datetime.datetime.now(), "Starting Server with logger.")

def get_client_ip():
    forwarded_for = request.headers.get('X-Forwarded-For')
    return forwarded_for.split(",")[0].strip() if forwarded_for else request.remote_addr

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

@app.route('/kick', methods=['POST'])
def kick():
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
        return render_template('home.html', quizzes=quizzes, user_uploaded=user_uploaded), 200
    except Exception as e:
        print("DEBUG: Error in home route:", str(e))
        return f"Error in home route: {str(e)}", 500

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

@app.route('/quiz/<quiz_name>', methods=['GET'])
def quiz_index(quiz_name):
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

    current_index = question_data.get(client_ip, 0)
    
    # If the current question index is out-of-range, render finish.html
    if current_index >= len(questions):
        print(client_ip, f"Quiz '{quiz_name}' finished for client {client_ip}. Rendering finish.html.")
        return render_template("finish.html", quiz_name=quiz_name)
    
    # Otherwise, show the current question.
    question = questions[current_index]
    display_index = current_index + 1
    quiz_total = len(questions)
    session['current_question_name'] = question.get('question', 'Unknown Question')
    
    return render_template("quiz.html",
                           quiz_name=quiz_name,
                           question=question,
                           question_index=display_index,
                           quiz_total=quiz_total)

@app.route('/editquiz/<quiz_name>', methods=['GET', 'POST'])
def edit_quiz(quiz_name):
    quiz_file = os.path.join(os.path.dirname(__file__), "non_static", "quiz", f"{quiz_name}.txt")
    question_file = os.path.join(os.path.dirname(__file__), "non_static", "question", f"{quiz_name}.json")
    
    if request.method == 'GET':
        # Read quiz text content.
        print(get_client_ip(), "is currently editing", quiz_name)
        try:
            with open(quiz_file, "r", encoding="utf-8") as f:
                quiz_content = f.read()
        except Exception as e:
            quiz_content = ""
            print(get_client_ip(), "Got an error while reading the quiz: ", str(e)) 
            print(get_client_ip(), "is currently editing", quiz_name)   

        # Read question JSON
        try:
            with open(question_file, "r", encoding="utf-8") as f:
                question_data = json.load(f)
        except Exception as e:
            question_data = {}
        return render_template("editquiz.html", quiz_name=quiz_name, quiz_content=quiz_content, question_data=question_data)
    else:
        # POST: update both the quiz text and the question data.
        print(get_client_ip(), "is saving their edits to", quiz_name)
        new_content = request.form.get("quiz_content")
        # This assumes the form passes the question data as a JSON string.
        question_data_str = request.form.get("question_data")
        try:
            new_question_data = json.loads(question_data_str) if question_data_str else {}
        except Exception as e:
            new_question_data = {}
            print(get_client_ip(), " Got an error while parsing question data: ", str(e))

        # Write updated quiz text.
        try:
            with open(quiz_file, "w", encoding="utf-8") as f:
                f.write(new_content)
                print(get_client_ip(), "Saved edits to", quiz_name, " successfully.")
        except Exception as e:
            return f"Error updating quiz text: {str(e)}", 500

        # Write updated question JSON.
        try:
            with open(question_file, "w", encoding="utf-8") as f:
                json.dump(new_question_data, f)
        except Exception as e:
            print(get_client_ip(), " Got an error while parsing question data: ", str(e))
            return f"Error updating question data: {str(e)}", 500

        message = "Quiz and question updated successfully!"
        return render_template("editquiz.html", quiz_name=quiz_name, quiz_content=new_content, question_data=new_question_data, message=message)

@app.route('/quiz/<quiz_name>/quiz/validate', methods=['POST'])
def quiz_validate(quiz_name):
    answer = request.json.get('answer', '')
    try:
        questions = read_quiz(quiz_name)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    if not questions:
        return jsonify({'error': 'No questions found.'}), 404
    question_file = os.path.join(os.path.dirname(__file__), "non_static", "question", f"{quiz_name}.json")
    try:
        with open(question_file, "r", encoding="utf-8") as f:
            question_data = json.load(f)
    except Exception as e:
        question_data = {}
    client_ip = get_client_ip()
    current_index = question_data.get(client_ip, 0)
    if current_index >= len(questions):
        current_index = 0
    correct_answer = questions[current_index].get('answer', '')
    is_correct = answer.strip().lower() == correct_answer.strip().lower()
    if is_correct:
        new_index = current_index + 1
        if new_index >= len(questions):
            # Signal finish; client-side JS should redirect accordingly.
            return jsonify({'redirect': url_for('finish_quiz', quiz_name=quiz_name)})
        else:
            question_data[client_ip] = new_index
            try:
                with open(question_file, "w", encoding="utf-8") as f:
                    json.dump(question_data, f)
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
    if os.path.exists(logs_dir):
        # Get files sorted by name.
        files = sorted(os.listdir(logs_dir))
        for filename in files:
            file_path = os.path.join(logs_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                if filename == "print.txt":
                    logs_content += file_content + "\n\n"
                else:
                    # Only show nonempty files.
                    if file_content.strip() != "":
                        logs_content += f"--- {filename} ---\n{file_content}\n\n"
            except Exception as e:
                logs_content += f"--- {filename} ---\nError reading file: {str(e)}\n\n"
    else:
        logs_content = "No logs found."
    print("Detected IP", get_client_ip(), "on /logs")
    return render_template("logs.html", logs_content=logs_content)

@app.route('/logs-content')
def logs_content():
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    logs_text = ""
    if os.path.exists(logs_dir):
        files = sorted(os.listdir(logs_dir))
        for filename in files:
            file_path = os.path.join(logs_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                if filename == "print.txt":
                    logs_text += file_content + "\n\n"
                else:
                    if file_content.strip() != "":
                        logs_text += f"--- {filename} ---\n{file_content}\n\n"
            except Exception as e:
                logs_text += f"--- {filename} ---\nError reading file: {str(e)}\n\n"
    else:
        logs_text = "No logs found."
    return logs_text

@app.route('/quiz/<quiz_name>/answer', methods=['POST'])
def submit_answer(quiz_name):
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

    current_index = question_data.get(client_ip, 0)
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
        return redirect(url_for('quiz_index', quiz_name=quiz_name))

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

@app.route('/quiz/<quiz_name>/save_time', methods=['POST'])
def save_time(quiz_name):
    if not quiz_name or quiz_name.strip() == "":
        print(datetime.datetime.now(), "Error: Quiz name is missing in the URL.")
        return jsonify({'error': 'Quiz name is required in the URL.'}), 400
    client_ip = get_client_ip()
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
    return redirect(url_for("quiz_index", quiz_name=quiz_name))

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

if __name__ == '__main__':
    print(datetime.datetime.now(), "Server is not running. Starting Server...")
    app.run(debug=True, host="0.0.0.0", port=5702)
    print(datetime.datetime.now(), "Server Error. Stopping Server...")
    # Optional: Add any cleanup code here if needed.
    print(datetime.datetime.now(), "Server stopped.")
else:
    print(datetime.datetime.now(), "There was an errror while starting the server:", __name__)
    # Optional: Add any cleanup code here if needed.
    print(datetime.datetime.now(), "Server stopped.")
