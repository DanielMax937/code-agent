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
    Uses file redirection to avoid output truncation issues.
    
    Args:
        prompt: The prompt to send to Gemini
        cwd: Current working directory to execute gemini from (optional)
        
    Returns:
        JSON response as string (extracted from gemini-cli wrapper)
        
    Raises:
        CodeModificationError: If the call fails
    """
    import tempfile
    
    # Get model from environment variable or use default
    gemini_model = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
    
    try:
        # Create temporary file for output (avoids truncation)
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Run gemini-cli with output redirected to file
            # This avoids terminal rendering truncation issues
            cmd = f'gemini -m {gemini_model} -p {json.dumps(prompt)} --output-format json > {tmp_path}'
            
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                timeout=1200,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise CodeModificationError(f"Gemini CLI error: {result.stderr}")
            
            # Read the complete output from file
            with open(tmp_path, 'r') as f:
                output = f.read()
            
            # Parse the gemini-cli JSON wrapper
            gemini_output = json.loads(output.strip())
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
            
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        
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
    Modify code files based on natural language instructions using a two-step AI process.
    
    This agent uses a two-step approach:
    1. Ask AI to identify which files need changes
    2. For each file, ask AI to generate the new content
    3. Write all modified files to disk
    
    This approach provides better accuracy and handles larger codebases more effectively.
    
    Args:
        prompt: Natural language description of changes to make
        file_paths: List of files to analyze (can be relative or absolute)
        base_directory: Base directory for resolving relative paths
        create_backup: Whether to create backups before modifying
        dry_run: If True, don't actually modify files (just show what would change)
        
    Returns:
        Dictionary with modification results:
        {
            "success": bool,
            "files_modified": int,
            "changed_files": List[str],  # List of files that were changed
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
            "changed_files": [],
            "changes": []
        }
    
    if not file_paths:
        return {
            "success": False,
            "error": "No files specified",
            "files_modified": 0,
            "changed_files": [],
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
            "changed_files": [],
            "changes": []
        }
    
    # STEP 1: Ask Gemini to identify which files need to be changed
    identify_prompt = f"""You are an expert software engineer. Analyze the requirements and identify which files need to be changed.

REQUIREMENTS:
{prompt}

CURRENT CODE FILES:
{file_context}

YOUR TASK:
Analyze the requirements and determine which files need to be modified to implement them.

Return ONLY a JSON object with the list of files that need changes:
{{
  "changed_files": ["relative/path/file1.py", "relative/path/file2.js"]
}}

RULES:
- Return ONLY valid JSON, no explanations
- List only files that actually need modification
- Use relative paths as shown in the code files above
"""
    
    # Call Gemini to identify files
    try:
        response_text = _call_gemini(identify_prompt, cwd=base_directory)
        
        # Parse JSON response
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        
        if start == -1 or end <= start:
            return {
                "success": False,
                "error": "Invalid JSON response from AI (identify step)",
                "files_modified": 0,
                "changed_files": [],
                "changes": []
            }
        
        json_str = response_text[start:end]
        
        try:
            identification = json.loads(json_str)
        except json.JSONDecodeError as e:
            try:
                identification = json.loads(json_str, strict=False)
            except:
                return {
                    "success": False,
                    "error": f"Failed to parse file identification: {str(e)}",
                    "files_modified": 0,
                    "changed_files": [],
                    "changes": []
                }
        
        changed_files_list = identification.get('changed_files', [])
        
        if not changed_files_list:
            return {
                "success": True,
                "message": "No changes needed",
                "files_modified": 0,
                "changed_files": [],
                "changes": []
            }
        
        print(f"Files to modify: {', '.join(changed_files_list)}")
        
        # STEP 2: For each file, generate the new content
        files_to_modify = []
        
        for file_path in changed_files_list:
            # Get absolute path for reading
            if not os.path.isabs(file_path):
                abs_file_path = os.path.join(base_directory, file_path)
            else:
                abs_file_path = file_path
            
            # Read current file content
            current_content = read_file_content(abs_file_path)
            
            # Ask Gemini to generate new content for this specific file
            generate_prompt = f"""You are an expert software engineer. Generate the modified content for a specific file.

REQUIREMENTS:
{prompt}

FILE TO MODIFY: {file_path}

CURRENT CONTENT:
```
{current_content}
```

YOUR TASK:
Implement the required changes for this file and return the COMPLETE updated file content.

Return ONLY a JSON object:
{{
  "new_content": "complete updated file content here"
}}

CRITICAL RULES:
- Return ONLY valid JSON (no markdown, no explanations)
- Provide COMPLETE file content (not diffs or snippets)
- Preserve code style, formatting, and indentation
- Ensure code is syntactically correct
- Properly escape JSON: \\n for newlines, \\t for tabs, \\\\ for backslashes, \\" for quotes
"""
            
            print(f"Generating new content for: {file_path}")
            file_response = _call_gemini(generate_prompt, cwd=base_directory)
            
            # Parse the file content response
            start = file_response.find('{')
            end = file_response.rfind('}') + 1
            
            if start != -1 and end > start:
                json_str = file_response[start:end]
                try:
                    file_data = json.loads(json_str)
                    files_to_modify.append({
                        'path': file_path,
                        'new_content': file_data.get('new_content', '')
                    })
                except json.JSONDecodeError as e:
                    try:
                        file_data = json.loads(json_str, strict=False)
                        files_to_modify.append({
                            'path': file_path,
                            'new_content': file_data.get('new_content', '')
                        })
                    except:
                        print(f"Warning: Failed to parse content for {file_path}: {e}")
                        continue
        
        if not files_to_modify:
            return {
                "success": False,
                "error": "Failed to generate content for any files",
                "files_modified": 0,
                "changed_files": changed_files_list,
                "changes": []
            }
        
    except CodeModificationError as e:
        return {
            "success": False,
            "error": str(e),
            "files_modified": 0,
            "changed_files": [],
            "changes": []
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "files_modified": 0,
            "changed_files": [],
            "changes": []
        }
    
    # STEP 3: Apply modifications to disk
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
        "changed_files": changed_files_list if changed_files_list else [c["file"] for c in changes if c.get("status") in ["modified", "created"]],
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

