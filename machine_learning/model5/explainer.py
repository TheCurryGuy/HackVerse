import os
import json
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_pitches(repo_data: dict) -> dict:

    prompt = f"""
You are an expert tech communicator who writes amazing project pitches for hackathons.
You will be given everything available about a GitHub project.
Use all sources intelligently — if the README is detailed use it heavily,
if it is short or missing, rely more on the dependencies and file structure.
Never mention missing information in your response.
Do not treat folder or file names as literal feature names.
Understand the overall purpose of the project from all sources combined.

━━━━━━━━━━━━━━━━━━━━━━━━
PROJECT NAME:
{repo_data['name']}

DESCRIPTION:
{repo_data['description']}

TECH STACK DETECTED:
{', '.join(repo_data['tech_stack'])}

TOPICS / TAGS:
{', '.join(repo_data['topics']) if repo_data['topics'] else 'None'}

README:
{repo_data['readme']}

DEPENDENCIES:
{repo_data['dependencies']}

FILE & FOLDER STRUCTURE:
{chr(10).join(repo_data['file_structure'])}
━━━━━━━━━━━━━━━━━━━━━━━━

Based on ALL of the above, generate three versions of a project explanation.

Return ONLY a valid JSON object with exactly these three keys:
- "one_liner": A catchy tagline. Format: "ProjectName: what it does". Example: "HackVerse: AI-powered hackathon management platform". Max 20 words.
- "tech_pitch": 3-4 sentences. A clear and exciting explanation of what the project does. No jargon.
- "full_explanation": 3 paragraphs. Technical and detailed, written for judges and developers.

Return only the JSON. No extra text, no markdown, no code blocks.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"```json|```", "", raw).strip()
    raw = re.sub(r'[\x00-\x1f\x7f]', ' ', raw)
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        raw = match.group()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        retry_response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": raw},
                {"role": "user", "content": "Your response had invalid JSON. Return ONLY the JSON object, no special characters, no newlines inside values, no apostrophes. Use simple plain English only."}
            ],
            temperature=0.3,
        )
        raw2 = retry_response.choices[0].message.content.strip()
        raw2 = re.sub(r"```json|```", "", raw2).strip()
        raw2 = re.sub(r'[\x00-\x1f\x7f]', ' ', raw2)
        match2 = re.search(r'\{.*\}', raw2, re.DOTALL)
        if match2:
            raw2 = match2.group()
        result = json.loads(raw2)

    # Rename if LLM used wrong keys
    if "elevator_pitch" in result:
        result["tech_pitch"] = result.pop("elevator_pitch")
    if "short_summary" in result:
        result["tech_pitch"] = result.pop("short_summary")
    if "detailed_summary" in result:
        result["full_explanation"] = result.pop("detailed_summary")
    if "project_title" in result:
        result["one_liner"] = result.pop("project_title")

    return result