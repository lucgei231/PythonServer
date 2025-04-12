from flask import Flask, render_template, jsonify, request
import random
from non_static.utils import example_util_function, ExampleUtility
from non_static.quiz import get_random_question, validate_answer, read_questions

app = Flask(__name__)
all_questions = read_questions()


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/quiz/question', methods=['GET'])
def quiz_question():
    question_and_answer = random.choice(all_questions)
    question = {
        "question": question_and_answer["question"]
    }
    print(f"User asked for a question: {question}")
    return jsonify(question)

@app.route('/quiz/validate', methods=['POST'])
def quiz_validate():
    # Receive the entire question and the user answer from the request body
    answer = request.json.get('answer')
    question = request.json.get('question')

    is_correct = False
    
    for possible_question in all_questions:
        if possible_question["question"] == question:
            is_correct = answer == possible_question["answer"]
            break

    print(f"User answered question: {question} and said '{answer}'")
    return jsonify({'is_correct': is_correct})

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5601)