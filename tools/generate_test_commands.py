"""
Recommend testing frameworks and generate test execution commands.

This module analyzes codebases, recommends the best testing framework to use
based on the project's language and structure, and generates appropriate 
commands to run unit tests. Uses Gemini CLI following the same pattern as agent.py.
"""
import os
import json
import subprocess
from typing import List, Dict, Optional, Tuple
from pathlib import Path


class TestCommandGenerationError(Exception):
    """Exception raised when test command generation fails."""
    pass


def _call_gemini(prompt: str, cwd: Optional[str] = None) -> str:
    """
    Call gemini-cli with a prompt and return the JSON response.
    
    This follows the same pattern as agent.py for consistency.
    Uses file redirection to avoid output truncation issues.
    
    Args:
        prompt: The prompt to send to Gemini
        cwd: Current working directory to execute gemini from (optional)
        
    Returns:
        JSON response as string (extracted from gemini-cli wrapper)
        
    Raises:
        TestCommandGenerationError: If the call fails
    """
    import tempfile
    
    try:
        # Create temporary file for output (avoids truncation)
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Run gemini-cli with output redirected to file
            # This avoids terminal rendering truncation issues
            cmd = f'gemini -m gemini-2.5-flash -p {json.dumps(prompt)} --output-format json > {tmp_path}'
            
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                timeout=120,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise TestCommandGenerationError(f"Gemini CLI error: {result.stderr}")
            
            # Read the complete output from file
            with open(tmp_path, 'r') as f:
                output = f.read()
            
            # Parse the gemini-cli JSON wrapper
            gemini_output = json.loads(output.strip())
            response_text = gemini_output.get('response', '')
            
            # Remove markdown code blocks if present
            if '```json' in response_text:
                # Extract JSON from markdown code blocks
                start = response_text.find('```json') + 7
                end = response_text.rfind('```')
                if start > 6 and end > start:
                    response_text = response_text[start:end].strip()
            elif '```' in response_text:
                # Handle generic code blocks
                start = response_text.find('```') + 3
                end = response_text.rfind('```')
                if start > 2 and end > start:
                    response_text = response_text[start:end].strip()
            
            print(f"Gemini CLI final response for test commands: {response_text[:200]}...")
            return response_text
            
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        
    except subprocess.TimeoutExpired:
        raise TestCommandGenerationError("Gemini CLI request timed out")
    except FileNotFoundError:
        raise TestCommandGenerationError("gemini-cli not found. Please ensure it's installed and in PATH")
    except json.JSONDecodeError as e:
        raise TestCommandGenerationError(f"Failed to parse Gemini CLI output: {str(e)}")
    except Exception as e:
        raise TestCommandGenerationError(f"Error calling Gemini CLI: {str(e)}")


def detect_test_files(directory: str) -> List[str]:
    """
    Detect test files in a directory.
    
    Args:
        directory: Root directory to search
        
    Returns:
        List of test file paths
    """
    test_patterns = [
        'test_*.py', '*_test.py', 'test*.py',  # Python
        '*.test.js', '*.test.ts', '*.spec.js', '*.spec.ts',  # JavaScript/TypeScript
        '*Test.java', '*Tests.java',  # Java
        '*_test.go', '*_test.rb',  # Go, Ruby
        'test_*.php', '*Test.php'  # PHP
    ]
    
    test_files = []
    for root, _, files in os.walk(directory):
        # Skip common non-test directories
        if any(skip in root for skip in ['node_modules', 'venv', '__pycache__', '.git', 'dist', 'build', 'vendor']):
            continue
        
        for file in files:
            # Check if file matches test patterns
            file_lower = file.lower()
            if (file_lower.startswith('test') or 
                'test' in file_lower or 
                file_lower.endswith(('.test.js', '.test.ts', '.spec.js', '.spec.ts', '_test.py', '_test.go'))):
                test_files.append(os.path.join(root, file))
    
    return test_files


def detect_config_files(directory: str) -> Dict[str, str]:
    """
    Detect test configuration files.
    
    Args:
        directory: Root directory to search
        
    Returns:
        Dictionary of config file type to path
    """
    config_files = {
        # Python
        'pytest.ini': 'pytest.ini',
        'setup.cfg': 'setup.cfg',
        'tox.ini': 'tox.ini',
        'pyproject.toml': 'pyproject.toml',
        # JavaScript/TypeScript
        'jest.config.js': 'jest.config.js',
        'jest.config.ts': 'jest.config.ts',
        'vitest.config.js': 'vitest.config.js',
        'karma.conf.js': 'karma.conf.js',
        # Java
        'pom.xml': 'pom.xml',
        'build.gradle': 'build.gradle',
        # Ruby
        'Rakefile': 'Rakefile',
        # Go
        'go.mod': 'go.mod',
        # PHP
        'phpunit.xml': 'phpunit.xml'
    }
    
    found_configs = {}
    for config_name, config_path in config_files.items():
        full_path = os.path.join(directory, config_path)
        if os.path.exists(full_path):
            found_configs[config_name] = full_path
    
    return found_configs


def read_file_sample(file_path: str, max_lines: int = 50) -> str:
    """
    Read a sample of a file.
    
    Args:
        file_path: Path to the file
        max_lines: Maximum number of lines to read
        
    Returns:
        File content sample
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [f.readline() for _ in range(max_lines)]
            return ''.join(lines)
    except Exception as e:
        return f"# Error reading file: {str(e)}"


def build_test_context(
    test_files: List[str],
    config_files: Dict[str, str],
    base_directory: str,
    max_files: int = 10
) -> str:
    """
    Build context string from test files and configs.
    
    Args:
        test_files: List of test file paths
        config_files: Dictionary of config files
        base_directory: Base directory for relative paths
        max_files: Maximum test files to include
        
    Returns:
        Formatted context string
    """
    context_parts = []
    
    # Add config files
    if config_files:
        context_parts.append("=== Configuration Files ===")
        for config_name, config_path in config_files.items():
            rel_path = os.path.relpath(config_path, base_directory)
            context_parts.append(f"\nConfig: {rel_path}")
            content = read_file_sample(config_path, max_lines=30)
            context_parts.append(content)
    
    # Add test files
    if test_files:
        context_parts.append("\n=== Test Files ===")
        for test_file in test_files[:max_files]:
            rel_path = os.path.relpath(test_file, base_directory)
            context_parts.append(f"\nTest File: {rel_path}")
            content = read_file_sample(test_file, max_lines=20)
            context_parts.append(content)
    
    # Add project structure info
    context_parts.append("\n=== Project Files ===")
    try:
        # Get package.json, requirements.txt, etc.
        common_files = ['package.json', 'requirements.txt', 'Gemfile', 'go.mod', 'composer.json']
        for filename in common_files:
            filepath = os.path.join(base_directory, filename)
            if os.path.exists(filepath):
                context_parts.append(f"\nFound: {filename}")
                content = read_file_sample(filepath, max_lines=15)
                context_parts.append(content)
    except Exception:
        pass
    
    return "\n".join(context_parts)


def generate_test_commands(
    directory: str,
    specific_test_file: Optional[str] = None,
    test_pattern: Optional[str] = None
) -> Dict[str, any]:
    """
    Recommend testing framework and generate commands to run unit tests.
    
    Analyzes the project structure and recommends the best testing framework
    to use based on the language, dependencies, and best practices.
    
    Args:
        directory: Root directory of the project
        specific_test_file: Specific test file to run (optional)
        test_pattern: Pattern to match test files (optional)
        
    Returns:
        Dictionary with recommended framework, reasoning, test commands, and metadata
        
    Raises:
        TestCommandGenerationError: If generation fails
    """
    if not os.path.exists(directory):
        return {
            "success": False,
            "error": f"Directory not found: {directory}",
            "commands": None
        }
    
    # Detect test files
    test_files = detect_test_files(directory)
    
    # Detect config files
    config_files = detect_config_files(directory)
    
    if not test_files and not config_files:
        return {
            "success": False,
            "error": "No test files or test configuration found",
            "commands": None
        }
    
    # Build context
    context = build_test_context(test_files, config_files, directory)
    
    # Build prompt
    prompt = f"""You are a test automation expert. Analyze the following project and recommend which testing framework should be used.

PROJECT CONTEXT:
{context}

TASK:
Based on the project's language, existing dependencies, and structure, recommend the BEST testing framework to use for this project. Consider:
1. Programming language (Python, JavaScript/TypeScript, Java, Go, etc.)
2. Existing project dependencies and package managers
3. Project type (web app, API, library, etc.)
4. Industry best practices and modern standards
5. Existing test files (if any) to understand current patterns

If no testing framework is currently set up, recommend the most appropriate one for this tech stack.
If a framework already exists, validate if it's the best choice or recommend a better alternative.

Return a JSON object with this EXACT structure:
{{
  "recommended_framework": "name of the recommended testing framework (e.g., pytest, jest, vitest, junit, go test)",
  "reason": "why this framework is recommended for this project",
  "alternative_frameworks": ["alternative option 1", "alternative option 2"],
  "commands": [
    {{
      "command": "full command to run tests",
      "description": "what this command does",
      "scope": "all|unit|integration|specific"
    }}
  ],
  "setup_commands": [
    {{
      "command": "setup command to install the framework",
      "description": "what this setup does"
    }}
  ],
  "environment_variables": [
    {{
      "name": "ENV_VAR_NAME",
      "value": "suggested value",
      "description": "what this variable controls"
    }}
  ],
  "notes": "Additional setup notes or best practices"
}}

IMPORTANT:
- Recommend the BEST framework for this specific project
- Provide clear reasoning for the recommendation
- Include complete setup commands to install and configure the framework
- Include commands for running all tests
- Include commands for running specific test files
- Include commands for running tests with coverage
- Be specific about actual commands that would work
- Consider modern best practices (e.g., vitest over jest for Vite projects, pytest over unittest for Python)

Return ONLY valid JSON, no additional text.
"""
    
    # Add specific test file or pattern to prompt if provided
    if specific_test_file:
        prompt += f"\n\nNote: Generate commands specifically for running test file: {specific_test_file}"
    elif test_pattern:
        prompt += f"\n\nNote: Generate commands for tests matching pattern: {test_pattern}"
    
    # Call Gemini using same pattern as agent.py
    try:
        response_text = _call_gemini(prompt, cwd=directory)
        
        # Parse JSON response
        try:
            # Extract JSON from response
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start != -1 and end > start:
                json_str = response_text[start:end]
                commands_data = json.loads(json_str)
                
                return {
                    "success": True,
                    "recommended_framework": commands_data.get("recommended_framework", "unknown"),
                    "reason": commands_data.get("reason", ""),
                    "alternative_frameworks": commands_data.get("alternative_frameworks", []),
                    "commands": commands_data.get("commands", []),
                    "setup_commands": commands_data.get("setup_commands", []),
                    "environment_variables": commands_data.get("environment_variables", []),
                    "notes": commands_data.get("notes", ""),
                    "test_files_found": len(test_files),
                    "config_files_found": list(config_files.keys())
                }
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            print(f"Response: {response_text}")
            
            return {
                "success": False,
                "error": f"Failed to parse JSON response: {str(e)}",
                "raw_response": response_text[:500]
            }
    
    except TestCommandGenerationError as e:
        return {
            "success": False,
            "error": str(e),
            "commands": None
        }


def generate_test_commands_for_file(
    test_file: str,
    project_directory: Optional[str] = None
) -> Dict[str, any]:
    """
    Recommend testing framework and generate commands to run a specific test file.
    
    Args:
        test_file: Path to the test file
        project_directory: Project root directory (optional, defaults to file's directory)
        
    Returns:
        Dictionary with recommended framework and test commands
    """
    if not os.path.exists(test_file):
        return {
            "success": False,
            "error": f"Test file not found: {test_file}",
            "commands": None
        }
    
    # Determine project directory
    if project_directory is None:
        project_directory = os.path.dirname(test_file)
    
    return generate_test_commands(
        directory=project_directory,
        specific_test_file=test_file
    )


def save_commands_to_file(commands_data: Dict, output_path: str) -> bool:
    """
    Save test commands to a JSON file.
    
    Args:
        commands_data: Commands data dictionary
        output_path: Path to save the JSON file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(commands_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving commands to file: {e}")
        return False


def generate_and_save_commands(
    directory: str,
    output_file: str,
    specific_test_file: Optional[str] = None
) -> Dict[str, any]:
    """
    Recommend testing framework, generate test commands, and save to a file.
    
    Args:
        directory: Project root directory
        output_file: Path to save the JSON file
        specific_test_file: Specific test file (optional)
        
    Returns:
        Dictionary with recommended framework, commands, and metadata
    """
    result = generate_test_commands(
        directory=directory,
        specific_test_file=specific_test_file
    )
    
    if result['success']:
        if save_commands_to_file(result, output_file):
            result['output_file'] = output_file
            result['message'] = f"Test commands saved to {output_file}"
        else:
            result['success'] = False
            result['error'] = f"Failed to save commands to {output_file}"
    
    return result

