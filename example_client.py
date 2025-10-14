"""
Example script demonstrating how to use the Code Analysis API.
"""
import requests
import json


def analyze_code(
    api_url: str,
    problem_description: str,
    zip_file_path: str
):
    """
    Send a code analysis request to the API.

    Args:
        api_url: Base URL of the API (e.g., 'http://localhost:8000')
        problem_description: Natural language description of features
        zip_file_path: Path to the zip file containing code

    Returns:
        Analysis report as dictionary
    """
    endpoint = f"{api_url}/api/analyze"

    with open(zip_file_path, 'rb') as f:
        files = {'code_zip': f}
        data = {'problem_description': problem_description}

        response = requests.post(endpoint, files=files, data=data)
        response.raise_for_status()

        return response.json()


def main():
    """Example usage."""
    # Configuration
    API_URL = "http://localhost:8000"
    PROBLEM_DESCRIPTION = """
    Implement the following features:
    1. User authentication with login and registration
    2. Create and manage user profiles
    3. Password reset functionality
    """
    ZIP_FILE_PATH = "./sample_code.zip"

    print("Sending code analysis request...")
    print(f"Problem Description: {PROBLEM_DESCRIPTION}")
    print(f"Code Archive: {ZIP_FILE_PATH}")
    print()

    try:
        result = analyze_code(API_URL, PROBLEM_DESCRIPTION, ZIP_FILE_PATH)

        print("Analysis Report:")
        print("=" * 80)
        print(json.dumps(result, indent=2))
        print("=" * 80)

        # Print summary
        print("\nSummary:")
        print(f"Features analyzed: {len(result['feature_analysis'])}")
        print("\nFeatures:")
        for i, feature in enumerate(result['feature_analysis'], 1):
            print(f"\n{i}. {feature['feature_description']}")
            print(f"   Locations: {len(feature['implementation_location'])}")
            for loc in feature['implementation_location']:
                print(f"   - {loc['file']} :: {loc['function']} (lines {loc['lines']})")

        print(f"\nExecution Plan:\n{result['execution_plan_suggestion']}")

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
