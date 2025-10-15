"""
Direct code modification agent using AI.

This module combines diff generation and application into a single step.
Instead of generating a diff and then applying it, this agent directly
modifies files based on natural language instructions and returns the
changes as structured JSON.
"""
import os
import json
import subprocess
import shutil
from typing import List, Dict, Optional, Any
from pathlib import Path


class CodeModificationError(Exception):
    """Exception raised when code modification fails."""
    pass


def _call_gemini(prompt: str, cwd: Optional[str] = None) -> str:
    """
    Call gemini-cli with a prompt and return the JSON response.
    
    This follows the same pattern as agent.py for consistency.
    
    Args:
        prompt: The prompt to send to Gemini
        cwd: Current working directory to execute gemini from (optional)
        
    Returns:
        JSON response as string (extracted from gemini-cli wrapper)
        
    Raises:
        CodeModificationError: If the call fails
    """
    try:
        result = subprocess.run(
            ['gemini', '-m', 'gemini-2.5-flash', '-p', prompt, '--output-format', 'json'],
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
            cwd=cwd
        )
        
        if result.returncode != 0:
            raise CodeModificationError(f"Gemini CLI error: {result.stderr}")
        
        # Parse the gemini-cli JSON wrapper
        gemini_output = json.loads(result.stdout.strip())
        response_text = gemini_output.get('response', '')
        
        print(f"Gemini CLI response received ({len(response_text)} chars)")
        
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
        
        return response_text
        
    except subprocess.TimeoutExpired:
        raise CodeModificationError("Gemini CLI request timed out")
    except FileNotFoundError:
        raise CodeModificationError("gemini-cli not found. Please ensure it's installed and in PATH")
    except json.JSONDecodeError as e:
        raise CodeModificationError(f"Failed to parse Gemini CLI output: {str(e)}")
    except Exception as e:
        raise CodeModificationError(f"Error calling Gemini CLI: {str(e)}")


def read_file_content(file_path: str) -> str:
    """
    Read file content safely.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File content as string
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        return f"# Error reading file: {str(e)}"


def write_file_content(file_path: str, content: str) -> bool:
    """
    Write content to a file safely.
    
    Args:
        file_path: Path to the file
        content: Content to write
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path) or '.', exist_ok=True)
        
        # Write content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True
    except Exception as e:
        print(f"Error writing file {file_path}: {e}")
        return False


def backup_file(file_path: str) -> Optional[str]:
    """
    Create a backup of a file.
    
    Args:
        file_path: Path to the file to backup
        
    Returns:
        Path to backup file, or None if backup failed
    """
    try:
        if os.path.exists(file_path):
            backup_path = f"{file_path}.backup"
            shutil.copy2(file_path, backup_path)
            return backup_path
        return None
    except Exception as e:
        print(f"Error creating backup for {file_path}: {e}")
        return None


def build_file_context(
    file_paths: List[str],
    base_directory: str,
    max_lines_per_file: int = 1000
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
        
        # Get relative path for display
        try:
            rel_path = os.path.relpath(abs_path, base_directory)
        except ValueError:
            rel_path = os.path.basename(abs_path)
        
        # Read content
        content = read_file_content(abs_path)
        
        # Truncate if too long
        lines = content.split('\n')
        if len(lines) > max_lines_per_file:
            content = '\n'.join(lines[:max_lines_per_file])
            content += f"\n... (truncated, {len(lines) - max_lines_per_file} more lines)"
        
        context_parts.append(f"=== File: {rel_path} ===")
        context_parts.append(content)
        context_parts.append("")  # Empty line separator
    
    return "\n".join(context_parts)


def modify_code(
    prompt: str,
    file_paths: List[str],
    base_directory: str = ".",
    create_backup: bool = True,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Modify code files based on natural language instructions.
    
    This agent directly modifies files instead of generating diffs.
    It uses AI to understand the changes needed and applies them directly.
    
    Args:
        prompt: Natural language description of changes to make
        file_paths: List of files to modify (can be relative or absolute)
        base_directory: Base directory for resolving relative paths
        create_backup: Whether to create backups before modifying
        dry_run: If True, don't actually modify files (just show what would change)
        
    Returns:
        Dictionary with modification results:
        {
            "success": bool,
            "files_modified": int,
            "changes": [
                {
                    "file": str,
                    "status": "modified|created|unchanged|error",
                    "new_content": str,
                    "backup_path": str (optional),
                    "error": str (optional)
                }
            ],
            "error": str (optional)
        }
        Note: Actual changes are best captured via git diff
    """
    if not prompt or not prompt.strip():
        return {
            "success": False,
            "error": "Prompt cannot be empty",
            "files_modified": 0,
            "changes": []
        }
    
    if not file_paths:
        return {
            "success": False,
            "error": "No files specified",
            "files_modified": 0,
            "changes": []
        }
    
    # Build context from files
    try:
        file_context = build_file_context(file_paths, base_directory)
    except Exception as e:
        return {
            "success": False,
            "error": f"Error building file context: {str(e)}",
            "files_modified": 0,
            "changes": []
        }
    
    # Build prompt for AI
    ai_prompt = f"""You are an expert software engineer. Modify the provided code files based on the user's instructions.

USER INSTRUCTIONS:
{prompt}

CURRENT CODE:
{file_context}

TASK:
For each file that needs changes, provide the COMPLETE new file content.

Return a JSON object with this structure:
{{
  "files": [
    {{
      "path": "relative/path/to/file",
      "new_content": "complete new file content here"
    }}
  ]
}}

IMPORTANT:
- Return ONLY valid JSON, no additional text or markdown
- Include COMPLETE file content, not just changes
- Preserve formatting, indentation, and code style
- Make minimal, focused changes that address the instructions
- Ensure code is syntactically correct
- Omit files that don't need changes
- CRITICAL: Ensure the JSON is properly formatted:
  * Escape newlines in code as \\n
  * Escape tabs as \\t
  * Escape backslashes as \\\\
  * Escape double quotes as \\"
  * The "new_content" field must be a valid JSON string

Generate the modifications:
"""
    
    # Call Gemini
    try:
        response_text = _call_gemini(ai_prompt, cwd=base_directory)
        
        # Parse JSON response
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        
        if start == -1 or end <= start:
            return {
                "success": False,
                "error": "Invalid JSON response from AI",
                "files_modified": 0,
                "changes": []
            }
        
        json_str = response_text[start:end]
        
        # Try to parse JSON with better error handling
        try:
            modifications = json.loads(json_str)
        except json.JSONDecodeError as e:
            # Log the problematic JSON for debugging
            print(f"JSON Parse Error: {e}")
            print(f"Problematic JSON (first 500 chars): {json_str[:500]}")
            
            # Try to fix common issues with escape sequences
            # This is a workaround for AI responses with improperly escaped strings
            try:
                # Attempt to use strict=False to be more lenient
                modifications = json.loads(json_str, strict=False)
            except:
                return {
                    "success": False,
                    "error": f"Failed to parse AI response: {str(e)}. Response preview: {json_str[:200]}",
                    "files_modified": 0,
                    "changes": [],
                    "raw_response": json_str[:500]
                }
        
        files_to_modify = modifications.get('files', [])
        
        if not files_to_modify:
            return {
                "success": True,
                "message": "No changes needed",
                "files_modified": 0,
                "changes": []
            }
        
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Failed to parse AI response: {str(e)}",
            "files_modified": 0,
            "changes": [],
            "raw_response": response_text[:500] if 'response_text' in locals() else "N/A"
        }
    except CodeModificationError as e:
        return {
            "success": False,
            "error": str(e),
            "files_modified": 0,
            "changes": []
        }
    
    # Apply modifications
    changes = []
    files_modified = 0
    
    for file_mod in files_to_modify:
        file_path = file_mod.get('path', '')
        new_content = file_mod.get('new_content', '')
        
        # Convert to absolute path
        if not os.path.isabs(file_path):
            abs_path = os.path.join(base_directory, file_path)
        else:
            abs_path = file_path
        
        # Get relative path for reporting
        try:
            rel_path = os.path.relpath(abs_path, base_directory)
        except ValueError:
            rel_path = file_path
        
        change_info = {
            "file": rel_path,
            "new_content": new_content
        }
        
        # Check if file exists (for status)
        file_exists = os.path.exists(abs_path)
        
        # Skip if content unchanged
        if file_exists:
            old_content = read_file_content(abs_path)
            if old_content == new_content:
                change_info["status"] = "unchanged"
                changes.append(change_info)
                continue
        
        # Dry run - don't actually modify
        if dry_run:
            change_info["status"] = "would_modify"
            changes.append(change_info)
            files_modified += 1
            continue
        
        # Create backup if requested
        if create_backup and file_exists:
            backup_path = backup_file(abs_path)
            if backup_path:
                change_info["backup_path"] = backup_path
        
        # Write new content
        if write_file_content(abs_path, new_content):
            change_info["status"] = "modified" if file_exists else "created"
            files_modified += 1
        else:
            change_info["status"] = "error"
            change_info["error"] = "Failed to write file"
        
        changes.append(change_info)
    
    return {
        "success": files_modified > 0,
        "files_modified": files_modified,
        "changes": changes,
        "message": f"Modified {files_modified} file(s)"
    }


def modify_code_with_retry(
    prompt: str,
    file_paths: List[str],
    base_directory: str = ".",
    max_retries: int = 2
) -> Dict[str, Any]:
    """
    Modify code with automatic retry on failure.
    
    Args:
        prompt: Natural language description of changes
        file_paths: List of files to modify
        base_directory: Base directory
        max_retries: Maximum retry attempts
        
    Returns:
        Modification results dictionary
    """
    for attempt in range(max_retries + 1):
        result = modify_code(
            prompt=prompt,
            file_paths=file_paths,
            base_directory=base_directory
        )
        
        if result['success']:
            return result
        
        if attempt < max_retries:
            print(f"Attempt {attempt + 1} failed, retrying...")
    
    return result

