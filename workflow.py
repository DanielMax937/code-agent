"""
LangGraph workflow for automated code modification and testing.

This workflow sequences 4 agents to automate the complete development cycle:
1. Generate test commands
2. Modify code directly (AI-powered code modification)
3. Generate unit tests
4. Run tests (with retry logic)
"""
import os
import subprocess
from typing import Dict, List, Optional, TypedDict, Annotated, Tuple
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from tools import (
    generate_test_commands,
    modify_code,
    generate_unittest,
    generate_and_save_unittest,
    run_tests
)


class WorkflowState(TypedDict):
    """State for the agent workflow."""
    # Input
    feature_description: str
    feature_files: List[str]
    base_directory: str
    
    # Progress tracking
    current_step: str
    retry_count: int
    max_retries: int
    
    # Agent outputs
    test_commands: Optional[Dict]
    modify_result: Optional[Dict]
    changes_diff: Optional[str]  # Git diff of changes made
    generated_tests: Optional[Dict]
    test_results: Optional[Dict]
    
    # Errors and logs
    errors: Annotated[List[str], add_messages]
    logs: Annotated[List[str], add_messages]
    
    # Final status
    success: bool
    final_message: str


def run_git_command(command: List[str], cwd: str) -> Tuple[bool, str]:
    """
    Run a git command and return success status and output.
    
    Args:
        command: Git command as list (e.g., ['git', 'status'])
        cwd: Working directory
        
    Returns:
        Tuple of (success, output/error)
    """
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0, result.stdout if result.returncode == 0 else result.stderr
    except Exception as e:
        return False, str(e)


def ensure_git_repo(base_directory: str) -> Tuple[bool, str]:
    """
    Ensure git repository exists and create initial commit.
    
    Args:
        base_directory: Project directory
        
    Returns:
        Tuple of (success, message)
    """
    git_dir = os.path.join(base_directory, '.git')
    
    # Check if .git exists
    if os.path.exists(git_dir):
        return True, "Git repository already initialized"
    
    # Initialize git repo
    success, output = run_git_command(['git', 'init'], base_directory)
    if not success:
        return False, f"Failed to initialize git: {output}"
    
    # Configure git user (needed for commits)
    run_git_command(['git', 'config', 'user.name', 'Code Agent'], base_directory)
    run_git_command(['git', 'config', 'user.email', 'agent@codeagent.local'], base_directory)
    
    # Add all files
    success, output = run_git_command(['git', 'add', '.'], base_directory)
    if not success:
        return False, f"Failed to add files: {output}"
    
    # Create initial commit
    success, output = run_git_command(
        ['git', 'commit', '-m', 'Initial commit before code changes'],
        base_directory
    )
    if not success:
        # If nothing to commit, that's okay
        if 'nothing to commit' in output.lower():
            return True, "Git repository initialized (no files to commit)"
        return False, f"Failed to commit: {output}"
    
    return True, "Git repository initialized and committed"


def get_git_diff(base_directory: str) -> Tuple[bool, str]:
    """
    Get git diff of current changes, excluding backup files.
    
    Args:
        base_directory: Project directory
        
    Returns:
        Tuple of (success, diff_content)
    """
    # Use pathspec to exclude .backup files
    success, diff = run_git_command(
        ['git', 'diff', '--', '.', ':(exclude)*.backup'],
        base_directory
    )
    if not success:
        return False, f"Failed to get diff: {diff}"
    
    if not diff.strip():
        return True, "# No changes detected"
    
    return True, diff


def initialize_state(
    feature_description: str,
    feature_files: List[str],
    base_directory: str = ".",
    max_retries: int = 3
) -> WorkflowState:
    """Initialize the workflow state."""
    # Convert all file paths to absolute paths
    absolute_files = []
    for file_path in feature_files:
        if os.path.isabs(file_path):
            absolute_files.append(file_path)
        else:
            absolute_files.append(os.path.join(base_directory, file_path))
    
    return WorkflowState(
        feature_description=feature_description,
        feature_files=absolute_files,
        base_directory=base_directory,
        current_step="start",
        retry_count=0,
        max_retries=max_retries,
        test_commands=None,
        modify_result=None,
        changes_diff=None,
        generated_tests=None,
        test_results=None,
        errors=[],
        logs=[],
        success=False,
        final_message=""
    )


def generate_test_commands_node(state: WorkflowState) -> WorkflowState:
    """Node 1: Generate test commands and recommend testing framework."""
    state["current_step"] = "generate_test_commands"
    state["logs"].append("Step 1: Analyzing project and recommending testing framework...")
    
    try:
        result = generate_test_commands(directory=state["base_directory"])
        
        if result['success']:
            state["test_commands"] = result
            
            # Log recommended framework and reason
            framework = result.get('recommended_framework', 'Unknown')
            reason = result.get('reason', '')
            alternatives = result.get('alternative_frameworks', [])
            
            state["logs"].append(f"✅ Recommended framework: {framework}")
            if reason:
                state["logs"].append(f"   Reason: {reason[:150]}...")
            if alternatives:
                state["logs"].append(f"   Alternatives: {', '.join(alternatives[:3])}")
            
            # Log setup commands count
            setup_count = len(result.get('setup_commands', []))
            if setup_count > 0:
                state["logs"].append(f"   Setup commands: {setup_count} command(s) to configure testing")
                
        else:
            error = f"Failed to generate test commands: {result.get('error', 'Unknown error')}"
            state["errors"].append(error)
            state["logs"].append(f"❌ {error}")
            
    except Exception as e:
        error = f"Error in generate_test_commands: {str(e)}"
        state["errors"].append(error)
        state["logs"].append(f"❌ {error}")
    
    return state


def modify_code_node(state: WorkflowState) -> WorkflowState:
    """Node 2: Modify code based on feature description."""
    state["current_step"] = "modify_code"
    
    # Add retry context to prompt if this is a retry
    prompt = state["feature_description"]
    if state["retry_count"] > 0:
        last_error = state["test_results"].get("results", {}).get("failures", [])
        if last_error:
            error_context = "\n".join([f"- {f['test']}: {f['error']}" for f in last_error[:3]])
            prompt = f"""{prompt}

IMPORTANT: Previous implementation failed with these test errors:
{error_context}

Please fix these issues in the new implementation."""
        
        state["logs"].append(f"🔄 Retry {state['retry_count']}/{state['max_retries']}: Modifying code with error context...")
    else:
        state["logs"].append("Step 2: Modifying code directly...")
    
    # Ensure git repository and create initial commit
    state["logs"].append("   Initializing git repository and committing current state...")
    git_success, git_message = ensure_git_repo(state["base_directory"])
    if git_success:
        state["logs"].append(f"   ✅ {git_message}")
    else:
        state["logs"].append(f"   ⚠️  {git_message} (continuing without git tracking)")
    
    try:
        result = modify_code(
            prompt=prompt,
            file_paths=state["feature_files"],
            base_directory=state["base_directory"],
            create_backup=True,
            dry_run=False
        )
        
        if result['success']:
            files_modified = result.get('files_modified', 0)
            state["logs"].append(f"✅ Modified {files_modified} file(s) successfully")
            
            # Log details of changes
            for change in result.get('changes', [])[:5]:  # Show first 5
                file_name = change.get('file', 'unknown')
                status = change.get('status', 'unknown')
                state["logs"].append(f"   • {file_name}: {status}")
            
            # Get git diff of changes - this is the source of truth
            state["logs"].append("   Capturing changes with git diff...")
            diff_success, diff_content = get_git_diff(state["base_directory"])
            
            if diff_success:
                state["changes_diff"] = diff_content
                diff_lines = len(diff_content.split('\n'))
                state["logs"].append(f"   ✅ Captured diff ({diff_lines} lines)")
                
                # Parse git diff to extract modified files
                modified_files = []
                for line in diff_content.split('\n'):
                    if line.startswith('diff --git'):
                        # Extract file path: "diff --git a/path b/path"
                        parts = line.split()
                        if len(parts) >= 4:
                            file_path = parts[2][2:]  # Remove "a/" prefix
                            modified_files.append(file_path)
                
                # Set modify_result based on git diff (source of truth)
                state["modify_result"] = {
                    "success": True,
                    "source": "git_diff",
                    "diff": diff_content,
                    "files_modified": len(modified_files),
                    "modified_files": modified_files,
                    "diff_lines": diff_lines
                }
            else:
                state["logs"].append(f"   ⚠️  Could not capture diff: {diff_content}")
                state["changes_diff"] = None
                # Fallback to AI result if git diff fails
                state["modify_result"] = result
        else:
            error = f"Failed to modify code: {result.get('error', 'Unknown error')}"
            state["errors"].append(error)
            state["logs"].append(f"❌ {error}")
            
    except Exception as e:
        error = f"Error in modify_code: {str(e)}"
        state["errors"].append(error)
        state["logs"].append(f"❌ {error}")
    
    return state


def generate_unittest_node(state: WorkflowState) -> WorkflowState:
    """Node 3: Generate unit tests for the changes."""
    state["current_step"] = "generate_unittest"
    state["logs"].append("Step 3: Generating unit tests...")
    
    try:
        # Build test description with git diff context
        diff_context = ""
        if state.get("changes_diff"):
            diff_context = f"""

CHANGES MADE (Git Diff):
```diff
{state["changes_diff"]}
```

Generate tests specifically for the changes shown in the diff above.
"""
        
        # Generate tests for each modified file
        test_results = []
        
        for file_path in state["feature_files"]:
            test_description = f"""
Generate comprehensive unit tests for the feature: {state['feature_description']}
{diff_context}

Test requirements:
- Test all edge cases
- Test error handling
- Test normal operation
- Use appropriate assertions
- Focus on the specific changes made to this file
"""
            
            print(f"Generating tests for {file_path}")
            result = generate_and_save_unittest(
                source_file=file_path,
                test_description=test_description,
                test_commands_result=state.get("test_commands"),
                git_diff=state.get("changes_diff"),
                base_directory=state["base_directory"]
            )
            
            
            if result['success']:
                test_results.append(result)
                test_file = result.get('output_file', result.get('test_file_name', 'test file'))
                state["logs"].append(f"✅ Generated and saved tests for {file_path}")
                state["logs"].append(f"   Test file: {test_file}")
            else:
                state["logs"].append(f"⚠️  Could not generate tests for {file_path}: {result.get('error', 'Unknown')}")
        
        if test_results:
            state["generated_tests"] = {
                "success": True,
                "tests": test_results,
                "count": len(test_results)
            }
            state["logs"].append(f"✅ Generated {len(test_results)} test files")
        else:
            error = "Failed to generate any tests"
            state["errors"].append(error)
            state["logs"].append(f"❌ {error}")
            
    except Exception as e:
        error = f"Error in generate_unittest: {str(e)}"
        state["errors"].append(error)
        state["logs"].append(f"❌ {error}")
    
    return state


def run_tests_node(state: WorkflowState) -> WorkflowState:
    """Node 4: Run the tests and capture results."""
    state["current_step"] = "run_tests"
    state["logs"].append("Step 4: Running unit tests...")
    
    try:
        result = run_tests(
            directory=state["base_directory"],
            with_coverage=True,
            test_commands_result=state.get("test_commands"),
            generated_tests=state.get("generated_tests")
        )
        
        state["test_results"] = result
        
        if result['success']:
            state["logs"].append(f"✅ All {result['summary']['passed']} tests passed!")
            if result['summary'].get('coverage'):
                state["logs"].append(f"📊 Coverage: {result['summary']['coverage']}%")
            state["success"] = True
            state["final_message"] = f"Feature implemented and tested successfully! {result['summary']['passed']}/{result['summary']['total']} tests passed."
        else:
            failed_count = result['summary'].get('failed', 0)
            state["logs"].append(f"❌ {failed_count} tests failed")
            
            # Log first few failures
            for failure in result['results'].get('failures', [])[:3]:
                state["logs"].append(f"  • {failure['test']}: {failure['error'][:100]}")
            
            # Don't mark as error yet - will retry if possible
            
    except Exception as e:
        error = f"Error in run_tests: {str(e)}"
        state["errors"].append(error)
        state["logs"].append(f"❌ {error}")
    
    return state


def should_retry(state: WorkflowState) -> str:
    """Determine if we should retry after failed tests."""
    # If tests passed, we're done
    if state["success"]:
        return "end"
    
    # If we have errors in earlier steps, don't retry
    if state["errors"] and state["current_step"] != "run_tests":
        return "end"
    
    # If tests failed and we haven't exceeded retry limit
    if state["test_results"] and not state["test_results"]["success"]:
        if state["retry_count"] < state["max_retries"]:
            state["retry_count"] += 1
            return "retry"
        else:
            state["final_message"] = f"Tests failed after {state['max_retries']} attempts. Manual intervention required."
            return "end"
    
    # No test results or other issues
    return "end"


def build_workflow() -> StateGraph:
    """Build the LangGraph workflow."""
    workflow = StateGraph(WorkflowState)
    
    # Add nodes
    workflow.add_node("generate_test_commands", generate_test_commands_node)
    workflow.add_node("modify_code", modify_code_node)
    workflow.add_node("generate_unittest", generate_unittest_node)
    workflow.add_node("run_tests", run_tests_node)
    
    # Define the flow
    workflow.set_entry_point("generate_test_commands")
    workflow.add_edge("generate_test_commands", "modify_code")
    workflow.add_edge("modify_code", "generate_unittest")
    workflow.add_edge("generate_unittest", "run_tests")
    
    # Add conditional edge for retry logic
    # workflow.add_conditional_edges(
    #     "run_tests",
    #     should_retry,
    #     {
    #         "retry": "modify_code",  # Retry from code modification
    #         "end": END
    #     }
    # )
    
    return workflow.compile()


def run_feature_workflow(
    feature_description: str,
    feature_files: List[str],
    base_directory: str = ".",
    max_retries: int = 3
) -> Dict:
    """
    Run the complete workflow for a single feature.
    
    Args:
        feature_description: Description of the feature to implement
        feature_files: List of files to modify
        base_directory: Base directory for the project
        max_retries: Maximum number of retries on test failure
        
    Returns:
        Dictionary with workflow results
    """
    # Initialize state
    initial_state = initialize_state(
        feature_description=feature_description,
        feature_files=feature_files,
        base_directory=base_directory,
        max_retries=max_retries
    )
    
    # Build and run workflow
    app = build_workflow()
    
    try:
        # Execute the workflow
        final_state = app.invoke(initial_state)
        
        return {
            "success": final_state["success"],
            "message": final_state["final_message"],
            "retry_count": final_state["retry_count"],
            "test_results": final_state.get("test_results"),
            "logs": final_state["logs"],
            "errors": final_state["errors"]
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Workflow error: {str(e)}",
            "retry_count": 0,
            "test_results": None,
            "logs": [],
            "errors": [str(e)]
        }


def run_analysis_workflow(
    analysis_report: Dict,
    base_directory: str = ".",
    max_retries: int = 3
) -> List[Dict]:
    """
    Run the workflow for all features in an analysis report.
    
    Args:
        analysis_report: The analysis report from CodeAnalysisAgent
        base_directory: Base directory for the project
        max_retries: Maximum retries per feature
        
    Returns:
        List of results for each feature
    """
    results = []
    
    # Extract features from analysis report
    features = analysis_report.get("feature_analysis", [])
    
    print(f"\n🚀 Starting workflow for {len(features)} features...\n")
    
    for i, feature in enumerate(features, 1):
        feature_name = feature.get("feature_description", "Unknown feature")
        files_to_modify = [x.get("file") for x in feature.get("implementation_location", [])]
        implementation_notes = ", ".join([f"should modify function: {x.get('function')} in file: {x.get('file')} at lines: {x.get('lines')}" for x in feature.get("implementation_location", [])])
        
        print(f"{'='*80}")
        print(f"Feature {i}/{len(features)}: {feature_name}")
        print(f"{'='*80}")
        
        # Build feature description
        description = f"""
Feature: {feature_name}

Implementation Notes:
{implementation_notes}

Files to modify: {', '.join(files_to_modify)}
"""
        
        # Run workflow for this feature
        result = run_feature_workflow(
            feature_description=description,
            feature_files=files_to_modify,
            base_directory=base_directory,
            max_retries=max_retries
        )
        
        # Add feature info to result
        result["feature_name"] = feature_name
        result["feature_files"] = files_to_modify
        
        results.append(result)
        
        # Print summary
        if result["success"]:
            print(f"\n✅ SUCCESS: {feature_name}")
            if result["retry_count"] > 0:
                print(f"   (Succeeded after {result['retry_count']} retries)")
        else:
            print(f"\n❌ FAILED: {feature_name}")
            if result["errors"]:
                print(f"   Errors: {result['errors'][0]}")
        
        print(f"\n")
    
    # Print overall summary
    print(f"\n{'='*80}")
    print(f"WORKFLOW SUMMARY")
    print(f"{'='*80}")
    successful = sum(1 for r in results if r["success"])
    print(f"Total Features: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {len(results) - successful}")
    print(f"{'='*80}\n")
    
    return results

