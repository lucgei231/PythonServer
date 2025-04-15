import os
import json
import random
import datetime
import sys
import threading
from flask import Flask, render_template, jsonify, request, session
from non_static.utils import example_util_function, ExampleUtility
from non_static.quiz import get_random_question, validate_answer, read_quiz
import win32com.client

speaker = win32com.client.Dispatch("SAPI.SpVoice")

app = Flask(__name__)
app.secret_key = "your_random_secret_key_here"

def log_event(ip, event):
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    log_file = os.path.join(logs_dir, f"{ip}.log")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now()}: {event}\n")

@app.before_request
def log_connection():
    ip = request.remote_addr
    log_event(ip, "Connected")

@app.teardown_request
def log_disconnection(exception):
    ip = request.remote_addr
    log_event(ip, "Disconnected")

# Home route: list available quizzes found in non_static/quiz/
@app.route('/')
def home():
    try:
        quiz_dir = os.path.join(os.path.dirname(__file__), "non_static", "quiz")
        quizzes = []
        for file in os.listdir(quiz_dir):
            if file.endswith(".txt"):
                quiz_name = os.path.splitext(file)[0]
                quizzes.append(quiz_name)
        # Debugging log
        print(f"Available quizzes: {quizzes}")
        return render_template('home.html', quizzes=quizzes)
    except Exception as e:
        # Debugging log
        print(f"Error in home route: {str(e)}")
        return jsonify({"error": "An error occurred while loading the home page."}), 500

# Render the quiz page for the given quiz name (without .txt) and initialize score tracking
@app.route('/<quiz_name>')
def quiz_index(quiz_name):
    session['correct_count'] = 0
    session['total_attempt'] = 0
    session['quiz_name'] = quiz_name
    # Get the toggle from a query parameter; default is True (shuffle questions)
    shuffle_param = request.args.get('shuffle', 'false').lower() == 'true'
    session['shuffle'] = shuffle_param

    # Read the quiz questions from file
    questions = read_quiz(quiz_name)
    # Shuffle if desired
    if session['shuffle']:
         random.shuffle(questions)
    # Save the list to session
    session['questions'] = questions
    return render_template('index.html', quiz_name=quiz_name, shuffle=shuffle_param)

# Function to store the current question for each IP
@app.route('/<quiz_name>/quiz/question', methods=['GET'])
def quiz_question(quiz_name):
    try:
        questions = session.get('questions', [])
        ip = request.remote_addr

        if not questions:
            log_event(ip, f"No questions loaded in session for quiz '{quiz_name}'")
            return jsonify({"error": "No questions loaded. Please restart the quiz."}), 400

        question_dir = os.path.join(os.path.dirname(__file__), "non_static", "question")
        if not os.path.exists(question_dir):
            os.makedirs(question_dir)

        question_file = os.path.join(question_dir, f"{quiz_name}.json")
        if not os.path.exists(question_file):
            with open(question_file, "w", encoding="utf-8") as f:
                json.dump({}, f)

        with open(question_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                log_event(ip, f"Corrupted JSON file for quiz '{quiz_name}'. Resetting.")
                data = {}

        current_index = data.get(ip, 0)
        print(f"Current index for IP {ip}: {current_index}, Total questions: {len(questions)}")

        if current_index < len(questions):
            question_and_answer = questions[current_index]
            data[ip] = current_index + 1
            with open(question_file, "w", encoding="utf-8") as f:
                json.dump(data, f)

            log_event(ip, f"Requested question from quiz '{quiz_name}': {question_and_answer['question']}")
            return jsonify({"question": question_and_answer["question"]})
        else:
            log_event(ip, f"No more questions available for quiz '{quiz_name}'")
            return jsonify({"message": "No more questions available."})
    except Exception as e:
        print(f"Error in quiz_question route: {str(e)}")
        log_event(ip, f"Error in quiz_question route for quiz '{quiz_name}': {str(e)}")
        return jsonify({"error": "An error occurred while processing your request."}), 500

@app.route('/<quiz_name>/quiz/validate', methods=['POST'])
def quiz_validate(quiz_name):
    ip = request.remote_addr
    # Receive the entire question object and the user answer from the request body
    answer = request.json.get('answer')
    question_obj = request.json.get('question')
    question_text = question_obj["question"]
    log_event(ip, f"Submitted answer for question '{question_text}' with answer '{answer}' in quiz '{quiz_name}'")
    print(f"Answer received: {answer} for question: {question_text}")
    is_correct = False

    # Track score in session
    session['total_attempt'] = session.get('total_attempt', 0) + 1

    # Read all questions from the specified quiz file
    all_questions = read_quiz(quiz_name)
    for possible_question in all_questions:
        if possible_question["question"] == question_text:
            is_correct = answer.lower().strip() == possible_question["answer"].lower().strip()
            break

    if is_correct:
        session['correct_count'] = session.get('correct_count', 0) + 1
        log_event(ip, f"Correct answer for question: '{question_text}'")
    else:
        log_event(ip, f"Incorrect answer for question: '{question_text}'")

    print(f"User answered question: {question_text} and said '{answer}' in quiz {quiz_name}")

    return jsonify({'is_correct': is_correct})

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
    # Toggle the current shuffle state (default True)
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

def listen_for_commands():
    while True:
        cmd = input()
        if cmd.strip().lower() == "restart":
            print("Restarting...")
            # Restart the process by replacing the current process
            os.execv(sys.executable, [sys.executable] + sys.argv)

if __name__ == '__main__':
    # Start the command listener thread
    threading.Thread(target=listen_for_commands, daemon=True).start()
    app.run(debug=True, host="0.0.0.0", port=5710)