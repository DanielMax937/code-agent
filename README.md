# Code Analysis Agent

An AI-powered code analysis and automated implementation service built with FastAPI, Gemini CLI, and LangGraph. Analyzes codebases, generates code changes, and implements features with automated testing.

## Overview

This service provides two powerful capabilities:

1. **Code Analysis**: Analyzes a codebase and identifies where features should be implemented
2. **Automated Implementation** ⭐ **NEW**: Automatically implements features with a complete workflow:
   - Generate code changes from natural language
   - Apply changes safely
   - Generate unit tests
   - Run tests with intelligent retry logic (up to 3 attempts)

## Features

### Core Analysis
- RESTful API built with FastAPI
- Intelligent code analysis using Gemini CLI
- Structured JSON output with feature locations
- Automatic project structure analysis
- Execution plan generation
- No API key management needed (uses local gemini-cli)

### Automated Implementation Workflow ⭐ NEW
- **LangGraph-orchestrated** 5-agent workflow
- **Intelligent retry logic** - auto-fixes failed tests
- **End-to-end automation** - from description to tested code
- **Feature-by-feature processing** with detailed tracking
- **Comprehensive logging** and error handling

## Installation

### Prerequisites

- Python 3.9 or higher
- pip or poetry
- **gemini-cli** installed and configured (required)

### Setup

1. Install gemini-cli if you haven't already:
```bash
# Follow instructions at: https://github.com/google/generative-ai-cli
# Or use your preferred installation method
```

2. Clone the repository:
```bash
git clone <repository-url>
cd code-agent
```

3. Install dependencies:

Using pip:
```bash
pip install -r requirements.txt
```

Or using poetry:
```bash
poetry install
```

4. (Optional) Configure environment variables:
```bash
cp .env.example .env
```

You can configure server settings in `.env`:
```env
HOST=0.0.0.0
PORT=8000
MAX_UPLOAD_SIZE=52428800
TEMP_DIR=./temp
```

## Usage

### Starting the Server

Run the FastAPI server:

```bash
python main.py
```

Or using uvicorn directly:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### API Endpoints

The service provides three main endpoints:

#### 1. `/api/analyze` - Code Analysis Only
Analyzes a codebase and returns feature locations without implementation.

#### 2. `/api/analyze-and-implement` - One-Step Automation
Analyzes codebase AND automatically implements all features with the workflow.

#### 3. `/api/run-and-test` ⭐ **NEW** - Two-Step Workflow
Runs the workflow on an existing analysis result. Perfect for:
- Reviewing analysis before implementation
- Implementing features selectively
- Reusing analysis across multiple runs

### Making Requests

#### 1. Analyze Only

```bash
curl -X POST "http://localhost:8000/api/analyze" \
  -F "problem_description=Implement user authentication with login and registration features" \
  -F "code_zip=@/path/to/your/code.zip"
```

#### Using Python

```python
import requests

url = "http://localhost:8000/api/analyze"

with open("code.zip", "rb") as f:
    files = {"code_zip": f}
    data = {"problem_description": "Implement user authentication with login and registration"}
    response = requests.post(url, files=files, data=data)

print(response.json())
```

#### Using JavaScript/fetch

```javascript
const formData = new FormData();
formData.append('problem_description', 'Implement user authentication');
formData.append('code_zip', fileInput.files[0]);

const response = await fetch('http://localhost:8000/api/analyze', {
  method: 'POST',
  body: formData
});

const result = await response.json();
console.log(result);
```

#### 2. Two-Step Workflow (Analyze + Run Workflow)

**Step 1: Analyze**
```bash
curl -X POST "http://localhost:8000/api/analyze" \
  -F "problem_description=Implement user authentication" \
  -F "code_zip=@./project.zip" \
  > analysis.json
```

**Step 2: Run workflow with analysis**
```bash
curl -X POST "http://localhost:8000/api/run-and-test" \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "analysis_report": $(cat analysis.json),
  "base_directory": "./my-project",
  "max_retries": 3
}
EOF
```

**Python Example:**
```python
import requests

# Step 1: Analyze
with open('project.zip', 'rb') as f:
    analyze_response = requests.post(
        'http://localhost:8000/api/analyze',
        data={'problem_description': 'Implement authentication'},
        files={'code_zip': f}
    )

analysis = analyze_response.json()

# Review analysis before implementing
print(f"Features found: {len(analysis['feature_analysis'])}")

# Step 2: Run workflow for each feature
workflow_response = requests.post(
    'http://localhost:8000/api/run-and-test',
    json={
        'analysis_report': analysis,
        'base_directory': './my-project',
        'max_retries': 3
    }
)

result = workflow_response.json()
print(f"Success: {result['summary']['successful']}/{result['summary']['total_features']}")
```

#### 3. One-Step Workflow (All-in-One)

```bash
curl -X POST "http://localhost:8000/api/analyze-and-implement" \
  -F "problem_description=Implement user authentication" \
  -F "code_zip=@./project.zip" \
  -F "max_retries=3"
```

**Python Example:**
```python
import requests

with open('project.zip', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/analyze-and-implement',
        data={
            'problem_description': 'Implement authentication',
            'max_retries': 3
        },
        files={'code_zip': f}
    )

result = response.json()
print(f"Analysis: {len(result['analysis']['feature_analysis'])} features")
print(f"Implementation: {result['summary']['successful']} successful")
```

### Workflow Comparison

| Feature | `/api/analyze` | `/api/run-and-test` | `/api/analyze-and-implement` |
|---------|----------------|---------------------|------------------------------|
| Analyzes code | ✅ | ❌ (requires analysis) | ✅ |
| Implements features | ❌ | ✅ | ✅ |
| Review before implementing | ✅ | ✅ | ❌ |
| Selective implementation | N/A | ✅ | ❌ |
| Reuse analysis | ✅ | ✅ | ❌ |
| Number of API calls | 1 | 2 (analyze + run) | 1 |
| Best for | Code review | Controlled implementation | Full automation |

### Response Format

The API returns a JSON response with the following structure:

```json
{
  "feature_analysis": [
    {
      "feature_description": "Implement the 'create channel' feature",
      "implementation_location": [
        {
          "file": "src/modules/channel/channel.resolver.ts",
          "function": "createChannel",
          "lines": "13-16"
        },
        {
          "file": "src/modules/channel/channel.service.ts",
          "function": "create",
          "lines": "21-24"
        }
      ]
    }
  ],
  "execution_plan_suggestion": "To run this project, execute `npm install` and then `npm run start:dev`"
}
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `MAX_UPLOAD_SIZE` | Maximum upload size in bytes | `52428800` (50MB) |
| `TEMP_DIR` | Temporary directory for file processing | `./temp` |

**Note:** The application uses `gemini-cli` which should be configured separately. No API keys are needed in the application configuration.

## Project Structure

```
code-agent/
├── main.py              # FastAPI application
├── agent.py             # Code analysis agent logic
├── config.py            # Configuration management
├── models.py            # Pydantic models
├── utils.py             # Utility functions
├── requirements.txt     # Python dependencies
├── templates/           # HTML templates
│   └── index.html       # Web UI
├── tools/               # Code modification tools
│   ├── apply_code_change.py  # Git diff parser and applier
│   ├── demo.py          # Interactive demo
│   ├── test_apply_code_change.py  # Tests
│   └── README.md        # Tools documentation
├── .env.example         # Example environment configuration
└── README.md            # This file
```

## Tools

### Code Modification & Testing Agents

The `tools/` directory contains five powerful AI agents that automate the complete development workflow:

#### 1. Generate Diff Agent
Generates git diffs from natural language prompts using AI.

**Quick Example:**
```python
from tools import generate_diff_for_files

result = generate_diff_for_files(
    prompt="Add input validation to the login function",
    file_paths=["auth.py"]
)
```

#### 2. Apply Code Change Agent
Parses and applies git diff files to update code safely.

**Quick Example:**
```python
from tools import apply_diff_from_file

result = apply_diff_from_file("changes.diff", base_directory="./project")
```

#### 3. Generate Test Commands Agent
Analyzes code and generates commands to run unit tests.

**Quick Example:**
```python
from tools import generate_test_commands

result = generate_test_commands(directory="./project")
if result['success']:
    print(f"Framework: {result['test_framework']}")
    for cmd in result['commands']:
        print(cmd['command'])
```

#### 4. Generate Unittest Agent
Generates actual unit test code using AI based on source files.

**Quick Example:**
```python
from tools import generate_unittest

result = generate_unittest(
    source_file="calculator.py",
    test_description="Test all functions with edge cases"
)
if result['success']:
    print(f"Test code:\n{result['test_code']}")
    print(f"Run: {result['run_command']}")
```

#### 5. Run Unittest Agent ⭐ NEW
Executes unit tests and returns structured results with detailed output.

**Quick Example:**
```python
from tools import run_tests

result = run_tests(directory="./project", with_coverage=True)
if result['success']:
    print(f"✅ {result['summary']['passed']}/{result['summary']['total']} tests passed")
    print(f"Coverage: {result['summary']['coverage']}%")
else:
    print(f"❌ {result['summary']['failed']} tests failed")
```

#### Complete Workflow: Generate → Apply → Test → Execute → Verify

```python
from tools import (
    generate_diff_for_files,
    apply_git_diff,
    generate_unittest,
    generate_test_commands,
    run_tests
)

# Step 1: Generate diff from natural language
gen_result = generate_diff_for_files(
    prompt="Add error handling to file operations",
    file_paths=["service.py"]
)

# Step 2: Apply the changes
if gen_result['success']:
    apply_result = apply_git_diff(gen_result['diff'], base_directory=".")
    print(f"✅ Modified {apply_result['successful_files']} files")
    
    # Step 3: Generate unit tests for the changes
    test_gen = generate_unittest(
        source_file="service.py",
        test_description="Test error handling with edge cases"
    )
    if test_gen['success']:
        print(f"✅ Tests generated: {test_gen['test_file_name']}")
    
    # Step 4: Get commands to run tests
    test_cmd = generate_test_commands(directory=".")
    if test_cmd['success']:
        print(f"🧪 Run: {test_cmd['commands'][0]['command']}")
    
    # Step 5: Execute the tests and get results
    test_result = run_tests(directory=".", with_coverage=True)
    if test_result['success']:
        print(f"✅ All {test_result['summary']['passed']} tests passed!")
        print(f"📊 Coverage: {test_result['summary']['coverage']}%")
    else:
        print(f"❌ {test_result['summary']['failed']} tests failed")
        for failure in test_result['results']['failures']:
            print(f"  • {failure['test']}")
```

**Features:**
- 🤖 AI-powered diff generation (natural language → git diff)
- ✅ Parse and apply git diff files
- 🧪 Auto-generate test commands (detects framework & creates commands)
- 🧬 Generate complete unit test code (AI-powered test creation)
- ▶️ Execute tests and capture structured results
- 📝 Support for file creation, modification, and deletion
- 🔍 Dry run mode to preview changes
- 🛡️ Context verification for safe application
- 📊 Detailed statistics and error reporting
- 🎯 CI/CD ready (JSON output for pipelines)
- 🔄 TDD support (generate tests before implementation)
- 📈 Coverage tracking and detailed test reports

**Demo and Tests:**
```bash
# Test the apply agent
python tools/test_apply_code_change.py

# Demo all agents
python tools/demo.py                    # Apply code changes
python tools/demo_generate_diff.py      # Generate diffs
python tools/demo_test_commands.py      # Generate test commands
python tools/demo_unittest.py           # Generate unit tests
python tools/demo_run_tests.py          # Run tests and get results ⭐ NEW
python tools/workflow_example.py        # Complete workflows
```

See [tools/README.md](tools/README.md) and [tools/AGENTS_OVERVIEW.md](tools/AGENTS_OVERVIEW.md) for complete documentation.

---

## LangGraph Workflow - Automated Implementation

### Overview

The **LangGraph Workflow** orchestrates all 5 agents to provide complete end-to-end automation from feature analysis to tested implementation, with intelligent retry logic.

### Workflow Sequence

```
1. Generate Test Commands  →  Auto-detect test framework
2. Generate Diff          →  Create code changes from description
3. Apply Code Change      →  Safely apply changes to files
4. Generate Unit Tests    →  Create comprehensive tests
5. Run Tests             →  Execute tests and verify
   ↓
   Tests Failed? → Retry (up to 3 times) → Regenerate with error context
   ↓
   Tests Passed? → Success!
```

### Quick Start

#### Using the API Endpoint

```bash
curl -X POST "http://localhost:8000/api/analyze-and-implement" \
  -F "problem_description=Implement user authentication with JWT tokens" \
  -F "code_zip=@./my-project.zip" \
  -F "max_retries=3"
```

#### Using Python

```python
import requests

with open('my-project.zip', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/analyze-and-implement',
        data={
            'problem_description': 'Add user authentication',
            'max_retries': 3
        },
        files={'code_zip': f}
    )

result = response.json()
print(f"Features: {result['summary']['successful']}/{result['summary']['total_features']}")
```

#### Direct Workflow Usage

```python
from workflow import run_feature_workflow

result = run_feature_workflow(
    feature_description="Add email validation to registration",
    feature_files=["auth.py", "validators.py"],
    base_directory="./project",
    max_retries=3
)

if result['success']:
    print(f"✅ Feature implemented!")
    print(f"Tests: {result['test_results']['summary']['passed']} passed")
    if result['retry_count'] > 0:
        print(f"Succeeded after {result['retry_count']} retries")
```

### Key Features

#### 🔄 Intelligent Retry Logic
- Automatically retries failed tests up to 3 times (configurable)
- Extracts error context from failures
- Regenerates code with fixes based on test errors
- Tracks retry attempts and provides detailed logs

#### 📊 Comprehensive Results

```python
{
    "success": True,
    "message": "Feature implemented successfully! 15/15 tests passed.",
    "retry_count": 1,
    "test_results": {
        "summary": {
            "total": 15,
            "passed": 15,
            "failed": 0,
            "coverage": 95
        }
    },
    "logs": [
        "Step 1: Generating test commands...",
        "✅ Test framework detected: pytest",
        "Step 2: Generating code diff...",
        "✅ Generated diff for 2 files",
        "Step 3: Applying code changes...",
        "✅ Modified 2 files successfully",
        "Step 4: Generating unit tests...",
        "✅ Generated 2 test files",
        "Step 5: Running unit tests...",
        "❌ 2 tests failed",
        "🔄 Retry 1/3: Regenerating with error context...",
        "✅ All 15 tests passed!",
        "📊 Coverage: 95%"
    ]
}
```

#### 🎯 Multi-Feature Processing

```python
from workflow import run_analysis_workflow

# Process all features from analysis report
results = run_analysis_workflow(
    analysis_report=analysis,  # From CodeAnalysisAgent
    base_directory="./project",
    max_retries=3
)

# Summary
successful = sum(1 for r in results if r['success'])
print(f"Implemented: {successful}/{len(results)} features")
```

### Response Format

#### Success Response
```json
{
  "analysis": {
    "feature_analysis": [...],
    "project_structure": {...}
  },
  "workflow_results": [
    {
      "feature_name": "User Authentication",
      "success": true,
      "retry_count": 1,
      "test_results": {
        "summary": {
          "total": 15,
          "passed": 15,
          "coverage": 95
        }
      }
    }
  ],
  "summary": {
    "total_features": 2,
    "successful": 2,
    "failed": 0,
    "total_retries": 1
  }
}
```

### Configuration

- **max_retries**: Maximum retry attempts per feature (default: 3)
- **base_directory**: Project directory path
- **feature_files**: List of files to modify

### Documentation

- **[WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md)** - Complete workflow documentation
- **[workflow.py](workflow.py)** - Implementation
- **[workflow_example.py](workflow_example.py)** - Usage examples

---

## Development

### Running Tests

```bash
pytest

# Or run specific tool tests
python tools/test_apply_code_change.py
```

### Code Formatting

```bash
black .
```

### Linting

```bash
pylint *.py
```

## Supported Languages

The agent can analyze codebases in multiple programming languages:
- Python (.py)
- JavaScript/TypeScript (.js, .ts, .jsx, .tsx)
- Java (.java)
- C/C++ (.c, .cpp, .h)
- Go (.go)
- Rust (.rs)
- Ruby (.rb)
- PHP (.php)
- Swift (.swift)
- Kotlin (.kt)
- C# (.cs)
- Scala (.scala)
- SQL (.sql)
- GraphQL (.graphql)
- Vue (.vue)
- Svelte (.svelte)

## Limitations

- Maximum upload size: 50MB (configurable)
- The agent analyzes up to 30 key files to manage token usage
- Large files are truncated to 500 lines for analysis

## Troubleshooting

### "gemini-cli not found"
Make sure `gemini-cli` is installed and available in your system PATH. You can verify by running:
```bash
gemini --version
```

### "Gemini CLI request timed out"
The analysis is taking longer than expected (>2 minutes). This can happen with very large codebases. Try:
- Reducing the size of your codebase
- Removing unnecessary files before zipping
- Checking your internet connection (gemini-cli needs network access)

### "File size exceeds maximum"
The uploaded zip file is larger than the configured `MAX_UPLOAD_SIZE`. Either reduce the size of your codebase or increase the limit in `.env`.

### Poor analysis results
- Ensure your problem description is clear and specific
- Check that the uploaded codebase is complete
- Make sure your gemini-cli is properly configured and authenticated

## License

MIT

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.
