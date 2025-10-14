"""
FastAPI application for code analysis service.
"""
import os
import shutil
import tempfile
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from models import AnalysisReport
from agent import CodeAnalysisAgent
from utils import extract_zip


# Initialize FastAPI app
app = FastAPI(
    title="Code Analysis Agent API",
    description="AI-powered code analysis service for feature location",
    version="1.0.0"
)

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load settings
settings = get_settings()

# Create temp directory if it doesn't exist
os.makedirs(settings.temp_dir, exist_ok=True)


@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    print(f"Starting Code Analysis Agent API")
    print(f"AI Provider: Gemini CLI")
    print(f"Host: {settings.host}:{settings.port}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("Shutting down Code Analysis Agent API")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint serving the HTML interface."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/info")
async def api_info():
    """API information endpoint."""
    return {
        "message": "Code Analysis Agent API",
        "version": "1.0.0",
        "endpoints": {
            "analyze": "/api/analyze",
            "health": "/health",
            "info": "/api/info"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "ai_provider": "gemini-cli",
        "port": settings.port
    }


@app.post("/api/analyze", response_model=AnalysisReport)
async def analyze_code(
    problem_description: str = Form(..., description="Natural language description of features"),
    code_zip: UploadFile = File(..., description="Zip file containing the source code")
) -> AnalysisReport:
    """
    Analyze a codebase and generate a feature location report.

    Args:
        problem_description: Natural language description of features to implement
        code_zip: Zip file containing the complete source code

    Returns:
        AnalysisReport with feature analysis and execution plan
    """
    temp_zip_path = None
    temp_extract_dir = None

    try:
        # Validate file size
        file_size = 0
        chunk_size = 1024 * 1024  # 1MB chunks
        temp_zip_path = tempfile.mktemp(suffix='.zip', dir=settings.temp_dir)

        # Save uploaded file
        with open(temp_zip_path, 'wb') as f:
            while chunk := await code_zip.read(chunk_size):
                file_size += len(chunk)
                if file_size > settings.max_upload_size:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File size exceeds maximum allowed size of {settings.max_upload_size} bytes"
                    )
                f.write(chunk)

        # Validate it's a zip file
        if not temp_zip_path.endswith('.zip'):
            raise HTTPException(
                status_code=400,
                detail="Uploaded file must be a zip file"
            )

        # Extract the zip file
        temp_extract_dir = tempfile.mkdtemp(dir=settings.temp_dir)
        extract_zip(temp_zip_path, temp_extract_dir)

        # Initialize agent
        agent = CodeAnalysisAgent(settings)

        # Analyze the codebase
        report = agent.analyze_codebase(
            problem_description=problem_description,
            code_directory=temp_extract_dir
        )

        return report

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error analyzing code: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing code: {str(e)}"
        )
    finally:
        # Cleanup temporary files
        if temp_zip_path and os.path.exists(temp_zip_path):
            try:
                os.remove(temp_zip_path)
            except Exception as e:
                print(f"Error removing temp zip: {e}")

        if temp_extract_dir and os.path.exists(temp_extract_dir):
            try:
                shutil.rmtree(temp_extract_dir)
            except Exception as e:
                print(f"Error removing temp directory: {e}")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
