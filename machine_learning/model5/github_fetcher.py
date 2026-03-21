import requests
import base64
import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def fetch_repo_data(github_url: str) -> dict:
    parts = github_url.rstrip("/").split("/")
    owner = parts[-2]
    repo  = parts[-1]

    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    # ── 1. Basic metadata ──────────────────────────────
    meta = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}",
        headers=headers
    ).json()

    # ── 2. Languages ───────────────────────────────────
    languages_resp = requests.get(
        meta.get("languages_url", ""),
        headers=headers
    ).json()
    detected_stack = list(languages_resp.keys())

    # ── 3. Topics ──────────────────────────────────────
    topics_resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/topics",
        headers={**headers, "Accept": "application/vnd.github.mercy-preview+json"}
    ).json()
    topics = topics_resp.get("names", [])

    # ── 4. README ──────────────────────────────────────
    readme_resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/readme",
        headers=headers
    ).json()

    if "content" in readme_resp:
        readme_text = base64.b64decode(
            readme_resp["content"]
        ).decode("utf-8", errors="ignore")[:3000]
    else:
        readme_text = "Not provided"

    # ── 5. File & folder structure ─────────────────────
    tree_resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1",
        headers=headers
    ).json()
    all_files = [
        f["path"] for f in tree_resp.get("tree", [])
        if f["type"] == "blob"
    ]

    # ── 6. Dependencies ────────────────────────────────
    dependencies = "Not found"

    # Check package.json first (Node/JS projects)
    if any("package.json" in f for f in all_files):
        pkg_resp = requests.get(
            f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/package.json",
            headers=headers
        )
        if pkg_resp.status_code == 200:
            try:
                pkg = pkg_resp.json()
                deps = list(pkg.get("dependencies", {}).keys())
                dev_deps = list(pkg.get("devDependencies", {}).keys())
                dependencies = f"dependencies: {', '.join(deps)} | devDependencies: {', '.join(dev_deps)}"
            except:
                pass

    # ── 7. Contributors ────────────────────────────────
    contributors_resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/contributors",
        headers=headers
    ).json()
    
    contributors = []
    if isinstance(contributors_resp, list):
        for c in contributors_resp[:10]:  # max 10
            contributors.append({
                "username": c.get("login", ""),
                "contributions": c.get("contributions", 0)
            })

    # Check requirements.txt (Python projects)
    if dependencies == "Not found" and any("requirements.txt" in f for f in all_files):
        req_resp = requests.get(
            f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/requirements.txt",
            headers=headers
        )
        if req_resp.status_code == 200:
            dependencies = req_resp.text[:1000]

    # Clean file list — just top 40 most meaningful files
    skip_extensions = {
        ".png", ".jpg", ".jpeg", ".gif", ".svg",
        ".ico", ".lock", ".map", ".min.js"
    }
    clean_files = [
        f for f in all_files
        if not any(f.endswith(ext) for ext in skip_extensions)
    ][:40]

    return {
        "name":           meta.get("name", "Unknown"),
        "description":    meta.get("description") or "Not provided",
        "tech_stack":     detected_stack,
        "topics":         topics,
        "readme":         readme_text,
        "file_structure": clean_files,
        "dependencies":   dependencies,
        "contributors":   contributors,   # ← new!
    }