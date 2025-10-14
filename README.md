# Code Analysis Agent

An AI-powered code analysis service built with FastAPI and Gemini CLI that analyzes codebases and generates structured feature location reports.

## Overview

This service accepts a codebase (as a zip file) and a natural language description of features, then uses Google's Gemini AI via CLI to identify where those features are implemented in the code.

## Features

- RESTful API built with FastAPI
- Intelligent code analysis using Gemini CLI
- Structured JSON output with feature locations
- Automatic project structure analysis
- Execution plan generation
- No API key management needed (uses local gemini-cli)

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

### Making Requests

#### Using cURL

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
├── .env.example         # Example environment configuration
└── README.md            # This file
```

## Development

### Running Tests

```bash
pytest
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
