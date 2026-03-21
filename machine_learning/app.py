from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from fastapi.responses import FileResponse, JSONResponse
from typing import List
import os
import shutil
from io import BytesIO
import pandas as pd

from machine_learning.model2.main import allocate_rooms   
from machine_learning.model3.main import get_predictions_csv_path_for, predict_score_from_json
from pydantic import BaseModel
import tempfile

from machine_learning.model1.part1 import evaluate_candidate
from machine_learning.model1.part2 import form_teams_from_csv

from machine_learning.model5.github_fetcher import fetch_repo_data
from machine_learning.model5.explainer import generate_pitches

app = FastAPI(title="Machine Learning Models API")

BASE_DIR = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.get("/")
def home():
    return {"message": "Welcome to the Machine Learning Models API"}


# --- Model 1 Endpoint ---
class CandidateInput(BaseModel):
    name: str
    tech_stack_used: str


## --- Endpoint 1: Evaluate Candidate ---
@app.post("/model1/evaluate")
def evaluate_candidate_api(data: CandidateInput):
   

    cleaned_stack = data.tech_stack_used.replace("  ", ",").replace(" ,", ",").strip()
    skills = [s.strip() for s in cleaned_stack.split(",") if s.strip()]

    name, score, eligible_to = evaluate_candidate(data.name, skills)

    return {
        "name": name,
        "score": score,
        "eligible_to": eligible_to
    }

## --- Endpoint 2: Form Teams ---
@app.post("/model1/form_teams", response_class=FileResponse)
async def form_teams(file: UploadFile = File(...)):
    

    content = await file.read()
    csv_content = content.decode("utf-8")

    teams_csv = form_teams_from_csv(csv_content)

    os.makedirs("outputs", exist_ok=True)
    file_path = "outputs/teams.csv"
    with open(file_path, "w", encoding="utf-8", newline="") as f:
        f.write(teams_csv)

    return FileResponse(
        path=file_path,
        filename="teams.csv",
        media_type="text/csv"
    )
    
    

# --- Model 2 Endpoint upload 1 CSV + two integers) ---
@app.post("/model2/upload")
async def upload_and_run_model2(file: UploadFile = File(...), no_of_rooms_available: int = Query(...), each_room_capacity: int = Query(...)):
    try:
        teams_df = pd.read_csv(BytesIO(await file.read()))

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        final_output_path = os.path.abspath(os.path.join(OUTPUT_DIR, "room_allocation.csv"))
        allocate_rooms(teams_df, no_of_rooms_available, each_room_capacity, final_output_path)

        if not os.path.exists(final_output_path):
            raise RuntimeError("Model 2 did not produce an output CSV.")

        return FileResponse(final_output_path, filename="room_allocation.csv", media_type="text/csv")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Model 3 Endpoint (upload CSV, save + download) ---
@app.post("/model3/upload")
async def upload_and_run_model3(file: UploadFile = File(...)):
    try:
        fd, temp_input_path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        contents = await file.read()
        with open(temp_input_path, "wb") as f:
            f.write(contents)

        source_output = os.path.abspath(get_predictions_csv_path_for(temp_input_path))
        
        if not os.path.exists(source_output):
            raise RuntimeError(f"Model 3 did not produce an output CSV at: {source_output}")

        final_output_path = os.path.abspath(os.path.join(OUTPUT_DIR, "predicted_scores.csv"))
        os.makedirs(os.path.dirname(final_output_path), exist_ok=True)
        try:
            shutil.copyfile(source_output, final_output_path)
            path_to_return = final_output_path
        except Exception:
            path_to_return = source_output

        return FileResponse(path_to_return, filename="predicted_scores.csv", media_type="text/csv")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            if 'temp_input_path' in locals() and os.path.exists(temp_input_path):
                os.remove(temp_input_path)
        except Exception:
            pass


# --- Model 3 JSON Endpoint ---

class TeamInput(BaseModel):
    team_name: str
    tech_stack_used: str
    
@app.post("/model3/predict")
def predict_score(team_input: TeamInput):
    try:
        json_input = {
            "team_name": team_input.team_name,
            "tech_stack_used": team_input.tech_stack_used
        }
        predicted_score = predict_score_from_json(json_input)
        return {
            "name": team_input.team_name,
            "score": predicted_score
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# --- Model 5 Endpoint (AI Project Explanation) ---
class ExplainRequest(BaseModel):
    github_url: str
    team_id:    str

class ExplainResponse(BaseModel):
    one_liner:        str
    tech_pitch:       str
    full_explanation: str
    tech_stack_used:  list[str]
    contributors:     list[str]

@app.post("/model5/explain", response_model=ExplainResponse)
async def explain_project(req: ExplainRequest):
    try:
        repo_data = fetch_repo_data(req.github_url)
        pitches   = generate_pitches(repo_data)
        return ExplainResponse(
            one_liner        = pitches["one_liner"],
            tech_pitch       = pitches["tech_pitch"],
            full_explanation = pitches["full_explanation"],
            tech_stack_used  = repo_data["tech_stack"],
            contributors     = [f"{c['username']}: {c['contributions']}" for c in repo_data["contributors"]]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))