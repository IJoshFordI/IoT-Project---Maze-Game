"""Generate and validate multiple-choice cybersecurity questions with Ollama."""

import json


DIFFICULTY_GUIDANCE = {
    "Easy": "Ask about a familiar safety basic with an obvious answer.",
    "Medium": "Use one simple everyday IoT situation and ask for the safest basic action.",
    "Hard": "Use one short beginner-friendly situation that needs one extra reasoning step, but no specialist knowledge.",
}


def _normalize_question(data, difficulty):
    """Return a predictable question shape for the game UI."""
    if not isinstance(data, dict):
        raise ValueError("Ollama returned a question that was not a JSON object.")

    question_text = str(data.get("question", "")).strip()
    if not question_text:
        raise ValueError("Ollama did not include question text.")

    raw_options = data.get("options")
    if isinstance(raw_options, dict):
        options = {str(key).strip().upper(): str(value).strip() for key, value in raw_options.items()}
    elif isinstance(raw_options, list):
        options = {}
        for index, option in enumerate(raw_options[:4]):
            letter = chr(65 + index)
            if isinstance(option, dict):
                letter = str(option.get("letter", letter)).strip().upper()
                option = option.get("text", option.get("answer", ""))
            options[letter] = str(option).strip()
    else:
        raise ValueError("Ollama returned options in an unsupported format.")

    options = {letter: options.get(letter, "") for letter in "ABCD"}
    if any(not options[letter] for letter in "ABCD"):
        raise ValueError("Ollama must return four options labelled A, B, C, and D.")

    raw_answer = str(data.get("correct_answer", "")).strip()
    answer = raw_answer.upper()
    if answer not in options:
        answer = next(
            (letter for letter, option in options.items() if option.casefold() == raw_answer.casefold()),
            "",
        )
    if answer not in options:
        raise ValueError("Ollama did not identify the correct answer as A, B, C, or D.")

    return {
        "difficulty": difficulty,
        "question": question_text,
        "options": options,
        "correct_answer": answer,
        "explanation": str(data.get("explanation", "")).strip(),
    }


def generate_question(difficulty="Easy"):
    """Generate one IoT cybersecurity question at the requested difficulty."""
    difficulty = str(difficulty).title()
    if difficulty not in DIFFICULTY_GUIDANCE:
        raise ValueError("Difficulty must be Easy, Medium, or Hard.")

    # Import requests only when generation is requested so the maze can still
    # launch and display a helpful error if the optional package is missing.
    import requests

    prompt = f"""Write one short, beginner-friendly IoT cybersecurity multiple-choice question.
Difficulty: {difficulty}. {DIFFICULTY_GUIDANCE[difficulty]}
Use familiar words, four concise and plausible options, and exactly one correct answer.
Return only a JSON object with: question, options (A, B, C, D), correct_answer (letter), and a one-sentence explanation.
Avoid jargon, obscure facts, trick answers, and multi-step analysis."""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2:3b",
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "keep_alive": "10m",
            "options": {"num_predict": 220},
        },
        timeout=120,
    )
    response.raise_for_status()
    return _normalize_question(json.loads(response.json()["response"]), difficulty)


if __name__ == "__main__":
    try:
        question = generate_question("Easy")
        print("\n=== CYBER CHALLENGE ===")
        print(f"Difficulty: {question['difficulty']}")
        print(question["question"])
        for letter, option in question["options"].items():
            print(f"{letter}. {option}")
        answer = input("\nYour answer (A/B/C/D): ").strip().upper()
        if answer == question["correct_answer"]:
            print("\nCorrect! Door unlocked.")
        else:
            print(f"\nIncorrect. The correct answer was {question['correct_answer']}.")
        print("Explanation:", question["explanation"])
    except Exception as error:
        print("Error:", error)
