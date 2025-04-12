document.addEventListener('DOMContentLoaded', function() {
    const quizForm = document.getElementById('quiz-form');
    const questionDisplay = document.getElementById('question-display');
    const answerInput = document.getElementById('answer-input');
    const submitButton = document.getElementById('submit-button');

    quizForm.addEventListener('submit', function(event) {
        event.preventDefault();
        const userAnswer = answerInput.value;
        // Here you would typically send the answer to the server for validation
        console.log('User answer submitted:', userAnswer);
        answerInput.value = ''; // Clear the input field
    });

    function displayQuestion(question) {
        questionDisplay.textContent = question;
    }

    // Example of displaying a question (this would be replaced with dynamic content)
    displayQuestion('What is the capital of France?');
});