"""
Apply code changes from git diff files.

This module provides functionality to parse git diff files and apply
the changes to the actual source files.
"""
import os
import re
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass


@dataclass
class DiffHunk:
    """Represents a single hunk in a diff."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[str]


@dataclass
class FileDiff:
    """Represents changes to a single file."""
    old_path: Optional[str]
    new_path: str
    is_new_file: bool
    is_deleted_file: bool
    hunks: List[DiffHunk]


class DiffParseError(Exception):
    """Exception raised when diff parsing fails."""
    pass


class DiffApplyError(Exception):
    """Exception raised when applying diff fails."""
    pass


def parse_git_diff(diff_content: str) -> List[FileDiff]:
    """
    Parse a git diff string into structured FileDiff objects.
    
    Args:
        diff_content: String content of a git diff file
        
    Returns:
        List of FileDiff objects representing changes
        
    Raises:
        DiffParseError: If the diff format is invalid
    """
    if not diff_content.strip():
        raise DiffParseError("Empty diff content")
    
    file_diffs = []
    current_file = None
    current_hunk = None
    
    lines = diff_content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # New file diff starts
        if line.startswith('diff --git'):
            if current_file and current_hunk:
                current_file.hunks.append(current_hunk)
            if current_file:
                file_diffs.append(current_file)
            
            # Extract file paths from "diff --git a/path b/path"
            match = re.match(r'diff --git a/(.*?) b/(.*?)$', line)
            if not match:
                raise DiffParseError(f"Invalid diff header: {line}")
            
            old_path = match.group(1)
            new_path = match.group(2)
            
            current_file = FileDiff(
                old_path=old_path,
                new_path=new_path,
                is_new_file=False,
                is_deleted_file=False,
                hunks=[]
            )
            current_hunk = None
            
        # New file marker
        elif line.startswith('new file mode'):
            if current_file:
                current_file.is_new_file = True
                
        # Deleted file marker
        elif line.startswith('deleted file mode'):
            if current_file:
                current_file.is_deleted_file = True
                
        # Hunk header: @@ -old_start,old_count +new_start,new_count @@
        elif line.startswith('@@'):
            if current_hunk and current_file:
                current_file.hunks.append(current_hunk)
            
            match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if not match:
                raise DiffParseError(f"Invalid hunk header: {line}")
            
            old_start = int(match.group(1))
            old_count = int(match.group(2)) if match.group(2) else 1
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) else 1
            
            current_hunk = DiffHunk(
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
                lines=[]
            )
            
        # Hunk content lines
        elif current_hunk is not None:
            # Lines starting with +, -, or space (context)
            if line.startswith(('+', '-', ' ')):
                current_hunk.lines.append(line)
            elif line.startswith('\\'):
                # "\ No newline at end of file" - ignore
                pass
            
        i += 1
    
    # Add the last hunk and file
    if current_file and current_hunk:
        current_file.hunks.append(current_hunk)
    if current_file:
        file_diffs.append(current_file)
    
    return file_diffs


def apply_hunk_to_lines(
    original_lines: List[str],
    hunk: DiffHunk
) -> List[str]:
    """
    Apply a single diff hunk to file lines.
    
    Args:
        original_lines: Original file content as list of lines
        hunk: DiffHunk to apply
        
    Returns:
        Modified file content as list of lines
        
    Raises:
        DiffApplyError: If the hunk cannot be applied
    """
    # Convert 1-based line numbers to 0-based indices
    old_start_idx = hunk.old_start - 1
    
    # Extract the lines to replace
    result_lines = original_lines[:old_start_idx].copy()
    
    # Process the hunk lines
    old_line_idx = old_start_idx
    
    for hunk_line in hunk.lines:
        if hunk_line.startswith(' '):
            # Context line - verify it matches
            expected_line = hunk_line[1:]  # Remove leading space
            if old_line_idx < len(original_lines):
                actual_line = original_lines[old_line_idx].rstrip('\n')
                if actual_line != expected_line.rstrip('\n'):
                    raise DiffApplyError(
                        f"Context line mismatch at line {old_line_idx + 1}. "
                        f"Expected: '{expected_line}', Got: '{actual_line}'"
                    )
                result_lines.append(original_lines[old_line_idx])
                old_line_idx += 1
            else:
                raise DiffApplyError(
                    f"Hunk extends beyond file length at line {old_line_idx + 1}"
                )
                
        elif hunk_line.startswith('-'):
            # Deletion - verify and skip
            expected_line = hunk_line[1:]  # Remove leading minus
            if old_line_idx < len(original_lines):
                actual_line = original_lines[old_line_idx].rstrip('\n')
                if actual_line != expected_line.rstrip('\n'):
                    raise DiffApplyError(
                        f"Deletion line mismatch at line {old_line_idx + 1}. "
                        f"Expected: '{expected_line}', Got: '{actual_line}'"
                    )
                old_line_idx += 1  # Skip this line (delete it)
            else:
                raise DiffApplyError(
                    f"Cannot delete line {old_line_idx + 1}: beyond file length"
                )
                
        elif hunk_line.startswith('+'):
            # Addition - insert new line
            new_line = hunk_line[1:]  # Remove leading plus
            # Preserve newline if it exists in the hunk line
            if new_line or hunk_line == '+\n':
                result_lines.append(new_line + '\n')
    
    # Add remaining lines after the hunk
    result_lines.extend(original_lines[old_line_idx:])
    
    return result_lines


def apply_file_diff(
    file_diff: FileDiff,
    base_directory: str = "."
) -> Dict[str, any]:
    """
    Apply changes from a FileDiff to the actual file.
    
    Args:
        file_diff: FileDiff object containing changes
        base_directory: Base directory for file paths
        
    Returns:
        Dictionary with status information
        
    Raises:
        DiffApplyError: If changes cannot be applied
    """
    file_path = os.path.join(base_directory, file_diff.new_path)
    
    # Handle file deletion
    if file_diff.is_deleted_file:
        if os.path.exists(file_path):
            os.remove(file_path)
            return {
                "status": "deleted",
                "file": file_diff.new_path,
                "message": f"Deleted file: {file_diff.new_path}"
            }
        else:
            return {
                "status": "skipped",
                "file": file_diff.new_path,
                "message": f"File not found (already deleted?): {file_diff.new_path}"
            }
    
    # Handle new file creation
    if file_diff.is_new_file:
        # Create parent directories if needed
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Reconstruct file content from additions
        new_lines = []
        for hunk in file_diff.hunks:
            for line in hunk.lines:
                if line.startswith('+'):
                    new_lines.append(line[1:] + '\n')
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        return {
            "status": "created",
            "file": file_diff.new_path,
            "message": f"Created new file: {file_diff.new_path}",
            "lines_added": len(new_lines)
        }
    
    # Handle file modification
    if not os.path.exists(file_path):
        raise DiffApplyError(f"File not found: {file_path}")
    
    # Read original file
    with open(file_path, 'r', encoding='utf-8') as f:
        original_lines = f.readlines()
    
    # Apply each hunk sequentially
    modified_lines = original_lines.copy()
    
    # Sort hunks by starting line to apply in order
    sorted_hunks = sorted(file_diff.hunks, key=lambda h: h.old_start)
    
    # Track line offset as we apply hunks
    line_offset = 0
    
    for hunk in sorted_hunks:
        # Adjust hunk start position based on previous changes
        adjusted_hunk = DiffHunk(
            old_start=hunk.old_start + line_offset,
            old_count=hunk.old_count,
            new_start=hunk.new_start,
            new_count=hunk.new_count,
            lines=hunk.lines
        )
        
        try:
            modified_lines = apply_hunk_to_lines(modified_lines, adjusted_hunk)
            # Update offset for next hunk
            line_offset += (hunk.new_count - hunk.old_count)
        except DiffApplyError as e:
            raise DiffApplyError(f"Failed to apply hunk at line {hunk.old_start}: {str(e)}")
    
    # Write modified content back to file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(modified_lines)
    
    # Calculate statistics
    lines_added = sum(1 for hunk in file_diff.hunks for line in hunk.lines if line.startswith('+'))
    lines_removed = sum(1 for hunk in file_diff.hunks for line in hunk.lines if line.startswith('-'))
    
    return {
        "status": "modified",
        "file": file_diff.new_path,
        "message": f"Modified file: {file_diff.new_path}",
        "lines_added": lines_added,
        "lines_removed": lines_removed
    }


def apply_git_diff(
    diff_content: str,
    base_directory: str = ".",
    dry_run: bool = False
) -> Dict[str, any]:
    """
    Parse and apply a git diff to files.
    
    Args:
        diff_content: String content of a git diff file
        base_directory: Base directory for file paths
        dry_run: If True, parse but don't apply changes
        
    Returns:
        Dictionary with summary of changes applied
        
    Raises:
        DiffParseError: If diff parsing fails
        DiffApplyError: If applying changes fails
    """
    # Parse the diff
    try:
        file_diffs = parse_git_diff(diff_content)
    except DiffParseError as e:
        return {
            "success": False,
            "error": f"Failed to parse diff: {str(e)}",
            "files_processed": 0
        }
    
    if not file_diffs:
        return {
            "success": False,
            "error": "No file changes found in diff",
            "files_processed": 0
        }
    
    # Apply changes to each file
    results = []
    errors = []
    
    for file_diff in file_diffs:
        try:
            if dry_run:
                results.append({
                    "status": "dry_run",
                    "file": file_diff.new_path,
                    "message": f"Would process: {file_diff.new_path}",
                    "hunks": len(file_diff.hunks)
                })
            else:
                result = apply_file_diff(file_diff, base_directory)
                results.append(result)
        except (DiffApplyError, Exception) as e:
            errors.append({
                "file": file_diff.new_path,
                "error": str(e)
            })
    
    # Build summary
    total_files = len(file_diffs)
    successful_files = len(results)
    failed_files = len(errors)
    
    summary = {
        "success": failed_files == 0,
        "total_files": total_files,
        "successful_files": successful_files,
        "failed_files": failed_files,
        "results": results,
        "dry_run": dry_run
    }
    
    if errors:
        summary["errors"] = errors
    
    return summary


def apply_diff_from_file(
    diff_file_path: str,
    base_directory: str = ".",
    dry_run: bool = False
) -> Dict[str, any]:
    """
    Read and apply a git diff from a file.
    
    Args:
        diff_file_path: Path to the diff file
        base_directory: Base directory for file paths
        dry_run: If True, parse but don't apply changes
        
    Returns:
        Dictionary with summary of changes applied
    """
    if not os.path.exists(diff_file_path):
        return {
            "success": False,
            "error": f"Diff file not found: {diff_file_path}",
            "files_processed": 0
        }
    
    try:
        with open(diff_file_path, 'r', encoding='utf-8') as f:
            diff_content = f.read()
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to read diff file: {str(e)}",
            "files_processed": 0
        }
    
    return apply_git_diff(diff_content, base_directory, dry_run)

