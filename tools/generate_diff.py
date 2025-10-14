"""
Generate git diffs using AI based on prompts and code context.

This module provides functionality to generate git diff files from natural
language descriptions of desired code changes.

Note: The _call_gemini function follows the same pattern as agent.py
for consistency in how we interact with gemini-cli.
"""
import os
import json
import subprocess
from typing import List, Dict, Optional, Tuple
from pathlib import Path


class DiffGenerationError(Exception):
    """Exception raised when diff generation fails."""
    pass


def read_file_content(file_path: str, max_lines: Optional[int] = None) -> str:
    """
    Read file content with optional line limit.
    
    Args:
        file_path: Path to the file
        max_lines: Maximum number of lines to read
        
    Returns:
        File content as string
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            if max_lines:
                lines = [f.readline() for _ in range(max_lines)]
                return ''.join(lines)
            return f.read()
    except Exception as e:
        return f"# Error reading file: {str(e)}"


def get_relevant_files(
    directory: str,
    file_patterns: Optional[List[str]] = None,
    max_files: int = 10
) -> List[str]:
    """
    Get relevant files from a directory.
    
    Args:
        directory: Root directory to search
        file_patterns: List of file patterns to include (e.g., ['*.py', '*.js'])
        max_files: Maximum number of files to return
        
    Returns:
        List of file paths
    """
    if not os.path.exists(directory):
        raise DiffGenerationError(f"Directory not found: {directory}")
    
    # Default file extensions
    extensions = (
        '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h',
        '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.cs', '.vue'
    )
    
    files = []
    for root, _, filenames in os.walk(directory):
        # Skip common non-source directories
        if any(skip in root for skip in ['node_modules', 'venv', '__pycache__', '.git', 'dist', 'build']):
            continue
        
        for filename in filenames:
            if filename.endswith(extensions):
                files.append(os.path.join(root, filename))
    
    # Prioritize certain file types
    priority_patterns = ['controller', 'service', 'handler', 'route', 'api', 'model']
    
    def file_priority(filepath: str) -> int:
        filename = os.path.basename(filepath).lower()
        for i, pattern in enumerate(priority_patterns):
            if pattern in filename:
                return i
        return len(priority_patterns)
    
    files = sorted(files, key=file_priority)[:max_files]
    return files


def build_file_context(
    file_paths: List[str],
    base_directory: str,
    max_lines_per_file: int = 500
) -> str:
    """
    Build context string from multiple files.
    
    Args:
        file_paths: List of file paths to include (can be relative or absolute)
        base_directory: Base directory for resolving relative paths
        max_lines_per_file: Maximum lines to include per file
        
    Returns:
        Formatted context string with file contents
    """
    context_parts = []
    
    for file_path in file_paths:
        # Convert to absolute path if it's relative
        if not os.path.isabs(file_path):
            abs_path = os.path.join(base_directory, file_path)
        else:
            abs_path = file_path
        
        # Get relative path for display in context
        try:
            rel_path = os.path.relpath(abs_path, base_directory)
        except ValueError:
            # If relpath fails (e.g., different drives on Windows), use basename
            rel_path = os.path.basename(abs_path)
        
        # Read content using absolute path
        content = read_file_content(abs_path, max_lines=max_lines_per_file)
        
        context_parts.append(f"=== File: {rel_path} ===")
        context_parts.append(content)
        context_parts.append("")  # Empty line separator
    
    return "\n".join(context_parts)


def _call_gemini(prompt: str, cwd: Optional[str] = None) -> str:
    """
    Call gemini-cli with a prompt and return the response.
    
    This follows the same pattern as agent.py for consistency.
    
    Args:
        prompt: The prompt to send to Gemini
        cwd: Current working directory to execute gemini from (optional)
        
    Returns:
        Response text (extracted from gemini-cli JSON wrapper)
        
    Raises:
        DiffGenerationError: If the call fails
    """
    try:
        result = subprocess.run(
            ['gemini','-m', 'gemini-2.5-flash', '-p', prompt, '--output-format', 'json'],
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
            cwd=cwd
        )
        
        if result.returncode != 0:
            raise DiffGenerationError(f"Gemini CLI error: {result.stderr}")
        
        # Parse the gemini-cli JSON wrapper
        gemini_output = json.loads(result.stdout.strip())
        response_text = gemini_output.get('response', '')
        
        print(f"Gemini CLI response received ({len(response_text)} chars)")
        
        # Remove markdown code blocks if present
        if '```diff' in response_text:
            # Extract diff from markdown code blocks
            start = response_text.find('```diff') + 7
            end = response_text.rfind('```')
            if start > 6 and end > start:
                response_text = response_text[start:end].strip()
        elif '```' in response_text:
            # Handle generic code blocks
            start = response_text.find('```') + 3
            end = response_text.rfind('```')
            if start > 2 and end > start:
                response_text = response_text[start:end].strip()
        return response_text
        
    except subprocess.TimeoutExpired:
        raise DiffGenerationError("Gemini CLI request timed out")
    except FileNotFoundError:
        raise DiffGenerationError("gemini-cli not found. Please ensure it's installed and in PATH")
    except json.JSONDecodeError as e:
        raise DiffGenerationError(f"Failed to parse Gemini CLI output: {str(e)}")
    except Exception as e:
        raise DiffGenerationError(f"Error calling Gemini CLI: {str(e)}")


def call_gemini_for_diff(
    prompt: str,
    file_context: str,
    cwd: Optional[str] = None
) -> str:
    """
    Call Gemini CLI to generate a diff.
    
    Args:
        prompt: User prompt describing desired changes
        file_context: Context of files to modify
        cwd: Current working directory (optional)
        
    Returns:
        Generated diff as string
        
    Raises:
        DiffGenerationError: If generation fails
    """
    system_prompt = """You are an expert software engineer. Generate a git diff (unified diff format) 
based on the user's request and the provided code context.

IMPORTANT RULES:
1. Generate ONLY valid unified diff format
2. Start with "diff --git a/path b/path"
3. Include proper headers (---, +++, @@)
4. Use proper diff syntax (+, -, space for context)
5. Ensure context lines match the actual code
6. Make minimal, focused changes
7. DO NOT include explanations or markdown - ONLY the diff
8. If creating a new file, use "new file mode 100644"
9. If deleting a file, use "deleted file mode 100644"

Example format:
diff --git a/path/to/file.py b/path/to/file.py
index abc123..def456 100644
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -1,3 +1,4 @@
 existing line
 another existing line
+new line added
 more existing lines

Now generate the diff based on the user's request.
"""
    
    full_prompt = f"""{system_prompt}

USER REQUEST:
{prompt}

CODE CONTEXT:
{file_context}

Generate the git diff to implement the requested changes:
"""
    
    # Call gemini using the same pattern as agent.py
    response_text = _call_gemini(full_prompt, cwd=cwd)
    
    # Extract diff from response
    diff_text = extract_diff_from_response(response_text)
    
    return diff_text


def extract_diff_from_response(response: str) -> str:
    """
    Extract diff content from AI response, removing markdown formatting.
    
    This function handles various response formats from the AI.
    
    Args:
        response: AI response text
        
    Returns:
        Clean diff text
    """
    original_length = len(response)
    
    # Remove markdown code blocks if present
    if '```diff' in response:
        start = response.find('```diff') + 7
        end = response.rfind('```')
        if start > 6 and end > start:
            extracted = response[start:end].strip()
            print(f"Extracted diff from ```diff block ({original_length} -> {len(extracted)} chars)")
            return extracted
    elif '```' in response:
        start = response.find('```') + 3
        end = response.rfind('```')
        if start > 2 and end > start:
            extracted = response[start:end].strip()
            print(f"Extracted diff from ``` block ({original_length} -> {len(extracted)} chars)")
            return extracted
    
    # If no markdown, look for diff start
    if 'diff --git' in response:
        start = response.find('diff --git')
        extracted = response[start:].strip()
        print(f"Extracted diff from plain text ({original_length} -> {len(extracted)} chars)")
        return extracted
    
    print(f"Using response as-is ({original_length} chars)")
    return response.strip()


def generate_diff(
    prompt: str,
    file_paths: Optional[List[str]] = None,
    directory: Optional[str] = None,
    base_directory: str = ".",
    max_files: int = 10,
    max_lines_per_file: int = 500
) -> Dict[str, any]:
    """
    Generate a git diff based on a prompt and code context.
    
    Args:
        prompt: Natural language description of desired changes
        file_paths: Specific files to include in context (optional)
        directory: Directory to scan for files (optional, used if file_paths not provided)
        base_directory: Base directory for relative paths
        max_files: Maximum files to include in context
        max_lines_per_file: Maximum lines per file
        
    Returns:
        Dictionary with diff and metadata
        
    Raises:
        DiffGenerationError: If generation fails
    """
    if not prompt or not prompt.strip():
        return {
            "success": False,
            "error": "Prompt cannot be empty",
            "diff": None
        }
    
    # Determine which files to include
    if file_paths:
        # Use provided file paths
        files_to_process = file_paths
    elif directory:
        # Scan directory for relevant files
        files_to_process = get_relevant_files(directory, max_files=max_files)
    else:
        return {
            "success": False,
            "error": "Either file_paths or directory must be provided",
            "diff": None
        }
    
    if not files_to_process:
        return {
            "success": False,
            "error": "No files found to process",
            "diff": None
        }
    
    # Build context from files
    try:
        file_context = build_file_context(
            files_to_process,
            base_directory,
            max_lines_per_file
        )
    except Exception as e:
        return {
            "success": False,
            "error": f"Error building file context: {str(e)}",
            "diff": None
        }
    
    # Generate diff using AI
    try:
        diff_content = call_gemini_for_diff(
            prompt=prompt,
            file_context=file_context,
            cwd=base_directory
        )
        
        if not diff_content or 'diff --git' not in diff_content:
            return {
                "success": False,
                "error": "Generated content is not a valid diff",
                "diff": None
            }
        
        return {
            "success": True,
            "diff": diff_content,
            "files_analyzed": len(files_to_process),
            "prompt": prompt,
            "message": "Diff generated successfully"
        }
        
    except DiffGenerationError as e:
        return {
            "success": False,
            "error": str(e),
            "diff": None
        }


def generate_diff_for_files(
    prompt: str,
    file_paths: List[str],
    base_directory: str = "."
) -> Dict[str, any]:
    """
    Generate diff for specific files.
    
    Args:
        prompt: Description of changes to make
        file_paths: List of file paths to modify
        base_directory: Base directory for relative paths
        
    Returns:
        Dictionary with diff and metadata
    """
    return generate_diff(
        prompt=prompt,
        file_paths=file_paths,
        base_directory=base_directory
    )


def generate_diff_for_directory(
    prompt: str,
    directory: str,
    base_directory: str = ".",
    max_files: int = 10
) -> Dict[str, any]:
    """
    Generate diff by scanning a directory.
    
    Args:
        prompt: Description of changes to make
        directory: Directory to scan for files
        base_directory: Base directory for relative paths
        max_files: Maximum files to analyze
        
    Returns:
        Dictionary with diff and metadata
    """
    return generate_diff(
        prompt=prompt,
        directory=directory,
        base_directory=base_directory,
        max_files=max_files
    )


def save_diff_to_file(diff_content: str, output_path: str) -> bool:
    """
    Save diff content to a file.
    
    Args:
        diff_content: Diff content to save
        output_path: Path to save the diff file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(diff_content)
        return True
    except Exception as e:
        print(f"Error saving diff to file: {e}")
        return False


def generate_and_save_diff(
    prompt: str,
    output_file: str,
    file_paths: Optional[List[str]] = None,
    directory: Optional[str] = None,
    base_directory: str = "."
) -> Dict[str, any]:
    """
    Generate a diff and save it to a file.
    
    Args:
        prompt: Description of changes to make
        output_file: Path to save the generated diff
        file_paths: Specific files to include (optional)
        directory: Directory to scan (optional)
        base_directory: Base directory for relative paths
        
    Returns:
        Dictionary with results and metadata
    """
    result = generate_diff(
        prompt=prompt,
        file_paths=file_paths,
        directory=directory,
        base_directory=base_directory
    )
    
    if result['success']:
        if save_diff_to_file(result['diff'], output_file):
            result['output_file'] = output_file
            result['message'] = f"Diff generated and saved to {output_file}"
        else:
            result['success'] = False
            result['error'] = f"Failed to save diff to {output_file}"
    
    return result

