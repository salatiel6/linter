import ast

from pathlib import Path
from typing import List

from src.logger import logger


def load_linter_ignore(ignore_file: str = ".linterignore") -> List[Path]:
    """
    Reads `.linterignore` and returns a list of ignored files/directories.

    :param ignore_file: The filename to look for ignored paths.
    :return: A list of file paths to ignore.
    """
    ignore_paths = []
    ignore_path = Path(ignore_file)

    if ignore_path.exists():
        with open(ignore_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):  # Ignore empty lines and comments
                    full_path = Path(stripped).resolve()
                    ignore_paths.append(full_path)

    return ignore_paths


def find_python_files(root_dir: Path, ignored_paths: List[Path]) -> List[Path]:
    """
    Recursively finds all Python files in the given directory while ignoring specified paths.

    :param root_dir: The root directory to search.
    :param ignored_paths: A list of paths to ignore.
    :return: A list of paths to `.py` files.
    """
    python_files = []
    for file in root_dir.rglob("*.py"):
        resolved_path = file.resolve()

        # Check if the file is in an ignored directory
        if any(resolved_path.is_relative_to(ignore) for ignore in ignored_paths):
            continue

        python_files.append(resolved_path)

    return python_files


def check_import_order(file_path: Path) -> List[str]:
    """
    Checks if imports follow the order: stdlib -> third party -> local imports.
    Each section should be alphabetically ordered and separated by a blank line.

    :param file_path: Path to the Python file to check
    :return: List of error messages
    """
    LOCAL_PACKAGES = {}

    with open(file_path, "r", encoding="utf-8") as file:
        tree = ast.parse(file.read(), filename=str(file_path))

    direct_imports = []
    third_party_from_imports = []
    local_from_imports = []
    errors = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            direct_imports.append((node.lineno, ast.unparse(node)))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module_name = node.module.split('.')[0]
                if module_name in LOCAL_PACKAGES:
                    local_from_imports.append((node.lineno, ast.unparse(node)))
                else:
                    third_party_from_imports.append((node.lineno, ast.unparse(node)))

    # Check ordering within sections
    if direct_imports and sorted(direct_imports, key=lambda x: x[1]) != direct_imports:
        errors.append(f"{file_path}:1 - Direct imports are not alphabetically ordered")

    if third_party_from_imports and sorted(third_party_from_imports, key=lambda x: x[1]) != third_party_from_imports:
        errors.append(f"{file_path}:1 - Third-party from-imports are not alphabetically ordered")

    if local_from_imports and sorted(local_from_imports, key=lambda x: x[1]) != local_from_imports:
        errors.append(f"{file_path}:1 - Local from-imports are not alphabetically ordered")

    # Check section ordering
    if direct_imports and third_party_from_imports:
        last_direct = max(x[0] for x in direct_imports)
        first_third_party = min(x[0] for x in third_party_from_imports)
        if first_third_party < last_direct:
            errors.append(f"{file_path}:1 - Third-party from-imports must come after direct imports")

    if third_party_from_imports and local_from_imports:
        last_third_party = max(x[0] for x in third_party_from_imports)
        first_local = min(x[0] for x in local_from_imports)
        if first_local < last_third_party:
            errors.append(f"{file_path}:1 - Local from-imports must come after third-party from-imports")

    return errors


def check_docstrings_and_type_hints(file_path: Path) -> List[str]:
    """
    Checks if all classes, methods, and functions in a file have docstrings and type hints.

    :param file_path: The Python file to inspect.
    :return: A list of missing docstrings or type hints.
    """
    issues_ = []

    with open(file_path, "r", encoding="utf-8") as file:
        tree = ast.parse(file.read(), filename=str(file_path))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            line = node.lineno
            name = node.name

            # Check for missing docstrings
            if not ast.get_docstring(node):
                issues_.append(f"{file_path}:{line} - Missing docstring: Function: {name}")

            # Check for missing type hints (ignoring self and cls)
            if not node.returns or any(
                    arg.annotation is None for arg in node.args.args if arg.arg not in {"self", "cls"}
            ):
                issues_.append(f"{file_path}:{line} - Missing type hints: Function: {name}")

        if isinstance(node, ast.ClassDef):
            for method in node.body:
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    line = method.lineno
                    method_name = method.name

                    # Check for missing docstrings
                    if not ast.get_docstring(method):
                        issues_.append(f"{file_path}:{line} - Missing docstring: Method: {node.name}.{method_name}")

                    # Check for missing type hints (ignoring self and cls)
                    if not method.returns or any(
                            arg.annotation is None for arg in method.args.args if arg.arg not in {"self", "cls"}
                    ):
                        issues_.append(f"{file_path}:{line} - Missing type hints: Method: {node.name}.{method_name}")

    return issues_


if __name__ == "__main__":
    root_dir = Path.cwd()  # Current working directory
    ignored_paths = load_linter_ignore()
    python_files = find_python_files(root_dir, ignored_paths)

    all_issues_resolved = True  # Flag to track if all issues are resolved

    for file in python_files:

        # Check for import order issues
        import_issues = check_import_order(file)
        for issue in import_issues:
            print(issue)
            all_issues_resolved = False

        # Check for missing docstrings and type hints
        docstring_issues = check_docstrings_and_type_hints(file)
        for issue in docstring_issues:
            print(issue)
            all_issues_resolved = False

    # Final status
    if all_issues_resolved:
        logger.info("All Python files passed checks with correct imports, docstrings, and type hints.")
