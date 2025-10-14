"""
Run unit tests and capture results.

This module executes unit tests and returns structured results including
pass/fail status, coverage information, and detailed output.
"""
import os
import json
import subprocess
import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime


class TestExecutionError(Exception):
    """Exception raised when test execution fails."""
    pass


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
        'go': ['go.mod']
    }
    
    for framework, indicators in framework_indicators.items():
        for indicator in indicators:
            if os.path.exists(os.path.join(directory, indicator)):
                return framework
    
    # Check package.json for JS frameworks
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
    
    return 'pytest'  # Default


def get_test_command(framework: str, test_file: Optional[str] = None) -> List[str]:
    """
    Get the command to run tests for a framework.
    
    Args:
        framework: Test framework name
        test_file: Specific test file to run (optional)
        
    Returns:
        Command as list of strings
    """
    commands = {
        'pytest': ['pytest', '-v', '--tb=short'],
        'jest': ['npx', 'jest', '--verbose'],
        'vitest': ['npx', 'vitest', 'run'],
        'mocha': ['npx', 'mocha'],
        'junit': ['mvn', 'test'],
        'go': ['go', 'test', '-v'],
        'unittest': ['python', '-m', 'unittest', 'discover']
    }
    
    cmd = commands.get(framework, ['pytest', '-v'])
    
    # Add test file if specified
    if test_file:
        if framework in ['pytest', 'mocha']:
            cmd.append(test_file)
        elif framework in ['jest', 'vitest']:
            cmd.append(test_file)
    
    return cmd


def parse_pytest_output(output: str, error: str) -> Dict:
    """
    Parse pytest output to extract test results.
    
    Args:
        output: Standard output from pytest
        error: Standard error from pytest
        
    Returns:
        Dictionary with parsed results
    """
    results = {
        "tests_run": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "tests_skipped": 0,
        "duration": 0.0,
        "test_cases": [],
        "failures": [],
        "coverage": None
    }
    
    combined = output + "\n" + error
    
    # Parse summary line (e.g., "5 passed, 2 failed in 1.23s")
    summary_match = re.search(r'(\d+)\s+passed', combined)
    if summary_match:
        results["tests_passed"] = int(summary_match.group(1))
    
    failed_match = re.search(r'(\d+)\s+failed', combined)
    if failed_match:
        results["tests_failed"] = int(failed_match.group(1))
    
    skipped_match = re.search(r'(\d+)\s+skipped', combined)
    if skipped_match:
        results["tests_skipped"] = int(skipped_match.group(1))
    
    # Total tests
    results["tests_run"] = (results["tests_passed"] + 
                           results["tests_failed"] + 
                           results["tests_skipped"])
    
    # Parse duration
    duration_match = re.search(r'in\s+([\d.]+)s', combined)
    if duration_match:
        results["duration"] = float(duration_match.group(1))
    
    # Parse individual test results (PASSED/FAILED)
    test_pattern = r'([\w/\.]+)::([\w_]+)\s+(PASSED|FAILED|SKIPPED)'
    for match in re.finditer(test_pattern, combined):
        file_path, test_name, status = match.groups()
        results["test_cases"].append({
            "file": file_path,
            "name": test_name,
            "status": status.lower(),
            "full_name": f"{file_path}::{test_name}"
        })
    
    # Parse failures
    if results["tests_failed"] > 0:
        # Look for FAILED sections
        failure_pattern = r'FAILED\s+([\w/\.]+::\w+)\s+-\s+(.+?)(?=FAILED|$)'
        for match in re.finditer(failure_pattern, combined, re.DOTALL):
            test_name, error_msg = match.groups()
            results["failures"].append({
                "test": test_name.strip(),
                "error": error_msg.strip()[:200]  # Limit error message length
            })
    
    # Parse coverage if present
    coverage_match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', combined)
    if coverage_match:
        results["coverage"] = int(coverage_match.group(1))
    
    return results


def parse_jest_output(output: str, error: str) -> Dict:
    """
    Parse Jest output to extract test results.
    
    Args:
        output: Standard output from jest
        error: Standard error from jest
        
    Returns:
        Dictionary with parsed results
    """
    results = {
        "tests_run": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "tests_skipped": 0,
        "duration": 0.0,
        "test_cases": [],
        "failures": [],
        "coverage": None
    }
    
    combined = output + "\n" + error
    
    # Parse summary (e.g., "Tests: 5 passed, 5 total")
    passed_match = re.search(r'Tests:\s+(\d+)\s+passed', combined)
    if passed_match:
        results["tests_passed"] = int(passed_match.group(1))
    
    failed_match = re.search(r'(\d+)\s+failed', combined)
    if failed_match:
        results["tests_failed"] = int(failed_match.group(1))
    
    total_match = re.search(r'(\d+)\s+total', combined)
    if total_match:
        results["tests_run"] = int(total_match.group(1))
    
    # Parse duration (e.g., "Time: 2.345 s")
    duration_match = re.search(r'Time:\s+([\d.]+)\s*s', combined)
    if duration_match:
        results["duration"] = float(duration_match.group(1))
    
    # Parse test results
    test_pattern = r'✓\s+(.*?)\s+\((\d+)\s*ms\)'
    for match in re.finditer(test_pattern, combined):
        test_name, duration = match.groups()
        results["test_cases"].append({
            "name": test_name.strip(),
            "status": "passed",
            "duration_ms": int(duration)
        })
    
    # Parse failures
    fail_pattern = r'✕\s+(.*?)(?=\n|$)'
    for match in re.finditer(fail_pattern, combined):
        test_name = match.group(1).strip()
        results["failures"].append({
            "test": test_name,
            "error": "See output for details"
        })
    
    # Parse coverage
    coverage_match = re.search(r'All files\s*\|\s*([\d.]+)', combined)
    if coverage_match:
        results["coverage"] = float(coverage_match.group(1))
    
    return results


def run_tests(
    directory: str,
    test_file: Optional[str] = None,
    framework: Optional[str] = None,
    with_coverage: bool = False,
    verbose: bool = True
) -> Dict[str, any]:
    """
    Run unit tests and return results.
    
    Args:
        directory: Project directory
        test_file: Specific test file to run (optional)
        framework: Test framework to use (auto-detected if None)
        with_coverage: Include coverage report
        verbose: Verbose output
        
    Returns:
        Dictionary with test results
    """
    if not os.path.exists(directory):
        return {
            "success": False,
            "error": f"Directory not found: {directory}",
            "results": None
        }
    
    # Detect framework if not provided
    if framework is None:
        framework = detect_test_framework(directory)
    
    # Get test command
    cmd = get_test_command(framework, test_file)
    
    # Add coverage flags
    if with_coverage:
        if framework == 'pytest':
            cmd.extend(['--cov', '--cov-report=term'])
        elif framework in ['jest', 'vitest']:
            cmd.append('--coverage')
    
    print(f"Running tests with: {' '.join(cmd)}")
    print(f"Framework: {framework}")
    print(f"Directory: {directory}")
    
    # Run tests
    try:
        start_time = datetime.now()
        
        result = subprocess.run(
            cmd,
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        # Parse output based on framework
        if framework == 'pytest':
            parsed_results = parse_pytest_output(result.stdout, result.stderr)
        elif framework in ['jest', 'vitest']:
            parsed_results = parse_jest_output(result.stdout, result.stderr)
        else:
            # Generic parsing
            parsed_results = {
                "tests_run": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "duration": execution_time,
                "test_cases": [],
                "failures": []
            }
        
        # Determine success
        success = result.returncode == 0
        
        return {
            "success": success,
            "framework": framework,
            "command": ' '.join(cmd),
            "exit_code": result.returncode,
            "execution_time": execution_time,
            "results": parsed_results,
            "stdout": result.stdout if verbose else result.stdout[:1000],
            "stderr": result.stderr if verbose else result.stderr[:500],
            "summary": {
                "total": parsed_results["tests_run"],
                "passed": parsed_results["tests_passed"],
                "failed": parsed_results["tests_failed"],
                "skipped": parsed_results.get("tests_skipped", 0),
                "coverage": parsed_results.get("coverage"),
                "duration": parsed_results.get("duration", execution_time)
            }
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Test execution timed out (300s limit)",
            "framework": framework,
            "results": None
        }
    except FileNotFoundError as e:
        return {
            "success": False,
            "error": f"Test command not found: {cmd[0]}. Please install {framework}.",
            "framework": framework,
            "results": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error running tests: {str(e)}",
            "framework": framework,
            "results": None
        }


def run_tests_and_save_report(
    directory: str,
    output_file: str,
    test_file: Optional[str] = None,
    framework: Optional[str] = None,
    with_coverage: bool = False
) -> Dict[str, any]:
    """
    Run tests and save results to a JSON file.
    
    Args:
        directory: Project directory
        output_file: Path to save the JSON report
        test_file: Specific test file (optional)
        framework: Test framework (optional)
        with_coverage: Include coverage
        
    Returns:
        Dictionary with results
    """
    result = run_tests(
        directory=directory,
        test_file=test_file,
        framework=framework,
        with_coverage=with_coverage
    )
    
    # Save to file
    try:
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        
        result['report_file'] = output_file
        result['message'] = f"Test report saved to {output_file}"
    except Exception as e:
        result['save_error'] = f"Failed to save report: {str(e)}"
    
    return result


def run_specific_test(
    test_file: str,
    test_name: Optional[str] = None,
    framework: Optional[str] = None
) -> Dict[str, any]:
    """
    Run a specific test file or test case.
    
    Args:
        test_file: Path to test file
        test_name: Specific test name (optional)
        framework: Test framework (optional)
        
    Returns:
        Dictionary with results
    """
    if not os.path.exists(test_file):
        return {
            "success": False,
            "error": f"Test file not found: {test_file}",
            "results": None
        }
    
    directory = os.path.dirname(os.path.abspath(test_file))
    
    # Build command for specific test
    if framework is None:
        framework = detect_test_framework(directory)
    
    cmd = get_test_command(framework, test_file)
    
    # Add specific test name if provided
    if test_name:
        if framework == 'pytest':
            cmd[-1] = f"{test_file}::{test_name}"
        elif framework in ['jest', 'vitest']:
            cmd.extend(['-t', test_name])
    
    # Run in directory context
    return run_tests(
        directory=directory,
        test_file=os.path.basename(test_file),
        framework=framework
    )

