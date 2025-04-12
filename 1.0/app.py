import os
import json
import random
import datetime
from flask import Flask, render_template, jsonify, request
from non_static.utils import example_util_function, ExampleUtility
from non_static.quiz import get_random_question, validate_answer, read_quiz
import win32com.client

speaker = win32com.client.Dispatch("SAPI.SpVoice")

app = Flask(__name__)

def log_event(ip, event):
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    log_file = os.path.join(logs_dir, f"{ip}.txt")
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

# Render the quiz page for the given quiz name (without .txt)
@app.route('/<quiz_name>')
def quiz_index(quiz_name):
    return render_template('index.html', quiz_name=quiz_name)

@app.route('/<quiz_name>/quiz/question', methods=['GET'])
def quiz_question(quiz_name):
    question_and_answer = get_random_question(quiz_name)
    question = {
        "question": question_and_answer["question"]
    }
    ip = request.remote_addr
    log_event(ip, f"Requested question from quiz '{quiz_name}': {question['question']}")
    print(f"User asked for a question from {quiz_name}: {question}")
    return jsonify(question)

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

    # Read all questions from the specified quiz file
    all_questions = read_quiz(quiz_name)
    for possible_question in all_questions:
        if possible_question["question"] == question_text:
            is_correct = answer == possible_question["answer"]
            break

    if is_correct:
        log_event(ip, f"Correct answer for question: '{question_text}'")
    else:
        log_event(ip, f"Incorrect answer for question: '{question_text}'")

    print(f"User answered question: {question_text} and said '{answer}' in quiz {quiz_name}")
    speaker.Speak(f"Test")

    return jsonify({'is_correct': is_correct})

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5601)