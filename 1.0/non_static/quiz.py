import random
import os

def read_quiz(quiz_name):
    # Build the file path to the quiz file in the "quiz" subfolder
    file_path = os.path.join(os.path.dirname(__file__), "quiz", f"{quiz_name}.txt")
    questions = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            # Read non-empty lines
            lines = [line.strip() for line in f if line.strip()]
        # Every two lines form a question and its answer
        for i in range(0, len(lines), 2):
            if i + 1 < len(lines):
                questions.append({'question': lines[i], 'answer': lines[i+1]})
    except FileNotFoundError:
        questions.append({'question': "Quiz file not found", 'answer': ""})
    return questions

def get_random_question(quiz_name):
    questions = read_quiz(quiz_name)
    if questions:
        return random.choice(questions)
    return {'question': "No questions available", 'answer': ""}

def validate_answer(question, user_answer):
    return question['answer'].strip().lower() == user_answer.strip().lower()