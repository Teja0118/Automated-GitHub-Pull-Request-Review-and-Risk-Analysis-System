import ast
from typing import Dict


def extract_ast_metrics(code: str) -> Dict[str, int]:
    # AST-based complexity extraction

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {
            "ast_node_count": 0,
            "function_count": 0,
            "class_count": 0,
            "branch_count": 0,
        }

    ast_node_count = 0
    function_count = 0
    class_count = 0
    branch_count = 0

    for node in ast.walk(tree):
        ast_node_count += 1

        if isinstance(node, ast.FunctionDef):
            function_count += 1
        elif isinstance(node, ast.ClassDef):
            class_count += 1
        elif isinstance(node, (ast.If, ast.For, ast.While)):
            branch_count += 1

    return {
        "ast_node_count": ast_node_count,
        "function_count": function_count,
        "class_count": class_count,
        "branch_count": branch_count,
    }
