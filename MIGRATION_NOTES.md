# Migration to Gemini CLI

## Summary

The Code Analysis Agent has been refactored to use `gemini-cli` instead of LangChain with OpenAI/Anthropic APIs.

## Changes Made

### 1. Core Agent (`agent.py`)
- **Removed**: LangChain dependencies (`ChatOpenAI`, `ChatAnthropic`, `HumanMessage`, `SystemMessage`)
- **Added**: Direct subprocess calls to `gemini-cli`
- **New Method**: `_call_gemini()` - handles all gemini-cli invocations
- **Updated Methods**: 
  - `_identify_key_files()` - now uses gemini-cli
  - `_analyze_features()` - now uses gemini-cli
- **Removed Method**: `_initialize_llm()` - no longer needed

### 2. Configuration (`config.py`)
- **Removed Settings**:
  - `openai_api_key`
  - `anthropic_api_key`
  - `llm_provider`
  - `model_name`
- **Remaining Settings**:
  - `host`
  - `port`
  - `max_upload_size`
  - `temp_dir`

### 3. Dependencies
- **Removed from `requirements.txt` and `pyproject.toml`**:
  - `langchain`
  - `langchain-openai`
  - `langchain-anthropic`
- **Added to `pyproject.toml`**:
  - `pydantic-settings` (was missing)
  - `jinja2` (was missing)

### 4. API Changes (`main.py`)
- Updated startup message to show "Gemini CLI" instead of LLM provider
- Updated health check endpoint to return `ai_provider: "gemini-cli"`

### 5. Documentation (`README.md`)
- Updated overview to mention Gemini CLI
- Added prerequisite: gemini-cli installation
- Updated setup instructions
- Removed API key configuration steps
- Updated troubleshooting section with gemini-cli specific issues

## Prerequisites

Before running the application, ensure:

1. **gemini-cli is installed**: 
   ```bash
   gemini --version
   ```

2. **gemini-cli is authenticated** (if required by your setup)

3. **Python dependencies are updated**:
   ```bash
   pip install -r requirements.txt
   # or
   poetry install
   ```

## Benefits

✅ **Simpler Configuration**: No API keys to manage in the application
✅ **Reduced Dependencies**: Removed heavy LangChain packages
✅ **Direct Integration**: Uses system-installed gemini-cli
✅ **Better Error Handling**: Clear error messages for CLI-specific issues

## Breaking Changes

⚠️ **Environment Variables**: The following `.env` variables are no longer used:
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `LLM_PROVIDER`
- `MODEL_NAME`

⚠️ **Dependencies**: You must have `gemini-cli` installed on your system

## Testing

To verify the setup works:

1. Test gemini-cli directly:
   ```bash
   gemini -p "Hello, how are you?" --output-format json
   ```

2. Start the application:
   ```bash
   python main.py
   ```

3. Check the health endpoint:
   ```bash
   curl http://localhost:8000/health
   ```

   Expected response:
   ```json
   {
     "status": "healthy",
     "ai_provider": "gemini-cli",
     "port": 8000
   }
   ```

## Rollback

If you need to rollback to the LangChain version, checkout the previous commit before this migration.

