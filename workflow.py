"""
LangGraph workflow for automated code modification and testing.

This workflow sequences all 5 agents to automate the complete development cycle:
1. Generate test commands
2. Generate code diff
3. Apply code changes
4. Generate unit tests
5. Run tests (with retry logic)
"""
from typing import Dict, List, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from tools import (
    generate_test_commands,
    generate_diff_for_files,
    apply_git_diff,
    generate_unittest,
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
    generated_diff: Optional[str]
    apply_result: Optional[Dict]
    generated_tests: Optional[Dict]
    test_results: Optional[Dict]
    
    # Errors and logs
    errors: Annotated[List[str], add_messages]
    logs: Annotated[List[str], add_messages]
    
    # Final status
    success: bool
    final_message: str


def initialize_state(
    feature_description: str,
    feature_files: List[str],
    base_directory: str = ".",
    max_retries: int = 3
) -> WorkflowState:
    """Initialize the workflow state."""
    return WorkflowState(
        feature_description=feature_description,
        feature_files=feature_files,
        base_directory=base_directory,
        current_step="start",
        retry_count=0,
        max_retries=max_retries,
        test_commands=None,
        generated_diff=None,
        apply_result=None,
        generated_tests=None,
        test_results=None,
        errors=[],
        logs=[],
        success=False,
        final_message=""
    )


def generate_test_commands_node(state: WorkflowState) -> WorkflowState:
    """Node 1: Generate test commands for the project."""
    state["current_step"] = "generate_test_commands"
    state["logs"].append("Step 1: Generating test commands...")
    
    try:
        result = generate_test_commands(directory=state["base_directory"])
        
        if result['success']:
            state["test_commands"] = result
            state["logs"].append(f"✅ Test framework detected: {result['test_framework']}")
        else:
            error = f"Failed to generate test commands: {result.get('error', 'Unknown error')}"
            state["errors"].append(error)
            state["logs"].append(f"❌ {error}")
            
    except Exception as e:
        error = f"Error in generate_test_commands: {str(e)}"
        state["errors"].append(error)
        state["logs"].append(f"❌ {error}")
    
    return state


def generate_diff_node(state: WorkflowState) -> WorkflowState:
    """Node 2: Generate code diff from feature description."""
    state["current_step"] = "generate_diff"
    
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
        
        state["logs"].append(f"🔄 Retry {state['retry_count']}/{state['max_retries']}: Regenerating with error context...")
    else:
        state["logs"].append("Step 2: Generating code diff...")
    
    try:
        result = generate_diff_for_files(
            prompt=prompt,
            file_paths=state["feature_files"],
            base_directory=state["base_directory"]
        )
        
        if result['success']:
            state["generated_diff"] = result['diff']
            state["logs"].append(f"✅ Generated diff for {len(state['feature_files'])} files")
        else:
            error = f"Failed to generate diff: {result.get('error', 'Unknown error')}"
            state["errors"].append(error)
            state["logs"].append(f"❌ {error}")
            
    except Exception as e:
        error = f"Error in generate_diff: {str(e)}"
        state["errors"].append(error)
        state["logs"].append(f"❌ {error}")
    
    return state


def apply_code_change_node(state: WorkflowState) -> WorkflowState:
    """Node 3: Apply the generated diff to the codebase."""
    state["current_step"] = "apply_code_change"
    state["logs"].append("Step 3: Applying code changes...")
    
    if not state["generated_diff"]:
        error = "No diff to apply"
        state["errors"].append(error)
        state["logs"].append(f"❌ {error}")
        return state
    
    try:
        result = apply_git_diff(
            diff_content=state["generated_diff"],
            base_directory=state["base_directory"]
        )
        
        if result['successful_files'] > 0:
            state["apply_result"] = result
            state["logs"].append(f"✅ Modified {result['successful_files']} files successfully")
        else:
            error = f"Failed to apply changes: {result.get('error', 'No files modified')}"
            state["errors"].append(error)
            state["logs"].append(f"❌ {error}")
            
    except Exception as e:
        error = f"Error in apply_code_change: {str(e)}"
        state["errors"].append(error)
        state["logs"].append(f"❌ {error}")
    
    return state


def generate_unittest_node(state: WorkflowState) -> WorkflowState:
    """Node 4: Generate unit tests for the changes."""
    state["current_step"] = "generate_unittest"
    state["logs"].append("Step 4: Generating unit tests...")
    
    try:
        # Generate tests for each modified file
        test_results = []
        
        for file_path in state["feature_files"]:
            test_description = f"""
Generate comprehensive unit tests for the feature: {state['feature_description']}

Test requirements:
- Test all edge cases
- Test error handling
- Test normal operation
- Use appropriate assertions
"""
            
            result = generate_unittest(
                source_file=file_path,
                test_description=test_description,
                base_directory=state["base_directory"]
            )
            
            if result['success']:
                test_results.append(result)
                state["logs"].append(f"✅ Generated tests for {file_path}")
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
    """Node 5: Run the tests and capture results."""
    state["current_step"] = "run_tests"
    state["logs"].append("Step 5: Running unit tests...")
    
    try:
        result = run_tests(
            directory=state["base_directory"],
            with_coverage=True
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
    workflow.add_node("generate_diff", generate_diff_node)
    workflow.add_node("apply_code_change", apply_code_change_node)
    workflow.add_node("generate_unittest", generate_unittest_node)
    workflow.add_node("run_tests", run_tests_node)
    
    # Define the flow
    workflow.set_entry_point("generate_test_commands")
    workflow.add_edge("generate_test_commands", "generate_diff")
    workflow.add_edge("generate_diff", "apply_code_change")
    workflow.add_edge("apply_code_change", "generate_unittest")
    workflow.add_edge("generate_unittest", "run_tests")
    
    # Add conditional edge for retry logic
    workflow.add_conditional_edges(
        "run_tests",
        should_retry,
        {
            "retry": "generate_diff",  # Retry from diff generation
            "end": END
        }
    )
    
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
        feature_name = feature.get("feature", "Unknown feature")
        files_to_modify = feature.get("files_to_modify", [])
        implementation_notes = feature.get("implementation_notes", "")
        
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

