import random
import os

def read_quiz(quiz_name):
    # Use the directory of this file as the base (which is ...\non_static)
    base_dir = os.path.dirname(__file__)
    # Append only the 'quiz' folder since this file is already in non_static
    quiz_dir = os.path.join(base_dir, "quiz")
    file_path = os.path.join(quiz_dir, f"{quiz_name}.txt")
    print("Reading quiz file from:", file_path)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Quiz file {file_path} not found")
        
    # Read and parse the quiz file
    questions = []ssss
    with open(file_path, "r", encoding="utf-8") as f:
        # Assume each question is separated by a newline and the answer follows on the next line
        lines = [line.strip() for line in f if line.strip()]
        i = 0
        while i < len(lines):
            question = lines[i]
            # Check if the next line exists for the answer
            answer = lines[i+1] if i+1 < len(lines) else ""
            questions.append({"question": question, "answer": answer})
            i += 2  # Move to the next question
    # Ensure questions are returned in their original order
    return questions

def get_random_question(quiz_name):
    questions = read_quiz(quiz_name)
    if questions:
        return random.choice(questions)
    return {'question': "No questions available", 'answer': ""}

def validate_answer(question, user_answer):
    return question['answer'].strip().lower() == user_answer.strip().lower()
