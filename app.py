import os
import json
import re

import requests

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session
)

from werkzeug.utils import secure_filename
from pypdf import PdfReader


app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "change-this-secret-key"
)

UPLOAD_FOLDER = "uploads"

ALLOWED_EXTENSIONS = {"pdf"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DEFAULT_QUESTIONS = [
    {
        "question": "Tell me about yourself.",
        "type": "HR"
    },
    {
        "question": "What are your strengths?",
        "type": "HR"
    },
    {
        "question": "What is your biggest weakness?",
        "type": "HR"
    },
    {
        "question": "Why should we hire you?",
        "type": "HR"
    },
    {
        "question": "Where do you see yourself in five years?",
        "type": "HR"
    },
    {
        "question": "Explain one technical project you have worked on.",
        "type": "Technical"
    },
    {
        "question": "What programming language are you most comfortable with and why?",
        "type": "Technical"
    },
    {
        "question": "What is the difference between a list and a tuple in Python?",
        "type": "Technical"
    },
    {
        "question": "What is a database and why is it used?",
        "type": "Technical"
    },
    {
        "question": "How do you debug an application when it is not working?",
        "type": "Technical"
    }
]

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def extract_resume_text(filepath):

    text = ""

    try:

        reader = PdfReader(filepath)

        for page in reader.pages:

            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

    except Exception as error:

        print("Resume error:", error)

    return text[:12000]


def fallback_questions(role):

    questions = []

    questions.extend(DEFAULT_QUESTIONS)

    if role:

        questions[5] = {
            "question":
                "Explain an important project or task related to "
                + role
                + " that you have worked on.",
            "type": "Technical"
        }

        questions[6] = {
            "question":
                "What skills are important for a "
                + role
                + "?",
            "type": "Technical"
        }

    return questions

def call_gemini(prompt):

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:

        return None

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/gemini-3.7-flash:generateContent"
    )

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }

    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

    try:

        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=60
        )

        if response.status_code != 200:

            print(
                "Gemini API error:",
                response.status_code,
                response.text
            )

            return None

        result = response.json()

        text = (
            result
            .get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text")
        )

        return text

    except Exception as error:

        print("Gemini error:", error)

        return None

def generate_questions(name, role, experience, resume_text):

    if not os.environ.get("GEMINI_API_KEY"):

        return fallback_questions(role)

    prompt = f"""
You are an expert technical interviewer.

Create exactly 10 interview questions.

Candidate name:
{name}

Job role:
{role}

Experience:
{experience}

Resume:
{resume_text[:8000]}

Requirements:

- 5 HR/behavioral questions
- 5 technical questions
- Technical questions should match the job role.
- If resume information is available, ask questions related to it.
- Questions should be suitable for a student or entry-level candidate.
- Do not ask extremely advanced questions.
- Return ONLY valid JSON.
- Do not use markdown.

Format:

[
  {{
    "question": "question here",
    "type": "HR"
  }},
  {{
    "question": "question here",
    "type": "Technical"
  }}
]
"""

    result = call_gemini(prompt)

    if not result:

        return fallback_questions(role)

    try:

        result = result.strip()

        result = re.sub(
            r"^```json\s*",
            "",
            result
        )

        result = re.sub(
            r"\s*```$",
            "",
            result
        )

        questions = json.loads(result)

        if isinstance(questions, list):

            cleaned = []

            for item in questions[:10]:

                if (
                    isinstance(item, dict)
                    and "question" in item
                ):

                    cleaned.append({
                        "question": str(
                            item["question"]
                        ),
                        "type": str(
                            item.get(
                                "type",
                                "Technical"
                            )
                        )
                    })

            if len(cleaned) >= 5:

                return cleaned

    except Exception as error:

        print(
            "Question JSON error:",
            error
        )

    return fallback_questions(role)

def evaluate_interview(
    name,
    role,
    experience,
    questions,
    answers
):

    if not os.environ.get("GEMINI_API_KEY"):

        return fallback_evaluation(
            questions,
            answers
        )

    interview_text = ""

    for index in range(len(questions)):

        question = questions[index]["question"]

        answer = answers[index]

        interview_text += (
            "\nQuestion "
            + str(index + 1)
            + ": "
            + question
            + "\nAnswer: "
            + answer
            + "\n"
        )

    prompt = f"""
You are a professional interview evaluator.

Evaluate this candidate interview.

Candidate:
{name}

Role:
{role}

Experience:
{experience}

Interview:
{interview_text}

Evaluate every answer.

For each question provide:

- score from 0 to 10
- short feedback
- improvement suggestion

Also provide:

- overall_score from 0 to 100
- strengths
- weaknesses
- final_feedback

Return ONLY valid JSON.

Format:

{{
  "overall_score": 75,
  "question_results": [
    {{
      "score": 8,
      "feedback": "Good answer.",
      "improvement": "Add a practical example."
    }}
  ],
  "strengths": [
    "Good communication"
  ],
  "weaknesses": [
    "Needs stronger technical explanation"
  ],
  "final_feedback": "Overall feedback here."
}}
"""

    result = call_gemini(prompt)

    if not result:

        return fallback_evaluation(
            questions,
            answers
        )

    try:

        result = result.strip()

        result = re.sub(
            r"^```json\s*",
            "",
            result
        )

        result = re.sub(
            r"\s*```$",
            "",
            result
        )

        evaluation = json.loads(result)

        return evaluation

    except Exception as error:

        print(
            "Evaluation JSON error:",
            error
        )

        return fallback_evaluation(
            questions,
            answers
        )

def fallback_evaluation(
    questions,
    answers
):

    results = []

    total = 0

    for answer in answers:

        length = len(answer.strip())

        if length == 0:

            score = 0

        elif length < 50:

            score = 4

        elif length < 100:

            score = 6

        elif length < 200:

            score = 8

        else:

            score = 9

        total += score

        results.append({
            "score": score,
            "feedback":
                "Answer contains useful information.",
            "improvement":
                "Add clearer examples and more specific details."
        })

    if results:

        overall = int(
            (total / len(results)) * 10
        )

    else:

        overall = 0

    return {
        "overall_score": overall,
        "question_results": results,
        "strengths": [
            "Completed the interview",
            "Attempted the questions"
        ],
        "weaknesses": [
            "AI evaluation is not enabled",
            "Answers can be more detailed"
        ],
        "final_feedback":
            "Add a Gemini API key to enable full AI evaluation."
    }


@app.route("/")
def home():

    return render_template(
        "index.html"
    )


@app.route(
    "/start",
    methods=["POST"]
)
def start():

    name = request.form.get(
        "name",
        ""
    ).strip()

    role = request.form.get(
        "role",
        "Software Developer"
    ).strip()

    experience = request.form.get(
        "experience",
        "Fresher"
    ).strip()

    resume_text = ""

    resume = request.files.get(
        "resume"
    )

    if resume and resume.filename:

        if allowed_file(
            resume.filename
        ):

            filename = secure_filename(
                resume.filename
            )

            filepath = os.path.join(
                UPLOAD_FOLDER,
                filename
            )

            resume.save(filepath)

            resume_text = extract_resume_text(
                filepath
            )

    if not name:

        return redirect(
            url_for("home")
        )

    questions = generate_questions(
        name,
        role,
        experience,
        resume_text
    )

    session["name"] = name

    session["role"] = role

    session["experience"] = experience

    session["resume_text"] = resume_text

    session["questions"] = questions

    session["answers"] = []

    session["evaluation"] = None

    return redirect(
        url_for(
            "interview",
            q=0
        )
    )



@app.route("/interview")
def interview():

    questions = session.get(
        "questions",
        DEFAULT_QUESTIONS
    )

    q = request.args.get(
        "q",
        0,
        type=int
    )

    if q < 0:

        q = 0

    if q >= len(questions):

        return redirect(
            url_for("result")
        )

    return render_template(
        "interview.html",
        name=session.get(
            "name",
            "Candidate"
        ),
        role=session.get(
            "role",
            "Software Developer"
        ),
        question=questions[q]["question"],
        question_type=questions[q]["type"],
        q=q,
        total=len(questions)
    )


@app.route(
    "/submit",
    methods=["POST"]
)
def submit():

    answer = request.form.get(
        "answer",
        ""
    ).strip()

    q = request.form.get(
        "q",
        0,
        type=int
    )

    questions = session.get(
        "questions",
        DEFAULT_QUESTIONS
    )

    answers = session.get(
        "answers",
        []
    )

    while len(answers) <= q:

        answers.append("")

    answers[q] = answer

    session["answers"] = answers

    next_q = q + 1

    if next_q >= len(questions):

        evaluation = evaluate_interview(
            session.get(
                "name",
                "Candidate"
            ),
            session.get(
                "role",
                "Software Developer"
            ),
            session.get(
                "experience",
                "Fresher"
            ),
            questions,
            answers
        )

        session["evaluation"] = evaluation

        return redirect(
            url_for("result")
        )

    return redirect(
        url_for(
            "interview",
            q=next_q
        )
    )


@app.route("/result")
def result():

    evaluation = session.get(
        "evaluation"
    )

    if not evaluation:

        return redirect(
            url_for("home")
        )

    questions = session.get(
        "questions",
        DEFAULT_QUESTIONS
    )

    answers = session.get(
        "answers",
        []
    )

    question_results = evaluation.get(
        "question_results",
        []
    )

    combined_results = []

    for index in range(
        len(questions)
    ):

        answer = ""

        if index < len(answers):

            answer = answers[index]

        result = {}

        if index < len(
            question_results
        ):

            result = question_results[index]

        combined_results.append({
            "question":
                questions[index]["question"],

            "type":
                questions[index]["type"],

            "answer":
                answer,

            "score":
                result.get(
                    "score",
                    0
                ),

            "feedback":
                result.get(
                    "feedback",
                    "No feedback available."
                ),

            "improvement":
                result.get(
                    "improvement",
                    "Try to give a more detailed answer."
                )
        })

    return render_template(
        "result.html",

        name=session.get(
            "name",
            "Candidate"
        ),

        role=session.get(
            "role",
            "Software Developer"
        ),

        overall_score=evaluation.get(
            "overall_score",
            0
        ),

        strengths=evaluation.get(
            "strengths",
            []
        ),

        weaknesses=evaluation.get(
            "weaknesses",
            []
        ),

        final_feedback=evaluation.get(
            "final_feedback",
            ""
        ),

        results=combined_results
    )


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=True
    )