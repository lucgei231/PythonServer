import os
import json
import random
import datetime
import re

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from non_static.quiz import read_quiz, get_random_question, validate_answer  # adjust imports as needed

app = Flask(__name__)
app.secret_key = "your_random_secret_key_here"

def get_client_ip():
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr

@app.before_request
def log_connection():
    ip = get_client_ip()
    # Optional: Add connection logging here

@app.after_request
def log_disconnection(response):
    ip = get_client_ip()
    # Optional: Add disconnection logging here
    return response

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
        return render_template('home.html', quizzes=quizzes, user_uploaded=user_uploaded), 200
    except Exception as e:
        return f"Error in home route: {str(e)}", 500

@app.route('/deletequiz', methods=['GET', 'POST'])
def deletequiz():
    ip = get_client_ip()
    if request.method == "GET":
        # Expect the quiz name as a query parameter: ?quiz=quizname
        quiz = request.args.get("quiz")
        if not quiz:
            return redirect(url_for("home"))
        return render_template("deletequiz_confirm.html", quiz=quiz)
    
    # POST: actually delete the quiz.
    quiz_to_delete = request.form.get("quiz")
    uploaded_file = os.path.join(os.path.dirname(__file__), "data", "uploaded.json")
    if os.path.exists(uploaded_file):
        with open(uploaded_file, "r", encoding="utf-8") as f:
            uploaded_data = json.load(f)
    else:
        uploaded_data = {}
    user_uploaded = uploaded_data.get(ip, [])
    
    # Delete the quiz file if allowed.
    if quiz_to_delete in user_uploaded:
        quiz_dir = os.path.join(os.path.dirname(__file__), "non_static", "quiz")
        quiz_file = os.path.join(quiz_dir, quiz_to_delete + ".txt")
        if os.path.exists(quiz_file):
            os.remove(quiz_file)
        user_uploaded.remove(quiz_to_delete)
        uploaded_data[ip] = user_uploaded
        with open(uploaded_file, "w", encoding="utf-8") as f:
            json.dump(uploaded_data, f)
    
    # Redirect to home page after deletion.
    return redirect(url_for("home"))

@app.route('/addquiz', methods=['GET', 'POST'])
def addquiz():
    if request.method == 'GET':
        return render_template("addquiz.html")
    # For POST, process the addition (placeholder logic)
    return render_template("addquiz.html", message="Quiz uploaded successfully!")

@app.route('/<quiz_name>', methods=['GET'])
def quiz_index(quiz_name):
    session['quiz_name'] = quiz_name

    # Read the quiz questions.
    try:
        questions = read_quiz(quiz_name)
    except Exception as e:
        return f"Error reading quiz: {str(e)}", 500

    if not questions:
        return "No questions available.", 404

    # Load the current question index for this client from the JSON file.
    question_file = os.path.join(os.path.dirname(__file__), "non_static", "question", f"{quiz_name}.json")
    try:
        with open(question_file, "r", encoding="utf-8") as f:
            question_data = json.load(f)
    except Exception as e:
        question_data = {}

    client_ip = get_client_ip()
    current_index = question_data.get(client_ip, 0)

    # Ensure the index is within range.
    if current_index >= len(questions):
        current_index = 0
        question_data[client_ip] = 0
        with open(question_file, "w", encoding="utf-8") as f:
            json.dump(question_data, f)

    # Pass the current question and its one-based index to the template.
    question = questions[current_index]
    display_index = current_index + 1
    return render_template("quiz.html", quiz_name=quiz_name, question=question, question_index=display_index)

@app.route('/editquiz/<quiz_name>', methods=['GET', 'POST'])
def edit_quiz(quiz_name):
    quiz_file = os.path.join(os.path.dirname(__file__), "non_static", "quiz", f"{quiz_name}.txt")
    question_file = os.path.join(os.path.dirname(__file__), "non_static", "question", f"{quiz_name}.json")
    
    if request.method == 'GET':
        # Read quiz text content.
        try:
            with open(quiz_file, "r", encoding="utf-8") as f:
                quiz_content = f.read()
        except Exception as e:
            quiz_content = ""
        # Read question JSON
        try:
            with open(question_file, "r", encoding="utf-8") as f:
                question_data = json.load(f)
        except Exception as e:
            question_data = {}
        return render_template("editquiz.html", quiz_name=quiz_name, quiz_content=quiz_content, question_data=question_data)
    else:
        # POST: update both the quiz text and the question data.
        new_content = request.form.get("quiz_content")
        # This assumes the form passes the question data as a JSON string.
        question_data_str = request.form.get("question_data")
        try:
            new_question_data = json.loads(question_data_str) if question_data_str else {}
        except Exception as e:
            new_question_data = {}

        # Write updated quiz text.
        try:
            with open(quiz_file, "w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception as e:
            return f"Error updating quiz text: {str(e)}", 500

        # Write updated question JSON.
        try:
            with open(question_file, "w", encoding="utf-8") as f:
                json.dump(new_question_data, f)
        except Exception as e:
            return f"Error updating question data: {str(e)}", 500

        message = "Quiz and question updated successfully!"
        return render_template("editquiz.html", quiz_name=quiz_name, quiz_content=new_content, question_data=new_question_data, message=message)

@app.route('/<quiz_name>/quiz/validate', methods=['POST'])
def quiz_validate(quiz_name):
    answer = request.json.get('answer', '')
    # Load quiz questions.
    try:
        questions = read_quiz(quiz_name)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not questions:
        return jsonify({'error': 'No questions found.'}), 404

    # Load the current question index for the client.
    question_file = os.path.join(os.path.dirname(__file__), "non_static", "question", f"{quiz_name}.json")
    try:
        with open(question_file, "r", encoding="utf-8") as f:
            question_data = json.load(f)
    except Exception as e:
        question_data = {}

    client_ip = get_client_ip()
    current_index = question_data.get(client_ip, 0)
    # Make sure the index is valid.
    if current_index >= len(questions):
        current_index = 0

    # Get correct answer from the current question.
    correct_answer = questions[current_index].get('answer', '')
    is_correct = answer.strip().lower() == correct_answer.strip().lower()

    if is_correct:
        # Increment the index (or reset when finished).
        new_index = current_index + 1
        if new_index >= len(questions):
            new_index = 0  # or you could return a finish page instead
        question_data[client_ip] = new_index
        try:
            with open(question_file, "w", encoding="utf-8") as f:
                json.dump(question_data, f)
        except Exception as e:
            return jsonify({'error': 'Failed to update question index.'}), 500

    return jsonify({'is_correct': is_correct})

@app.route('/makequiz', methods=['GET', 'POST'])
def makequiz():
    if request.method == 'POST':
        # Retrieve form data.
        filename = request.form.get("filename")
        quiz_content = request.form.get("quiz_content")
        # Define the quiz file path.
        quiz_dir = os.path.join(os.path.dirname(__file__), "non_static", "quiz")
        if not os.path.exists(quiz_dir):
            os.makedirs(quiz_dir)
        quiz_file = os.path.join(quiz_dir, f"{filename}.txt")
        try:
            with open(quiz_file, "w", encoding="utf-8") as f:
                f.write(quiz_content)
        except Exception as e:
            return f"Error saving quiz: {str(e)}", 500
        message = "Quiz created successfully!"
        return render_template("makequiz.html", message=message)
    return render_template("makequiz.html")

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5702)