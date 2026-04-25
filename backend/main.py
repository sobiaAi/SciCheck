from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from analyzer import analyze, analyze_files
from models import AnalyzeFilesRequest, AnalyzeRequest, AnalyzeResponse


app = FastAPI(title="SciCheck API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_endpoint(req: AnalyzeRequest) -> AnalyzeResponse:
    try:
        findings, elapsed, checked = await analyze(req.code, req.domain)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return AnalyzeResponse(
        domain=req.domain,
        patterns_checked=checked,
        analysis_time_seconds=round(elapsed, 2),
        findings=findings,
        clean=all(not f.found for f in findings) if findings else True,
    )


@app.post("/analyze/files", response_model=AnalyzeResponse)
async def analyze_files_endpoint(req: AnalyzeFilesRequest) -> AnalyzeResponse:
    try:
        files = {f.name: f.content for f in req.files}
        findings, elapsed, checked = await analyze_files(files, req.domain)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return AnalyzeResponse(
        domain=req.domain,
        patterns_checked=checked,
        analysis_time_seconds=round(elapsed, 2),
        findings=findings,
        clean=all(not f.found for f in findings) if findings else True,
    )
