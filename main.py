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
from models import AnalysisReport, RunAndTestRequest
from agent import CodeAnalysisAgent
from utils import extract_zip
from workflow import run_analysis_workflow


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
            "analyze_and_implement": "/api/analyze-and-implement",
            "run_and_test": "/api/run-and-test",
            "health": "/health",
            "info": "/api/info"
        },
        "workflows": {
            "two_step": {
                "step1": "POST /api/analyze - Analyze codebase",
                "step2": "POST /api/run-and-test - Run workflow for each feature"
            },
            "one_step": {
                "all_in_one": "POST /api/analyze-and-implement - Analyze and implement in one call"
            }
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


@app.post("/api/analyze")
async def analyze_code(
    problem_description: str = Form(..., description="Natural language description of features"),
    code_zip: UploadFile = File(..., description="Zip file containing the source code")
):
    """
    Analyze a codebase and generate a feature location report.

    Args:
        problem_description: Natural language description of features to implement
        code_zip: Zip file containing the complete source code

    Returns:
        AnalysisReport with feature analysis, execution plan, and codebase_path
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

        # Convert to dict and add codebase path
        report_dict = report.model_dump()
        report_dict['codebase_path'] = temp_extract_dir
        
        return report_dict

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error analyzing code: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing code: {str(e)}"
        )
    finally:
        # Cleanup temporary ZIP file only (keep extracted directory for workflow)
        if temp_zip_path and os.path.exists(temp_zip_path):
            try:
                os.remove(temp_zip_path)
            except Exception as e:
                print(f"Error removing temp zip: {e}")


@app.post("/api/analyze-and-implement")
async def analyze_and_implement(
    problem_description: str = Form(..., description="Natural language description of features"),
    code_zip: UploadFile = File(..., description="Zip file containing the source code"),
    max_retries: int = Form(3, description="Maximum retries per feature on test failure")
):
    """
    Analyze codebase and automatically implement features with tests.

    This endpoint combines analysis with the complete workflow:
    1. Analyze codebase and identify features
    2. For each feature:
       - Generate test commands
       - Generate code diff
       - Apply changes
       - Generate unit tests
       - Run tests (with retry on failure)

    Args:
        problem_description: Natural language description of features
        code_zip: Zip file containing source code
        max_retries: Maximum retries per feature (default: 3)

    Returns:
        Analysis report + workflow results for each feature
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

        # Step 1: Analyze the codebase
        print(f"\n{'='*80}")
        print("STEP 1: ANALYZING CODEBASE")
        print(f"{'='*80}\n")

        agent = CodeAnalysisAgent(settings)
        analysis_report = agent.analyze_codebase(
            problem_description=problem_description,
            code_directory=temp_extract_dir
        )

        # Step 2: Run workflow for each feature
        print(f"\n{'='*80}")
        print("STEP 2: IMPLEMENTING FEATURES WITH AUTOMATED WORKFLOW")
        print(f"{'='*80}\n")

        workflow_results = run_analysis_workflow(
            analysis_report=analysis_report.model_dump(),
            base_directory=temp_extract_dir,
            max_retries=max_retries
        )

        # Combine results
        return {
            "analysis": analysis_report.model_dump(),
            "workflow_results": workflow_results,
            "summary": {
                "total_features": len(workflow_results),
                "successful": sum(1 for r in workflow_results if r["success"]),
                "failed": sum(1 for r in workflow_results if not r["success"]),
                "total_retries": sum(r.get("retry_count", 0) for r in workflow_results)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in analyze-and-implement: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error: {str(e)}"
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


@app.post("/api/run-and-test")
async def run_and_test(request: RunAndTestRequest):
    """
    Run workflow for features from an existing analysis report.
    
    This endpoint accepts an analysis report (from /api/analyze) and runs
    the complete workflow for each feature:
    1. Generate test commands
    2. Generate code diff
    3. Apply changes
    4. Generate unit tests
    5. Run tests (with retry on failure)
    
    Args:
        request: RunAndTestRequest containing:
            - analysis_report: Analysis report from /api/analyze
            - base_directory: Base directory of the codebase
            - max_retries: Maximum retries per feature (default: 3)
        
    Returns:
        Workflow results for each feature with summary statistics
    """
    try:
        # Validate base directory exists
        if not os.path.exists(request.base_directory):
            raise HTTPException(
                status_code=400,
                detail=f"Base directory not found: {request.base_directory}"
            )
        
        print(f"\n{'='*80}")
        print("RUN AND TEST WORKFLOW")
        print(f"{'='*80}")
        print(f"Base directory: {request.base_directory}")
        print(f"Max retries: {request.max_retries}")
        print(f"Features to process: {len(request.analysis_report.get('feature_analysis', []))}")
        print(f"{'='*80}\n")
        
        # Run workflow for each feature in the analysis
        workflow_results = run_analysis_workflow(
            analysis_report=request.analysis_report,
            base_directory=request.base_directory,
            max_retries=request.max_retries
        )
        
        # Calculate summary statistics
        summary = {
            "total_features": len(workflow_results),
            "successful": sum(1 for r in workflow_results if r["success"]),
            "failed": sum(1 for r in workflow_results if not r["success"]),
            "total_retries": sum(r.get("retry_count", 0) for r in workflow_results),
            "features_with_retries": sum(1 for r in workflow_results if r.get("retry_count", 0) > 0)
        }
        
        return {
            "workflow_results": workflow_results,
            "summary": summary,
            "base_directory": request.base_directory,
            "max_retries": request.max_retries
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in run-and-test: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error running workflow: {str(e)}"
        )


@app.post("/api/cleanup")
async def cleanup_codebase(codebase_path: str = Form(...)):
    """
    Cleanup temporary codebase directory.
    
    Args:
        codebase_path: Path to the temporary codebase directory to cleanup
        
    Returns:
        Success message
    """
    try:
        if not codebase_path or not os.path.exists(codebase_path):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid or non-existent path: {codebase_path}"
            )
        
        # Security check: only allow cleanup of temp directories
        if not codebase_path.startswith(settings.temp_dir):
            raise HTTPException(
                status_code=403,
                detail="Can only cleanup temporary directories"
            )
        
        # Remove the directory
        shutil.rmtree(codebase_path)
        
        return {
            "success": True,
            "message": f"Cleaned up codebase at {codebase_path}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error cleaning up codebase: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error cleaning up: {str(e)}"
        )


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
