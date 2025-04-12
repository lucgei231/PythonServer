def get_random_question():
    questions = [
        {"question": "What is the capital of France?", "answer": "Paris"},
        {"question": "What is 2 + 2?", "answer": "4"},
        {"question": "What is the largest planet in our solar system?", "answer": "Jupiter"},
    ]
    import random
    return random.choice(questions)

def validate_answer(question, user_answer):
    return question['answer'].strip().lower() == user_answer.strip().lower()