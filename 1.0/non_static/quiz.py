import random
import os

def read_questions():
    # Build the file path to quiz.txt located in the same folder
    file_path = os.path.join(os.path.dirname(__file__), "quiz.txt")
    questions = []
    with open(file_path, "r", encoding="utf-8") as f:
        # Read non-empty lines
        lines = [line.strip() for line in f if line.strip()]
    # Every two lines form a question and answer pair
    for i in range(0, len(lines), 2):
        if i + 1 < len(lines):
            questions.append({'question': lines[i], 'answer': lines[i+1]})
    return questions

def get_random_question():
    questions = read_questions()
    if questions:
        return random.choice(questions)
    return {'question': "No questions available", 'answer': ""}

def validate_answer(question, user_answer):
    return question['answer'].strip().lower() == user_answer.strip().lower()