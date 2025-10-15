"""
Tools module for code analysis and modification.
"""
from .generate_test_commands import (
    generate_test_commands,
    generate_test_commands_for_file,
    generate_and_save_commands,
    TestCommandGenerationError
)

from .generate_unittest import (
    generate_unittest,
    generate_unittest_for_directory,
    generate_and_save_unittest,
    UnittestGenerationError
)

from .run_unittest import (
    run_tests,
    run_tests_and_save_report,
    run_specific_test,
    extract_test_files_from_result,
    generate_test_commands_for_files,
    TestExecutionError
)

from .code_modifier import (
    modify_code,
    modify_code_with_retry,
    CodeModificationError
)

__all__ = [
    # Generate test commands functions
    'generate_test_commands',
    'generate_test_commands_for_file',
    'generate_and_save_commands',
    'TestCommandGenerationError',
    # Generate unittest functions
    'generate_unittest',
    'generate_unittest_for_directory',
    'generate_and_save_unittest',
    'UnittestGenerationError',
    # Run unittest functions
    'run_tests',
    'run_tests_and_save_report',
    'run_specific_test',
    'extract_test_files_from_result',
    'generate_test_commands_for_files',
    'TestExecutionError',
    # Code modifier functions
    'modify_code',
    'modify_code_with_retry',
    'CodeModificationError'
]

