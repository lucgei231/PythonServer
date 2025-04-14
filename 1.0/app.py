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
    quiz_dir = os.path.join(os.path.dirname(__file__), "non_static", "quiz")
    quizzes = []
    try:
        for file in os.listdir(quiz_dir):
            if file.endswith(".txt"):
                quiz_name = os.path.splitext(file)[0]
                quizzes.append(quiz_name)
    except Exception as e:
        print("Error reading quiz folder:", e)
    return render_template('home.html', quizzes=quizzes)

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

@app.route('/<quiz_name>/quiz/question', methods=['GET'])
def quiz_question(quiz_name):
    # Use the saved list of questions, if available.
    questions = session.get('questions', [])
    if questions:
        # Get the next question from the list.
        question_and_answer = questions.pop(0)
        session['questions'] = questions  # update the session
    else:
        # Fallback to get a random question if the list is empty.
        question_and_answer = get_random_question(quiz_name)
    ip = request.remote_addr
    log_event(ip, f"Requested question from quiz '{quiz_name}': {question_and_answer['question']}")
    print(f"User asked for a question from {quiz_name}: {question_and_answer['question']}")
    return jsonify({"question": question_and_answer["question"]})

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
    log_event(ip, f"Finished quiz '{quiz_name}' with {correct} correct out of {total} attempts")
    result = {'score': correct, 'total': total}
    return jsonify(result)

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