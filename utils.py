"""
Utility functions for file handling and code extraction.
"""
import os
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Tuple


def extract_zip(zip_path: str, extract_to: str) -> str:
    """
    Extract a zip file to a directory.
    
    If the extracted content is a single folder, moves its contents to the root
    of the extraction directory to avoid unnecessary nesting.

    Args:
        zip_path: Path to the zip file
        extract_to: Directory to extract to

    Returns:
        Path to the extracted directory
    """
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    
    # Check if extracted content is just a single folder
    extracted_items = os.listdir(extract_to)
    
    # If there's only one item and it's a directory, flatten it
    if len(extracted_items) == 1:
        single_item = extracted_items[0]
        single_item_path = os.path.join(extract_to, single_item)
        
        if os.path.isdir(single_item_path):
            # This is a single folder - move all its contents up one level
            temp_dir = tempfile.mkdtemp(dir=os.path.dirname(extract_to))
            
            try:
                # Move all contents from the nested folder to temp
                for item in os.listdir(single_item_path):
                    src = os.path.join(single_item_path, item)
                    dst = os.path.join(temp_dir, item)
                    shutil.move(src, dst)
                
                # Remove the now-empty nested folder
                shutil.rmtree(single_item_path)
                
                # Move everything from temp to the extraction directory
                for item in os.listdir(temp_dir):
                    src = os.path.join(temp_dir, item)
                    dst = os.path.join(extract_to, item)
                    shutil.move(src, dst)
                
            finally:
                # Clean up temp directory
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
    
    return extract_to


def get_code_files(directory: str, extensions: Tuple[str, ...] = None) -> List[str]:
    """
    Get all code files from a directory recursively.

    Args:
        directory: Root directory to search
        extensions: Tuple of file extensions to include (e.g., ('.py', '.js', '.ts'))

    Returns:
        List of file paths
    """
    if extensions is None:
        extensions = (
            '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h',
            '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.cs', '.scala',
            '.sql', '.graphql', '.vue', '.svelte'
        )

    code_files = []
    for root, _, files in os.walk(directory):
        # Skip common non-source directories
        if any(skip in root for skip in ['node_modules', 'venv', '__pycache__', '.git', 'dist', 'build']):
            continue

        for file in files:
            if file.endswith(extensions):
                code_files.append(os.path.join(root, file))

    return code_files


def read_file_with_lines(file_path: str) -> str:
    """
    Read a file and return its contents with line numbers.

    Args:
        file_path: Path to the file

    Returns:
        File contents with line numbers
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            numbered_lines = [f"{i+1}: {line}" for i, line in enumerate(lines)]
            return ''.join(numbered_lines)
    except Exception as e:
        return f"Error reading file: {str(e)}"


def get_project_structure(directory: str, max_depth: int = 3) -> str:
    """
    Get a text representation of the project structure.

    Args:
        directory: Root directory
        max_depth: Maximum depth to traverse

    Returns:
        Text representation of directory structure
    """
    structure = []

    def walk_directory(path: str, prefix: str = "", depth: int = 0):
        if depth > max_depth:
            return

        try:
            entries = sorted(os.listdir(path))
        except PermissionError:
            return

        # Filter out common non-source directories
        skip_dirs = {'node_modules', 'venv', '__pycache__', '.git', 'dist', 'build', '.next', 'coverage'}
        entries = [e for e in entries if e not in skip_dirs]

        for i, entry in enumerate(entries):
            entry_path = os.path.join(path, entry)
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            structure.append(f"{prefix}{connector}{entry}")

            if os.path.isdir(entry_path):
                extension = "    " if is_last else "│   "
                walk_directory(entry_path, prefix + extension, depth + 1)

    structure.append(os.path.basename(directory) + "/")
    walk_directory(directory)
    return "\n".join(structure)


def extract_code_context(file_path: str, max_lines: int = 500) -> str:
    """
    Extract code context from a file with size limits.

    Args:
        file_path: Path to the file
        max_lines: Maximum number of lines to include

    Returns:
        Code content with truncation if needed
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        if len(lines) > max_lines:
            return ''.join(lines[:max_lines]) + f"\n... (truncated, {len(lines) - max_lines} more lines)"

        return ''.join(lines)
    except Exception as e:
        return f"Error reading file: {str(e)}"
