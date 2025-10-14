# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI-based AI code analysis service that uses LangChain to analyze codebases and generate structured feature location reports. The service accepts a zip file containing source code and a natural language description of features, then identifies where those features are implemented in the codebase.

## Architecture

### Core Components

1. **main.py** - FastAPI application entry point
   - Handles multipart/form-data requests
   - Manages file uploads and temporary file cleanup
   - Exposes `/api/analyze` endpoint for code analysis

2. **agent.py** - Code analysis agent (core intelligence)
   - `CodeAnalysisAgent` class orchestrates the analysis workflow
   - Multi-stage analysis: project structure → key file identification → feature location → execution plan
   - Uses LangChain to interact with LLMs (OpenAI or Anthropic)
   - Intelligently prioritizes files based on naming patterns (controllers, services, resolvers, etc.)

3. **models.py** - Pydantic models for request/response validation
   - `AnalysisReport` - Top-level response model
   - `FeatureAnalysis` - Individual feature analysis
   - `ImplementationLocation` - Specific code location (file, function, lines)

4. **config.py** - Configuration management using Pydantic settings
   - Loads environment variables from `.env`
   - Supports multiple LLM providers (OpenAI, Anthropic)
   - Configurable upload limits and temp directories

5. **utils.py** - File handling and code extraction utilities
   - Zip extraction and validation
   - Recursive code file discovery with extension filtering
   - Project structure tree generation
   - Line-numbered file reading

### Analysis Workflow

The agent follows this workflow in `agent.py`:

1. **Extract Project Structure** - Generate a tree view of the project
2. **Identify Key Files** - Use LLM to select the 10-15 most relevant files based on problem description
3. **Analyze Features** - Send key file contents to LLM with structured prompt requesting JSON output
4. **Generate Execution Plan** - Detect package.json, requirements.txt, etc. and suggest run commands

### LLM Integration

- Supports OpenAI (GPT-4) and Anthropic (Claude) via LangChain
- Uses `temperature=0` for deterministic outputs
- Prompts are designed to extract JSON responses
- Falls back gracefully if JSON parsing fails

## Commands

### Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py

# Run with uvicorn (recommended for development)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Testing the API

```bash
# Health check
curl http://localhost:8000/health

# Analyze a codebase
curl -X POST "http://localhost:8000/api/analyze" \
  -F "problem_description=Your feature description here" \
  -F "code_zip=@/path/to/code.zip"
```

## Key Design Decisions

### File Prioritization
When there are too many files (>30), the agent prioritizes based on naming patterns (agent.py:_identify_key_files):
- Controllers, resolvers, handlers, routes
- Services, business logic
- API endpoints
- Models, schemas, repositories

This ensures the most relevant files are analyzed first.

### Token Management
- Files are truncated to 200 lines during analysis to manage token usage
- Maximum 15 key files are analyzed in detail
- Project structure limited to 3 levels deep

### Error Handling
- Temporary files are always cleaned up in finally blocks
- File size validation occurs during streaming upload
- Graceful fallbacks when JSON parsing fails

### LLM Provider Flexibility
The `_initialize_llm()` method in agent.py makes it easy to switch between providers. Configuration is centralized in config.py using Pydantic settings.

## Environment Configuration

Required environment variables (see .env.example):
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` - API credentials
- `LLM_PROVIDER` - Which provider to use ("anthropic" or "openai")
- `MODEL_NAME` - Specific model (e.g., "claude-3-5-sonnet-20241022")

## Extending the Agent

### Adding New LLM Providers

1. Add provider configuration to `config.py`
2. Add new case in `agent.py:_initialize_llm()`
3. Install the corresponding LangChain integration package

### Customizing Analysis

- Modify prompts in `agent.py:_analyze_features()` to change output format
- Adjust file prioritization logic in `agent.py:_identify_key_files()`
- Change line limits in `utils.py:extract_code_context()`

### Adding New Endpoints

Follow FastAPI conventions in `main.py`. The app uses dependency injection via `get_settings()` for configuration.
