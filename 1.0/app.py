import os
import json
import random
import datetime
import sys
import threading
import re

from flask import Flask, render_template, jsonify, request, session
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

# Middleware to log when a user connects
@app.before_request
def log_connection():
    ip = request.remote_addr  # Get the user's IP address
    # Commenting out logging for testing
    # log_event(ip, "Connected")

# Middleware to log when a user disconnects
@app.teardown_request
def log_disconnection(exception):
    ip = request.remote_addr  # Get the user's IP address
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
        print("Home route: found quizzes:", quizzes)  # Debug print
        return render_template('home.html', quizzes=quizzes), 200
    except Exception as e:
        print(f"Error in home route: {str(e)}")
        return render_template('error.html', message="An error occurred while loading the home page."), 500

@app.route('/addquiz', methods=['GET'], strict_slashes=True)
def addquiz():
    return render_template('addquiz.html')

# Now the dynamic quiz route comes after specific routes
@app.route('/<quiz_name>')
def quiz_index(quiz_name):
    try:
        # Initialize session variables for tracking quiz progress
        session['correct_count'] = 0
        session['total_attempt'] = 0
        session['quiz_name'] = quiz_name
        session['shuffle'] = False  # Always set shuffle to False

        # Read the quiz questions from file
        questions = read_quiz(quiz_name)
        if not questions:  # Ensure questions are loaded
            return render_template('error.html', message="No questions found for this quiz."), 404

        # Store questions in the session (no shuffling)
        session['questions'] = questions
        return render_template('index.html', quiz_name=quiz_name, shuffle=False), 200
    except FileNotFoundError:
        return render_template('error.html', message="Quiz file not found."), 404
    except Exception as e:
        print(f"Error in quiz_index route: {str(e)}")  # Log the error
        return render_template('error.html', message="An error occurred while loading the quiz page."), 500

# Route to serve the next question for the given quiz
@app.route('/<quiz_name>/quiz/question', methods=['GET'])
def quiz_question(quiz_name):
    try:
        questions = session.get('questions', [])  # Retrieve questions from the session
        ip = request.remote_addr  # Get the user's IP address

        if not questions:  # If no questions are loaded, return an error
            return jsonify({"error": "No questions loaded. Please restart the quiz."}), 400

        # Directory to store question progress for each user
        question_dir = os.path.join(os.path.dirname(__file__), "non_static", "question")
        if not os.path.exists(question_dir):  # Create the directory if it doesn't exist
            os.makedirs(question_dir)

        # File to store the user's progress for the current quiz
        question_file = os.path.join(question_dir, f"{quiz_name}.json")
        if not os.path.exists(question_file):  # Create the file if it doesn't exist
            with open(question_file, "w", encoding="utf-8") as f:
                json.dump({}, f)

        # Load the user's progress from the file
        with open(question_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}

        # Determine the current question index for the user
        current_index = data.get(ip, 0)
        if current_index < len(questions):  # If there are more questions
            question_and_answer = questions[current_index]  # Get the current question
            data[ip] = current_index + 1  # Update the user's progress
            with open(question_file, "w", encoding="utf-8") as f:
                json.dump(data, f)  # Save the updated progress
            return jsonify({"question": question_and_answer["question"]}), 200  # Return the question
        else:
            return jsonify({"message": "No more questions available."}), 200  # No more questions
    except Exception as e:
        print(f"Error in quiz_question route: {str(e)}")  # Log the error
        return jsonify({"error": "An error occurred while processing your request."}), 500

# Route to validate the user's answer for a question
@app.route('/<quiz_name>/quiz/validate', methods=['POST'])
def quiz_validate(quiz_name):
    ip = request.remote_addr  # Get the user's IP address
    answer = request.json.get('answer')  # Get the user's answer from the request
    question_obj = request.json.get('question')  # Get the question object from the request
    question_text = question_obj["question"]  # Extract the question text
    log_event(ip, f"Submitted answer for question '{question_text}' with answer '{answer}' in quiz '{quiz_name}'")
    print(f"Answer received: {answer} for question: {question_text}")
    is_correct = False

    # Track the total number of attempts in the session
    session['total_attempt'] = session.get('total_attempt', 0) + 1

    # Read all questions from the specified quiz file
    all_questions = read_quiz(quiz_name)
    for possible_question in all_questions:  # Find the matching question
        if possible_question["question"] == question_text:
            # Compare the user's answer with the correct answer
            is_correct = answer.lower().strip() == possible_question["answer"].lower().strip()
            break

    if is_correct:
        session['correct_count'] = session.get('correct_count', 0) + 1  # Increment correct count
        log_event(ip, f"Correct answer for question: '{question_text}'")
    else:
        log_event(ip, f"Incorrect answer for question: '{question_text}'")

    print(f"User answered question: {question_text} and said '{answer}' in quiz {quiz_name}")

    return jsonify({'is_correct': is_correct})  # Return whether the answer was correct

@app.route('/<quiz_name>/quiz/finish', methods=['GET'])
def quiz_finish(quiz_name):
    correct = session.get('correct_count', 0)
    total = session.get('total_attempt', 0)
    ip = request.remote_addr

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
@app.route('/<quiz_name>/reset', methods=['POST'])
def reset_quiz(quiz_name):
    ip = request.remote_addr
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
@app.route('/<quiz_name>/toggle_shuffle', methods=['POST'])
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
    if not filename.endswith('.txt'):
        return render_template('error.html', message="Only .txt files are allowed."), 400
    quiz_dir = os.path.join(os.path.dirname(__file__), "non_static", "quiz")
    if not os.path.exists(quiz_dir):
        os.makedirs(quiz_dir)
    file_path = os.path.join(quiz_dir, filename)
    file.save(file_path)
    return render_template('addquiz.html', message="Quiz uploaded successfully!")

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