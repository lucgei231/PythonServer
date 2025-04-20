import os
import json
import random
import datetime
import sys
import threading
import re

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from non_static.utils import example_util_function, ExampleUtility
from non_static.quiz import get_random_question, validate_answer, read_quiz
#from win32com.client import Dispatch  # Removed win32com dependency
from werkzeug.utils import secure_filename

# Removed text-to-speech engine initialization that used win32com
# speaker = win32com.client.Dispatch("SAPI.SpVoice")

# Initialize the Flask app
app = Flask(__name__)
app.secret_key = "your_random_secret_key_here"  # Secret key for session management

# Function to log events (e.g., user actions) to a log file
def log_event(ip, event):
    # Create a directory for logs if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    # Write the event to a log file specific to the user's IP
    log_file = os.path.join(logs_dir, f"{ip}.log")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now()}: {event}\n")

def get_client_ip():
    # The X-Forwarded-For header can contain multiple IPs. Take the first one.
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr

# Middleware to log when a user connects
@app.before_request
def log_connection():
    ip = get_client_ip()  # Get the user's IP address
    # Commenting out logging for testing
    # log_event(ip, "Connected")

# Middleware to log when a user disconnects
@app.teardown_request
def log_disconnection(exception):
    ip = get_client_ip()  # Get the user's IP address
    log_event(ip, "Disconnected")  # Log the disconnection event

# Health check route to verify the server is running
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"}), 200  # Return a simple JSON response

# Home route: list available quizzes found in the "non_static/quiz/" directory
@app.route('/')
def home():
    try:
        quiz_dir = os.path.join(os.path.dirname(__file__), "non_static", "quiz")
        quizzes = []
        if os.path.exists(quiz_dir):
            for file in os.listdir(quiz_dir):
                if file.endswith(".txt"):
                    quiz_name = os.path.splitext(file)[0]
                    quizzes.append(quiz_name)
        # Load uploaded quizzes for current IP
        uploaded_file = os.path.join(os.path.dirname(__file__), "data", "uploaded.json")
        user_uploaded = []
        ip = get_client_ip()
        if os.path.exists(uploaded_file):
            with open(uploaded_file, "r", encoding="utf-8") as f:
                uploaded_data = json.load(f)
            user_uploaded = uploaded_data.get(ip, [])
        print("Home route: found quizzes:", quizzes)  # Debug print
        return render_template('home.html', quizzes=quizzes, user_uploaded=user_uploaded), 200
    except Exception as e:
        return f"Error in home route: {str(e)}", 500

@app.route('/addquiz', methods=['GET'], strict_slashes=True)
def addquiz():
    return render_template('addquiz.html')

# Now the dynamic quiz route comes after specific routes (under a fixed /quiz/ prefix)
@app.route('/quiz/<quiz_name>')
def quiz_index(quiz_name):
    try:
        # Initialize tracking variables
        session['correct_count'] = 0
        session['total_attempt'] = 0
        session['quiz_name'] = quiz_name
        session['shuffle'] = False  # Always set shuffle to False

        # Read quiz questions from file and store into session
        questions = read_quiz(quiz_name)
        session['questions'] = questions
        session['current_question_index'] = 0
        
        # Redirect to the question page
        return redirect(url_for('show_question', quiz_name=quiz_name))
    except FileNotFoundError:
        return f"Quiz '{quiz_name}' not found.", 404
    except Exception as e:
        return f"An error occurred: {str(e)}", 500

# Route to serve the next question for the given quiz (under /quiz/ prefix)
@app.route('/quiz/<quiz_name>/quiz/question', methods=['GET'])
def show_question(quiz_name):
    # Retrieve questions and current index from the session
    questions = session.get('questions')
    current_index = session.get('current_question_index', 0)
    if not questions:
        questions = read_quiz(quiz_name)
        session['questions'] = questions
        session['current_question_index'] = 0
        current_index = 0
    if current_index < len(questions):
        question = questions[current_index]
    else:
        # Provide a fallback object to avoid "question not defined" error in the template
        question = {'question': "No more questions available", 'options': []}
    return render_template('question.html', question=question, quiz_name=quiz_name)

# Route to validate the user's answer for a question (under /quiz/ prefix)
@app.route('/quiz/<quiz_name>/quiz/validate', methods=['POST'])
def quiz_validate(quiz_name):
    ip = get_client_ip()
    answer = request.json.get('answer')
    questions = session.get('questions', [])
    current_index = session.get('current_question_index', 0)
    
    if current_index < len(questions):
        current_question = questions[current_index]
        correct_answer = current_question.get("answer", "").lower().strip()
        is_correct = answer.lower().strip() == correct_answer
        print(f"User answered '{answer}' for question '{current_question.get('question')}'. Expected: '{correct_answer}'.")
        # Increment total attempt count
        session['total_attempt'] = session.get('total_attempt', 0) + 1
        if is_correct:
            # Increment correct count and update the question index
            session['correct_count'] = session.get('correct_count', 0) + 1
            session['current_question_index'] = current_index + 1
        return jsonify({'is_correct': is_correct})
    
    return jsonify({'error': 'No question available'}), 400

# Quiz finish, reset, and toggle_shuffle routes similarly update:
@app.route('/quiz/<quiz_name>/quiz/finish', methods=['GET'])
def quiz_finish(quiz_name):
    correct = session.get('correct_count', 0)
    total = session.get('total_attempt', 0)
    ip = get_client_ip()

    question_dir = os.path.join(os.path.dirname(__file__), "non_static", "question")
    question_file = os.path.join(question_dir, f"{quiz_name}.json")
    # Ensure the JSON file exists with an empty structure if it doesn't
    if not os.path.exists(question_file):
        with open(question_file, "w", encoding="utf-8") as f:
            json.dump({}, f)

    if os.path.exists(question_file):
        with open(question_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if ip in data:
            del data[ip]
        with open(question_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

    log_event(ip, f"Finished quiz '{quiz_name}' with {correct} correct out of {total} attempts")
    return render_template('index.html', result=f"You got {correct} out of {total}!", play_again=True)

# New route to reset the quiz
@app.route('/quiz/<quiz_name>/reset', methods=['GET', 'POST'])
def reset_quiz(quiz_name):
    ip = get_client_ip()
    question_dir = os.path.join(os.path.dirname(__file__), "non_static", "question")
    question_file = os.path.join(question_dir, f"{quiz_name}.json")
    if os.path.exists(question_file):
        with open(question_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        data[ip] = 1
        with open(question_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

    session['correct_count'] = 0
    session['total_attempt'] = 0
    session['questions'] = read_quiz(quiz_name)
    return jsonify({"message": "Quiz reset successfully."})

# New route to toggle the shuffle setting
@app.route('/quiz/<quiz_name>/toggle_shuffle', methods=['POST'])
def toggle_shuffle(quiz_name):
    # Toggle the current shuffle state (default False)
    current = session.get('shuffle', False)
    new_setting = not current
    session['shuffle'] = new_setting

    # Reload the quiz questions and shuffle them if needed
    questions = read_quiz(quiz_name)
    if new_setting:
        random.shuffle(questions)
    session['questions'] = questions

    # Return the new shuffle state as confirmation
    return jsonify({"shuffle": new_setting})

def custom_secure_filename(filename):
    # Only remove characters that are not alphanumeric, space, a dash, a dot, or an underscore.
    filename = os.path.basename(filename)
    filename = re.sub(r'[^\w\s.-]', '', filename).strip()
    return filename

@app.route('/upload_quiz', methods=['POST'])
def upload_quiz():
    if 'quiz_file' not in request.files:
        return render_template('error.html', message="No file part in the request."), 400
    file = request.files['quiz_file']
    if file.filename == '':
        return render_template('error.html', message="No file selected for uploading."), 400
    filename = custom_secure_filename(file.filename)  # Use the custom sanitization that preserves spaces
    if not filename.lower().endswith('.txt'):
        return render_template('error.html', message="Only .txt files are allowed."), 400
    quiz_dir = os.path.join(os.path.dirname(__file__), "non_static", "quiz")
    if not os.path.exists(quiz_dir):
        os.makedirs(quiz_dir)
    file_path = os.path.join(quiz_dir, filename)
    try:
        file.save(file_path)
    except Exception as e:
        return render_template('error.html', message=f"File saving failed: {str(e)}"), 500
    # Ensure the data directory exists
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    uploaded_file = os.path.join(data_dir, "uploaded.json")
    try:
        if os.path.exists(uploaded_file):
            with open(uploaded_file, "r", encoding="utf-8") as f:
                uploaded_data = json.load(f)
        else:
            uploaded_data = {}
    except Exception:
        uploaded_data = {}
    ip = get_client_ip()
    user_list = uploaded_data.get(ip, [])
    quiz_base = os.path.splitext(filename)[0]
    if quiz_base not in user_list:
        user_list.append(quiz_base)
    uploaded_data[ip] = user_list
    with open(uploaded_file, "w", encoding="utf-8") as f:
        json.dump(uploaded_data, f)
    return render_template('addquiz.html', message="Quiz uploaded successfully!")

@app.route('/deletequiz', methods=['GET', 'POST'])
def deletequiz():
    ip = get_client_ip()
    uploaded_file = os.path.join(os.path.dirname(__file__), "data", "uploaded.json")
    if os.path.exists(uploaded_file):
        with open(uploaded_file, "r", encoding="utf-8") as f:
            uploaded_data = json.load(f)
    else:
        uploaded_data = {}
    user_uploaded = uploaded_data.get(ip, [])
    if request.method == "POST":
        quiz_to_delete = request.form.get("quiz")
        if quiz_to_delete in user_uploaded:
            # Remove the quiz file
            quiz_dir = os.path.join(os.path.dirname(__file__), "non_static", "quiz")
            quiz_file = os.path.join(quiz_dir, quiz_to_delete + ".txt")
            if os.path.exists(quiz_file):
                os.remove(quiz_file)
            # Update the uploaded data
            user_uploaded.remove(quiz_to_delete)
            uploaded_data[ip] = user_uploaded
            with open(uploaded_file, "w", encoding="utf-8") as f:
                json.dump(uploaded_data, f)
            message = "Quiz deleted successfully."
        else:
            message = "You are not allowed to delete this quiz."
        return render_template("deletequiz.html", message=message, user_uploaded=user_uploaded)
    # For GET method, render the selection form
    return render_template("deletequiz.html", user_uploaded=user_uploaded)

@app.route('/makequiz', methods=['GET', 'POST'])
def makequiz():
    if request.method == "POST":
        # Get the entered quiz content and file name
        quiz_content = request.form.get('quiz_content')
        filename = request.form.get('filename')
        if not filename:
            return render_template('makequiz.html', message="Please provide a file name.")
        if not filename.endswith('.txt'):
            filename += '.txt'
        quiz_dir = os.path.join(os.path.dirname(__file__), "non_static", "quiz")
        if not os.path.exists(quiz_dir):
            os.makedirs(quiz_dir)
        file_path = os.path.join(quiz_dir, filename)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(quiz_content)
            # After saving the file, update uploaded.json
            uploaded_file = os.path.join(os.path.dirname(__file__), "data", "uploaded.json")
            if os.path.exists(uploaded_file):
                with open(uploaded_file, "r", encoding="utf-8") as f:
                    try:
                        uploaded_data = json.load(f)
                    except json.JSONDecodeError:
                        uploaded_data = {}
            else:
                uploaded_data = {}

            ip = get_client_ip()
            user_list = uploaded_data.get(ip, [])
            quiz_base = os.path.splitext(filename)[0]
            if quiz_base not in user_list:
                user_list.append(quiz_base)
            uploaded_data[ip] = user_list
            data_dir = os.path.join(os.path.dirname(__file__), "data")
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
            with open(uploaded_file, "w", encoding="utf-8") as f:
                json.dump(uploaded_data, f)
            message = "Quiz created successfully!"
        except Exception as e:
            message = f"An error occurred: {str(e)}"
        return render_template('makequiz.html', message=message)
    return render_template('makequiz.html')

@app.route('/editquiz', methods=['GET', 'POST'])
def editquiz_select():
    ip = get_client_ip()
    uploaded_file = os.path.join(os.path.dirname(__file__), "data", "uploaded.json")
    if os.path.exists(uploaded_file):
        with open(uploaded_file, "r", encoding="utf-8") as f:
            uploaded_data = json.load(f)
    else:
        uploaded_data = {}
    user_uploaded = uploaded_data.get(ip, [])
    if request.method == "POST":
        print("POST data:", request.form)  # Add this line
        quiz_to_edit = request.form.get("quiz")
        if quiz_to_edit in user_uploaded:
            return redirect(url_for('edit_quiz', quiz_name=quiz_to_edit))
        else:
            message = "You are not allowed to edit this quiz."
            return render_template("editquiz_select.html", user_uploaded=user_uploaded, message=message)
    return render_template("editquiz_select.html", user_uploaded=user_uploaded)

@app.route('/edit_quiz/<quiz_name>', methods=['GET', 'POST'])
def edit_quiz(quiz_name):
    quiz_dir = os.path.join(os.path.dirname(__file__), "non_static", "quiz")
    quiz_file = os.path.join(quiz_dir, quiz_name + ".txt")
    if request.method == "POST":
        new_content = request.form.get("quiz_content", "")
        try:
            with open(quiz_file, "w", encoding="utf-8") as f:
                f.write(new_content)
            message = "Quiz saved successfully!"
        except Exception as e:
            message = f"Error saving quiz: {str(e)}"
        return render_template("editquiz.html", quiz_name=quiz_name, quiz_content=new_content, message=message)
    # GET: Load current quiz content
    if os.path.exists(quiz_file):
        with open(quiz_file, "r", encoding="utf-8") as f:
            quiz_content = f.read()
    else:
        quiz_content = ""
    return render_template("editquiz.html", quiz_name=quiz_name, quiz_content=quiz_content)

def listen_for_commands():
    while True:
        cmd = input()
        cmd_lower = cmd.strip().lower()
        if cmd_lower == "restart":
            print("Restarting...")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        elif cmd_lower == "force-restart":
            print("Force restarting...")
            # Start a new process and then exit the current one.
            import subprocess
            subprocess.Popen([sys.executable] + sys.argv)
            sys.exit(0)

if __name__ == '__main__':
    # Start the command listener thread
    threading.Thread(target=listen_for_commands, daemon=True).start()
    app.run(debug=True, host="0.0.0.0", port=5710)