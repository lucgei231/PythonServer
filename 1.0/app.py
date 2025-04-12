from flask import Flask, render_template, jsonify
import random
from non_static.utils import example_util_function, ExampleUtility
from non_static.quiz import get_random_question, validate_answer

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/quiz/question', methods=['GET'])
def quiz_question():
    question = get_random_question()
    return jsonify(question)

@app.route('/quiz/validate', methods=['POST'])
def quiz_validate():
    # Assuming the answer is sent in the request body
    answer = request.json.get('answer')
    question_id = request.json.get('question_id')
    is_correct = validate_answer(question_id, answer)
    return jsonify({'is_correct': is_correct})

if __name__ == '__main__':
    app.run(debug=True)