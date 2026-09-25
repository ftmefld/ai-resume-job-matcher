import requests

url = "http://127.0.0.1:8000/analyze"

data = {
    "resume_text": "I have experience with Python, machine learning, FastAPI, and Git.",
    "job_description": "We are looking for an AI engineer with Python, SQL, Docker, FastAPI, and prompt engineering experience."
}

response = requests.post(url, json=data)

print(response.status_code)
print(response.json())