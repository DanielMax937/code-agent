"""
Tools module for code analysis and modification.
"""
from .apply_code_change import (
    apply_git_diff,
    apply_diff_from_file,
    parse_git_diff,
    DiffParseError,
    DiffApplyError,
    FileDiff,
    DiffHunk
)

from .generate_diff import (
    generate_diff,
    generate_diff_for_files,
    generate_diff_for_directory,
    generate_and_save_diff,
    DiffGenerationError
)

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
    # Apply diff functions
    'apply_git_diff',
    'apply_diff_from_file',
    'parse_git_diff',
    'DiffParseError',
    'DiffApplyError',
    'FileDiff',
    'DiffHunk',
    # Generate diff functions
    'generate_diff',
    'generate_diff_for_files',
    'generate_diff_for_directory',
    'generate_and_save_diff',
    'DiffGenerationError',
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

