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


def _call_gemini(prompt: str, cwd: Optional[str] = None) -> str:
    """
    Call gemini-cli with a prompt and return the JSON response.
    Uses file redirection to avoid output truncation issues.
    
    Args:
        prompt: The prompt to send to Gemini
        cwd: Current working directory to execute gemini from (optional)
        
    Returns:
        JSON response as string (extracted from gemini-cli wrapper)
        
    Raises:
        TestExecutionError: If the call fails
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
                timeout=120,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise TestExecutionError(f"Gemini CLI error: {result.stderr}")
            
            # Read the complete output from file
            with open(tmp_path, 'r') as f:
                output = f.read()
            
            # Parse the gemini-cli JSON wrapper
            gemini_output = json.loads(output.strip())
            response_text = gemini_output.get('response', '')
            
            # Remove markdown code blocks if present
            if '```json' in response_text:
                start = response_text.find('```json') + 7
                end = response_text.rfind('```')
                if start > 6 and end > start:
                    response_text = response_text[start:end].strip()
            elif '```' in response_text:
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
        raise TestExecutionError("Gemini CLI request timed out")
    except FileNotFoundError:
        raise TestExecutionError("gemini-cli not found. Please ensure it's installed and in PATH")
    except json.JSONDecodeError as e:
        raise TestExecutionError(f"Failed to parse Gemini CLI output: {str(e)}")
    except Exception as e:
        raise TestExecutionError(f"Error calling Gemini CLI: {str(e)}")


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


def extract_test_files_from_result(generated_tests: Dict) -> List[str]:
    """
    Extract test file paths from generated_tests result.
    
    Args:
        generated_tests: Result from generate_unittest containing test files
        
    Returns:
        List of test file paths
    """
    test_files = []
    
    if generated_tests and generated_tests.get('success'):
        tests = generated_tests.get('tests', [])
        for test in tests:
            if test.get('success'):
                # Try to get output_file first (saved location), then test_file_name
                test_file = test.get('output_file') or test.get('test_file_name')
                if test_file and os.path.exists(test_file):
                    test_files.append(test_file)
    
    return test_files


def generate_test_commands_for_files(
    test_files: List[str],
    framework: str,
    base_directory: str
) -> Dict[str, str]:
    """
    Use Gemini to generate specific commands for each test file.
    
    Args:
        test_files: List of test file paths
        framework: Testing framework to use
        base_directory: Base directory of the project
        
    Returns:
        Dictionary mapping test file to command
    """
    if not test_files:
        return {}
    
    # Build prompt for Gemini
    test_files_str = '\n'.join([f"- {os.path.basename(f)}" for f in test_files])
    
    prompt = f"""You are a testing expert. Analyze the project and generate comprehensive setup and test execution commands.

TESTING FRAMEWORK: {framework}

TEST FILES:
{test_files_str}

TASK:
1. Install ALL required dependencies:
   a) Project dependencies (runtime dependencies)
   b) Development dependencies (testing frameworks and tools)
   c) Type definitions if TypeScript
2. For each test file, provide the command to run it

Return a JSON object:
{{
  "setup_commands": [
    "npm install",
    "npm install --save-dev jest @types/jest ts-jest",
    "npm run build"
  ],
  "commands": [
    {{
      "file": "test_auth.test.ts",
      "command": "npm test -- test_auth.test.ts"
    }},
    {{
      "file": "test_login.test.ts",
      "command": "npm test -- test_login.test.ts"
    }}
  ]
}}

CRITICAL DEPENDENCY RULES:

For JavaScript/TypeScript projects:
- Install project deps: "npm install" or "pnpm install" or "yarn install"
- Install test framework:
  * Jest: "npm install --save-dev jest @types/jest ts-jest @jest/globals"
  * Vitest: "npm install --save-dev vitest @vitest/ui"
  * Mocha: "npm install --save-dev mocha @types/mocha chai"
- Install TypeScript deps if .ts files: "@types/node typescript ts-node"
- Build if needed: "npm run build" or "tsc"

For Python projects:
- Install deps: "pip install -r requirements.txt"
- Install test framework:
  * pytest: "pip install pytest pytest-cov"
  * unittest: (built-in, no install needed)

CRITICAL TEST COMMAND RULES:

For JavaScript/TypeScript:
- PREFER npm scripts: "npm test -- <file>" or "npm run test:specific <file>"
- Alternative with npx: "npx jest <file> --verbose"
- Alternative with package manager: "pnpm test <file>"

For Python:
- Use pytest: "pytest <file> -v"
- Or python -m: "python -m pytest <file> -v"

IMPORTANT:
- Include ALL dependencies (project + dev + testing)
- Use package.json scripts when available (npm test, npm run test)
- For each test file, provide ONE specific command
- Include verbose/detailed output flags
- Return ONLY valid JSON, no additional text

Generate the commands:
"""
    
    try:
        response_text = _call_gemini(prompt, cwd=base_directory)
        
        # Parse JSON response
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        
        if start != -1 and end > start:
            json_str = response_text[start:end]
            result = json.loads(json_str)
            
            # Extract setup commands
            setup_commands = result.get('setup_commands', [])
            
            # Run setup commands if any
            if setup_commands:
                print(f"\nRunning {len(setup_commands)} setup command(s)...")
                for setup_cmd in setup_commands:
                    print(f"  Setup: {setup_cmd}")
                    try:
                        setup_result = subprocess.run(
                            setup_cmd,
                            shell=True,
                            cwd=base_directory,
                            capture_output=True,
                            text=True,
                            timeout=300
                        )
                        if setup_result.returncode != 0:
                            print(f"    Warning: Setup command failed: {setup_result.stderr[:200]}")
                        else:
                            print(f"    ✓ Success")
                    except Exception as e:
                        print(f"    Warning: Setup command error: {e}")
            
            # Build file->command mapping
            commands_map = {}
            for cmd_info in result.get('commands', []):
                file_name = cmd_info.get('file')
                command = cmd_info.get('command')
                
                # Match file name to full path
                for test_file in test_files:
                    if os.path.basename(test_file) == file_name:
                        commands_map[test_file] = command
                        break
            
            return commands_map
    except Exception as e:
        print(f"Error generating commands with Gemini: {e}")
        
        # Fallback: generate basic commands
        commands_map = {}
        for test_file in test_files:
            file_name = os.path.basename(test_file)
            if framework == 'pytest':
                commands_map[test_file] = f"pytest {file_name} -v"
            elif framework in ['jest', 'vitest']:
                commands_map[test_file] = f"npx {framework} {file_name} --verbose"
            else:
                commands_map[test_file] = f"{framework} {file_name}"
        
        return commands_map
    
    return {}


def run_tests(
    directory: str,
    test_file: Optional[str] = None,
    framework: Optional[str] = None,
    with_coverage: bool = False,
    verbose: bool = True,
    test_commands_result: Optional[Dict] = None,
    generated_tests: Optional[Dict] = None
) -> Dict[str, any]:
    """
    Run unit tests and return results.
    
    Args:
        directory: Project directory
        test_file: Specific test file to run (optional)
        framework: Test framework to use (auto-detected if None)
        with_coverage: Include coverage report
        verbose: Verbose output
        test_commands_result: Result from generate_test_commands (framework info)
        generated_tests: Result from generate_unittest (test files to run)
        
    Returns:
        Dictionary with test results
    """
    if not os.path.exists(directory):
        return {
            "success": False,
            "error": f"Directory not found: {directory}",
            "results": None
        }
    
    # Extract framework from test_commands_result
    if test_commands_result and test_commands_result.get('success'):
        framework = test_commands_result.get('recommended_framework', framework)
    elif framework is None:
        framework = detect_test_framework(directory)
    
    # NEW: Extract test files from generated_tests and generate commands for each
    if generated_tests:
        test_files = extract_test_files_from_result(generated_tests)
        
        if test_files:
            print(f"Found {len(test_files)} test files to run:")
            for tf in test_files:
                print(f"  - {os.path.basename(tf)}")
            
            # Generate commands for each test file using Gemini
            print(f"Generating commands for each test file using {framework}...")
            print("test_files", test_files)
            test_commands = generate_test_commands_for_files(test_files, framework, directory)
            if not test_commands:
                return {
                    "success": False,
                    "error": "Failed to generate test commands",
                    "results": None
                }
            
            # Run each test file individually
            all_results = []
            total_passed = 0
            total_failed = 0
            total_tests = 0
            print("test_commands", test_commands)
            for test_file, cmd_str in test_commands.items():
                print(f"\nRunning: {cmd_str}")
                cmd = cmd_str.split()
                
                # Add coverage flags if needed
                if with_coverage and framework == 'pytest':
                    if '--cov' not in cmd:
                        cmd.extend(['--cov', '--cov-report=term'])
                
                try:
                    try:
                        result = subprocess.run(
                            cmd,
                            cwd=directory,
                            capture_output=True,
                            text=True,
                            timeout=300
                        )
                    except FileNotFoundError:
                        # If command not found, try alternative approaches for JS frameworks
                        if framework in ['jest', 'vitest', 'mocha']:
                            # Try 1: Add npx prefix
                            if not cmd[0].startswith('npx') and cmd[0] not in ['npm', 'pnpm', 'yarn']:
                                print(f"  ⚠️  Command not found, retrying with npx...")
                                cmd = ['npx'] + cmd
                                cmd_str = ' '.join(cmd)
                                print(f"  Retry: {cmd_str}")
                                result = subprocess.run(
                                    cmd,
                                    cwd=directory,
                                    capture_output=True,
                                    text=True,
                                    timeout=300
                                )
                            # Try 2: Use npm test if npx also fails
                            else:
                                print(f"  ⚠️  Command not found, trying npm test...")
                                test_file_name = os.path.basename(test_file)
                                cmd = ['npm', 'test', '--', test_file_name]
                                cmd_str = ' '.join(cmd)
                                print(f"  Retry: {cmd_str}")
                                result = subprocess.run(
                                    cmd,
                                    cwd=directory,
                                    capture_output=True,
                                    text=True,
                                    timeout=300
                                )
                        else:
                            raise
                    
                    # Display test output immediately
                    print("\n" + "="*70)
                    if result.stdout:
                        print("OUTPUT:")
                        print(result.stdout)
                    if result.stderr and result.returncode != 0:
                        print("\nERROR OUTPUT:")
                        print(result.stderr)
                    print("="*70)
                    
                    # Parse output
                    if framework == 'pytest':
                        parsed = parse_pytest_output(result.stdout, result.stderr)
                    elif framework in ['jest', 'vitest']:
                        parsed = parse_jest_output(result.stdout, result.stderr)
                    else:
                        parsed = {
                            "tests_run": 0,
                            "tests_passed": 0,
                            "tests_failed": 0,
                            "test_cases": []
                        }
                    
                    total_passed += parsed.get('tests_passed', 0)
                    total_failed += parsed.get('tests_failed', 0)
                    total_tests += parsed.get('tests_run', 0)
                    
                    # Display parsed summary
                    if result.returncode == 0:
                        print(f"✅ SUCCESS: {parsed.get('tests_passed', 0)} test(s) passed")
                    else:
                        print(f"❌ FAILED: {parsed.get('tests_failed', 0)} test(s) failed, {parsed.get('tests_passed', 0)} passed")
                    
                    all_results.append({
                        "test_file": os.path.basename(test_file),
                        "command": cmd_str,
                        "exit_code": result.returncode,
                        "success": result.returncode == 0,
                        "results": parsed,
                        "stdout": result.stdout if verbose else result.stdout[:500],
                        "stderr": result.stderr if verbose else result.stderr[:500]
                    })
                    
                except subprocess.TimeoutExpired:
                    print("\n" + "="*70)
                    print("❌ ERROR: Test execution timed out (300s limit)")
                    print("="*70)
                    all_results.append({
                        "test_file": os.path.basename(test_file),
                        "command": cmd_str,
                        "success": False,
                        "error": "Test execution timed out"
                    })
                except Exception as e:
                    print("\n" + "="*70)
                    print(f"❌ ERROR: {str(e)}")
                    print("="*70)
                    all_results.append({
                        "test_file": os.path.basename(test_file),
                        "command": cmd_str,
                        "success": False,
                        "error": str(e)
                    })
            
            # Return aggregated results
            overall_success = total_failed == 0 and total_tests > 0
            
            # Print final summary
            print("\n" + "="*70)
            print("FINAL SUMMARY")
            print("="*70)
            print(f"Total Files Tested: {len(test_files)}")
            print(f"Total Tests Run: {total_tests}")
            print(f"✅ Passed: {total_passed}")
            print(f"❌ Failed: {total_failed}")
            if overall_success:
                print("\n🎉 ALL TESTS PASSED!")
            else:
                print(f"\n⚠️  {total_failed} TEST(S) FAILED")
            print("="*70)
            
            return {
                "success": overall_success,
                "framework": framework,
                "test_files_run": len(test_files),
                "individual_results": all_results,
                "summary": {
                    "total": total_tests,
                    "passed": total_passed,
                    "failed": total_failed,
                    "files_tested": len(test_files)
                },
                "results": {
                    "tests_run": total_tests,
                    "tests_passed": total_passed,
                    "tests_failed": total_failed,
                    "failures": []  # Aggregate failures if needed
                }
            }
    
    # Fallback: Original behavior if no generated_tests provided
    if test_commands_result and test_commands_result.get('commands'):
        commands = test_commands_result.get('commands', [])
        if commands and len(commands) > 0:
            cmd_str = commands[0].get('command', '')
            cmd = cmd_str.split() if cmd_str else get_test_command(framework, test_file)
        else:
            cmd = get_test_command(framework, test_file)
    else:
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

