"""
Code analysis agent using Gemini CLI.
"""
import json
import os
import subprocess
from typing import Dict, List, Optional

from config import Settings
from models import AnalysisReport
from utils import get_code_files, get_project_structure, extract_code_context

from dotenv import load_dotenv

load_dotenv()

class CodeAnalysisAgent:
    """Agent for analyzing code and generating feature location reports."""

    def __init__(self, settings: Settings):
        """
        Initialize the code analysis agent.

        Args:
            settings: Application settings
        """
        self.settings = settings

    def _call_gemini(self, prompt: str, cwd: Optional[str] = None) -> str:
        """
        Call gemini-cli with a prompt and return the JSON response.

        Args:
            prompt: The prompt to send to Gemini
            cwd: Current working directory to execute gemini from (optional)

        Returns:
            JSON response as string (extracted from gemini-cli wrapper)
        """
        try:
            result = subprocess.run(
                ['gemini', '-p', prompt, '--output-format', 'json'],
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout
                cwd=cwd  # Execute in the specified directory
            )

            if result.returncode != 0:
                raise RuntimeError(f"Gemini CLI error: {result.stderr}")

            # Parse the gemini-cli JSON wrapper
            gemini_output = json.loads(result.stdout.strip())
            response_text = gemini_output.get('response', '')
            print(f"Gemini CLI response: {response_text}")
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
            print(f"Gemini CLI final response: {response_text}")
            return response_text

        except subprocess.TimeoutExpired:
            raise RuntimeError("Gemini CLI request timed out")
        except FileNotFoundError:
            raise RuntimeError("gemini-cli not found. Please ensure it's installed and in PATH")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse Gemini CLI output: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error calling Gemini CLI: {str(e)}")

    def analyze_codebase(
        self,
        problem_description: str,
        code_directory: str
    ) -> AnalysisReport:
        """
        Analyze a codebase and generate a feature location report.

        Args:
            problem_description: Natural language description of features
            code_directory: Path to the extracted code directory

        Returns:
            AnalysisReport containing feature analysis
        """
        # Step 1: Get project structure
        project_structure = get_project_structure(code_directory)

        # Step 2: Get all code files
        code_files = get_code_files(code_directory)

        # Step 3: Identify key files using LLM
        key_files = self._identify_key_files(
            problem_description,
            project_structure,
            code_files,
            code_directory
        )

        # Step 4: Analyze key files for feature implementation
        analysis = self._analyze_features(
            problem_description,
            key_files,
            code_directory
        )

        # Step 5: Generate execution plan
        execution_plan = self._generate_execution_plan(code_directory)

        return AnalysisReport(
            project_structure=project_structure,
            feature_analysis=analysis,
            execution_plan_suggestion=execution_plan
        )

    def _identify_key_files(
        self,
        problem_description: str,
        project_structure: str,
        code_files: List[str],
        base_directory: str
    ) -> List[str]:
        """
        Identify key files relevant to the problem description.

        Args:
            problem_description: Natural language description
            project_structure: Text representation of project structure
            code_files: List of all code files
            base_directory: Base directory path

        Returns:
            List of key file paths
        """
        # Limit the number of files to analyze
        max_files = 30
        if len(code_files) > max_files:
            # Prioritize certain file types and names
            priority_patterns = [
                'controller', 'resolver', 'service', 'handler', 'route',
                'api', 'endpoint', 'model', 'schema', 'repository'
            ]

            def file_priority(filepath: str) -> int:
                filename = os.path.basename(filepath).lower()
                for i, pattern in enumerate(priority_patterns):
                    if pattern in filename:
                        return i
                return len(priority_patterns)

            code_files = sorted(code_files, key=file_priority)[:max_files]

        # Get relative paths
        relative_files = [
            os.path.relpath(f, base_directory) for f in code_files
        ]

        prompt = f"""Given a software project with the following structure:

{project_structure}

And these code files:
{chr(10).join(relative_files[:50])}

The project needs to implement these features:
{problem_description}

Identify the 10-15 most relevant files that would contain the implementation of these features.
Focus on files that would contain:
- API endpoints/routes
- Service/business logic
- Controllers/Resolvers
- Data models

Return ONLY a JSON array of file paths, nothing else. Example format:
["src/api/users.ts", "src/services/auth.service.ts"]
"""

        response_text = self._call_gemini(prompt, cwd=base_directory)

        # Parse the JSON response
        try:
            # Extract JSON array from response
            start = response_text.find('[')
            end = response_text.rfind(']') + 1
            if start != -1 and end > start:
                json_str = response_text[start:end]
                selected_files = json.loads(json_str)

                # Convert back to absolute paths
                key_files = []
                for rel_path in selected_files:
                    abs_path = os.path.join(base_directory, rel_path)
                    if os.path.exists(abs_path):
                        key_files.append(abs_path)

                return key_files[:15]  # Limit to 15 files
        except json.JSONDecodeError:
            pass

        # Fallback: return first 15 files
        return code_files[:15]

    def _analyze_features(
        self,
        problem_description: str,
        key_files: List[str],
        base_directory: str
    ) -> List[Dict]:
        """
        Analyze key files to locate feature implementations.

        Args:
            problem_description: Natural language description
            key_files: List of key file paths
            base_directory: Base directory path

        Returns:
            List of feature analysis dictionaries
        """
        # Build context from key files
        file_contents = []
        for file_path in key_files:
            rel_path = os.path.relpath(file_path, base_directory)
            content = extract_code_context(file_path, max_lines=200)
            file_contents.append(f"=== File: {rel_path} ===\n{content}\n")

        combined_context = "\n".join(file_contents)

        prompt = f"""You are a code analysis expert. Analyze the following codebase to identify where specific features are implemented.

PROJECT FEATURES TO IMPLEMENT:
{problem_description}

CODEBASE CONTENTS:
{combined_context}

TASK:
For each feature mentioned in the problem description, identify:
1. Which files contain the implementation
2. Which functions/methods implement the feature
3. The line numbers where the implementation occurs

Return your analysis as a JSON object with this EXACT structure:
{{
  "feature_analysis": [
    {{
      "feature_description": "Brief description of the feature",
      "implementation_location": [
        {{
          "file": "relative/path/to/file.ts",
          "function": "functionName",
          "lines": "start-end"
        }}
      ]
    }}
  ]
}}

IMPORTANT:
- Be precise about line numbers based on the code shown
- Include the most relevant functions for each feature
- Use relative file paths
- If a feature spans multiple files, include all relevant locations
- Feature descriptions should be clear and concise

Return ONLY valid JSON, no additional text.
"""

        response_text = self._call_gemini(prompt, cwd=base_directory)

        # Parse JSON response
        try:
            # Extract JSON from response
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start != -1 and end > start:
                json_str = response_text[start:end]
                analysis_data = json.loads(json_str)
                return analysis_data.get("feature_analysis", [])
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            print(f"Response: {response_text}")

        # Fallback: return empty analysis
        return []

    def _generate_execution_plan(self, code_directory: str) -> str:
        """
        Generate suggestions for running the project.

        Args:
            code_directory: Path to code directory

        Returns:
            Execution plan as string
        """
        # Check for common configuration files
        config_files_to_check = [
            'package.json',
            'requirements.txt',
            'Pipfile',
            'pom.xml',
            'build.gradle',
            'Cargo.toml',
            'go.mod',
            'Gemfile',
            'composer.json'
        ]

        found_configs = []
        for config_file in config_files_to_check:
            config_path = os.path.join(code_directory, config_file)
            if os.path.exists(config_path):
                found_configs.append(config_file)

        # Generate execution suggestions based on found files
        if 'package.json' in found_configs:
            try:
                with open(os.path.join(code_directory, 'package.json'), 'r') as f:
                    package_data = json.load(f)
                    scripts = package_data.get('scripts', {})

                    suggestions = "To run this project:\n"
                    suggestions += "1. Install dependencies: `npm install` or `yarn install`\n"

                    if 'start' in scripts:
                        suggestions += "2. Start the application: `npm start` or `yarn start`\n"
                    if 'dev' in scripts or 'start:dev' in scripts:
                        dev_cmd = 'dev' if 'dev' in scripts else 'start:dev'
                        suggestions += f"2. Start in development mode: `npm run {dev_cmd}` or `yarn {dev_cmd}`\n"
                    if 'build' in scripts:
                        suggestions += "3. Build the project: `npm run build` or `yarn build`\n"

                    return suggestions
            except Exception:
                pass

        if 'requirements.txt' in found_configs or 'Pipfile' in found_configs:
            suggestions = "To run this Python project:\n"
            if 'requirements.txt' in found_configs:
                suggestions += "1. Install dependencies: `pip install -r requirements.txt`\n"
            else:
                suggestions += "1. Install dependencies: `pipenv install`\n"
            suggestions += "2. Run the application (check for main.py or app.py)\n"
            return suggestions

        # Generic fallback
        return "Check the project's README.md or documentation for specific instructions on building and running the project."
