"""
Generate unit test code based on prompts and code analysis.

This module generates actual unit test code using AI, following the
same pattern as agent.py for Gemini CLI interaction.
"""
import os
import json
import subprocess
from typing import List, Dict, Optional, Tuple
from pathlib import Path


class UnittestGenerationError(Exception):
    """Exception raised when unittest generation fails."""
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
        UnittestGenerationError: If the call fails
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
            print("call gemini ut command")
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                timeout=120,
                capture_output=True,
                text=True
            )

            print(f"result: {result}")
            
            if result.returncode != 0:
                raise UnittestGenerationError(f"Gemini CLI error: {result.stderr}")
            
            # Read the complete output from file
            with open(tmp_path, 'r') as f:
                output = f.read()
            
            # Parse the gemini-cli JSON wrapper
            gemini_output = json.loads(output.strip())
            response_text = gemini_output.get('response', '')
            
            print(f"Gemini CLI response: {response_text[:200]}...")
            
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
            
            print(f"Gemini CLI final response: {response_text[:200]}...")
            return response_text
            
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        
    except subprocess.TimeoutExpired:
        raise UnittestGenerationError("Gemini CLI request timed out")
    except FileNotFoundError:
        raise UnittestGenerationError("gemini-cli not found. Please ensure it's installed and in PATH")
    except json.JSONDecodeError as e:
        raise UnittestGenerationError(f"Failed to parse Gemini CLI output: {str(e)}")
    except Exception as e:
        raise UnittestGenerationError(f"Error calling Gemini CLI: {str(e)}")


def read_source_file(file_path: str, max_lines: int = 500) -> str:
    """
    Read source code file.
    
    Args:
        file_path: Path to the source file
        max_lines: Maximum number of lines to read
        
    Returns:
        File content as string
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [f.readline() for _ in range(max_lines)]
            content = ''.join(lines)
            
            if len(lines) == max_lines:
                content += f"\n# ... (file truncated at {max_lines} lines)"
            
            return content
    except Exception as e:
        return f"# Error reading file: {str(e)}"


def detect_test_framework(directory: str) -> str:
    """
    Detect the test framework being used.
    
    Args:
        directory: Project directory
        
    Returns:
        Test framework name
    """
    # Check for config files
    framework_indicators = {
        'pytest': ['pytest.ini', 'pyproject.toml', 'setup.cfg'],
        'jest': ['jest.config.js', 'jest.config.ts'],
        'junit': ['pom.xml', 'build.gradle'],
        'vitest': ['vitest.config.js', 'vitest.config.ts'],
        'mocha': ['.mocharc.json', '.mocharc.js'],
        'rspec': ['.rspec', 'spec/spec_helper.rb'],
        'phpunit': ['phpunit.xml', 'phpunit.xml.dist'],
        'go': ['go.mod']
    }
    
    for framework, indicators in framework_indicators.items():
        for indicator in indicators:
            if os.path.exists(os.path.join(directory, indicator)):
                return framework
    
    # Check for package.json to detect JS framework
    package_json = os.path.join(directory, 'package.json')
    if os.path.exists(package_json):
        try:
            with open(package_json, 'r') as f:
                data = json.load(f)
                dev_deps = data.get('devDependencies', {})
                if 'jest' in dev_deps:
                    return 'jest'
                elif 'vitest' in dev_deps:
                    return 'vitest'
                elif 'mocha' in dev_deps:
                    return 'mocha'
        except Exception:
            pass
    
    # Check for requirements.txt for Python
    req_file = os.path.join(directory, 'requirements.txt')
    if os.path.exists(req_file):
        try:
            with open(req_file, 'r') as f:
                content = f.read()
                if 'pytest' in content:
                    return 'pytest'
                elif 'unittest' in content or 'nose' in content:
                    return 'unittest'
        except Exception:
            pass
    
    # Default based on file types
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                return 'pytest'  # Default for Python
            elif file.endswith(('.js', '.ts')):
                return 'jest'  # Default for JavaScript/TypeScript
            elif file.endswith('.java'):
                return 'junit'
            elif file.endswith('.go'):
                return 'go'
    
    return 'unknown'


def generate_unittest(
    source_file: str,
    test_description: str,
    test_commands_result: Optional[Dict] = None,
    git_diff: Optional[str] = None,
    base_directory: Optional[str] = None
) -> Dict[str, any]:
    """
    Generate unit test code for a source file based on git diff changes.
    
    Args:
        source_file: Path to the source file to test
        test_description: Description of what to test
        test_commands_result: Result from generate_test_commands (framework info)
        git_diff: Git diff showing actual changes made
        base_directory: Base directory of the project
        
    Returns:
        Dictionary with generated test code and metadata
        
    Raises:
        UnittestGenerationError: If generation fails
    """
    if not os.path.exists(source_file):
        return {
            "success": False,
            "error": f"Source file not found: {source_file}",
            "test_code": None
        }
    
    # Get source code
    source_code = read_source_file(source_file)
    
    # Determine project directory
    if base_directory is None:
        base_directory = os.path.dirname(os.path.abspath(source_file))
    
    # Extract framework info from test_commands_result
    if test_commands_result and test_commands_result.get('success'):
        test_framework = test_commands_result.get('recommended_framework', 'pytest')
        test_commands = test_commands_result.get('commands', [])
        setup_commands = test_commands_result.get('setup_commands', [])
        framework_reason = test_commands_result.get('reason', '')
    else:
        # Fallback to auto-detection
        test_framework = detect_test_framework(base_directory)
        test_commands = []
        setup_commands = []
        framework_reason = ''
    
    # Auto-generate output file
    base_name = os.path.basename(source_file)
    name_without_ext = os.path.splitext(base_name)[0]
    
    if test_framework in ['pytest']:
        output_file = f"test_{base_name}"
    elif test_framework in ['jest', 'vitest', 'mocha', 'Jest with React Testing Library']:
        output_file = f"{name_without_ext}.test{os.path.splitext(base_name)[1]}"
    elif test_framework == 'junit':
        output_file = f"{name_without_ext}Test.java"
    elif test_framework == 'go':
        output_file = f"{name_without_ext}_test.go"
    else:
        output_file = f"test_{base_name}"
    
    # Build git diff context
    diff_context = ""
    if git_diff:
        diff_context = f"""

GIT DIFF - ACTUAL CHANGES MADE:
```diff
{git_diff}
```

The git diff above shows the exact changes made to the code. Generate tests specifically for these changes.
Focus on testing the new/modified functionality shown in the diff.
"""
    
    # Build prompt for Gemini
    prompt = f"""You are an expert test engineer. Generate comprehensive unit tests for the code changes.

TEST FRAMEWORK: {test_framework}
{f"Framework Choice: {framework_reason}" if framework_reason else ""}

SOURCE FILE: {os.path.basename(source_file)}
```
{source_code}
```
{diff_context}

TEST REQUIREMENTS:
{test_description}

TASK:
Generate complete, production-ready unit tests that:
1. Follow {test_framework} best practices and conventions
2. Test the specific changes shown in the git diff (if provided)
3. Include edge cases and error handling tests
4. Use appropriate assertions and test structure
5. Include setup/teardown if needed
6. Add helpful test descriptions/docstrings
7. Focus on NEW or MODIFIED functionality

Return your response as a JSON object with this structure:
{{
  "test_code": "complete test file content here",
  "test_file_name": "{output_file}"
}}

IMPORTANT:
- Generate complete, runnable test code
- Follow {test_framework} conventions exactly
- Include all necessary imports
- Make tests independent and isolated
- Use descriptive test names
- Return ONLY valid JSON, no additional text
- Focus tests on the changes shown in the git diff
"""
    
    # Call Gemini using same pattern as agent.py
    try:
        print(f"Calling Test Gemini with prompt: {prompt}")
        response_text = _call_gemini(prompt, cwd=base_directory)
        print(f"Gemini test response: {response_text}")
        # Parse JSON response
        try:
            # Extract JSON from response
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start != -1 and end > start:
                json_str = response_text[start:end]
                test_data = json.loads(json_str)
                
                # Extract run command from test_commands_result
                run_command = ""
                if test_commands and len(test_commands) > 0:
                    run_command = test_commands[0].get('command', '')
                
                return {
                    "success": True,
                    "test_code": test_data.get("test_code", ""),
                    "test_file_name": test_data.get("test_file_name", output_file),
                    "framework": test_framework,
                    "run_command": run_command,
                    "setup_commands": setup_commands,
                    "source_file": source_file,
                    "used_git_diff": bool(git_diff)
                }
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            print(f"Response: {response_text}")
            
            return {
                "success": False,
                "error": f"Failed to parse JSON response: {str(e)}",
                "raw_response": response_text[:500]
            }
    
    except UnittestGenerationError as e:
        return {
            "success": False,
            "error": str(e),
            "test_code": None
        }


def generate_unittest_for_directory(
    directory: str,
    test_description: str,
    file_pattern: Optional[str] = None,
    test_framework: Optional[str] = None
) -> Dict[str, any]:
    """
    Generate unit tests for all files in a directory.
    
    Args:
        directory: Directory containing source files
        test_description: Description of what to test
        file_pattern: Pattern to match files (e.g., '*.py')
        test_framework: Test framework to use
        
    Returns:
        Dictionary with generated tests for all files
    """
    if not os.path.exists(directory):
        return {
            "success": False,
            "error": f"Directory not found: {directory}",
            "tests": []
        }
    
    # Detect framework if not provided
    if test_framework is None:
        test_framework = detect_test_framework(directory)
    
    # Find source files
    source_files = []
    extensions = ('.py', '.js', '.ts', '.java', '.go') if file_pattern is None else [file_pattern]
    
    for root, _, files in os.walk(directory):
        # Skip test directories
        if any(skip in root for skip in ['test', '__pycache__', 'node_modules', 'dist', 'build']):
            continue
        
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                source_files.append(os.path.join(root, file))
    
    # Limit files
    max_files = 5
    if len(source_files) > max_files:
        source_files = source_files[:max_files]
    
    # Generate tests for each file
    results = []
    for source_file in source_files:
        result = generate_unittest(
            source_file=source_file,
            test_description=test_description,
            test_framework=test_framework
        )
        results.append(result)
    
    return {
        "success": True,
        "framework": test_framework,
        "files_processed": len(results),
        "tests": results
    }


def save_test_file(test_code: str, output_path: str) -> bool:
    """
    Save generated test code to a file.
    
    Args:
        test_code: Test code to save
        output_path: Path to save the test file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(test_code)
        return True
    except Exception as e:
        print(f"Error saving test file: {e}")
        return False


def generate_and_save_unittest(
    source_file: str,
    test_description: str,
    output_file: Optional[str] = None,
    test_commands_result: Optional[Dict] = None,
    git_diff: Optional[str] = None,
    base_directory: Optional[str] = None
) -> Dict[str, any]:
    """
    Generate unit test and save to file.
    
    Args:
        source_file: Source file to test
        test_description: What to test
        output_file: Where to save (auto-generated if None)
        test_commands_result: Result from generate_test_commands
        git_diff: Git diff showing changes
        base_directory: Base directory of the project
        
    Returns:
        Dictionary with results
    """
    result = generate_unittest(
        source_file=source_file,
        test_description=test_description,
        test_commands_result=test_commands_result,
        git_diff=git_diff,
        base_directory=base_directory
    )
    
    if result['success']:
        test_file = output_file or result['test_file_name']
        
        # Ensure test file is in the correct directory
        if base_directory and not os.path.isabs(test_file):
            test_file = os.path.join(base_directory, test_file)
        
        if save_test_file(result['test_code'], test_file):
            result['output_file'] = test_file
            result['message'] = f"Test file saved to {test_file}"
        else:
            result['success'] = False
            result['error'] = f"Failed to save test file to {test_file}"
    
    return result

