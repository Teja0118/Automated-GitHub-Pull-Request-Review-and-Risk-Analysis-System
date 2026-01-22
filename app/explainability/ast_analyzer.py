import ast
from typing import List, Dict
from app.ingestion.github_client import GithubClient


class ASTAnalyzer:
    # Performs lightweight AST-based complexity analysis for changed Python files in a pull request.

    def __init__(self, owner: str, repo: str):
        self.owner = owner
        self.repo = repo
        self.github = GithubClient()

    def analyze_pr(self, pr_number: int) -> Dict:
        # Fetch PR files
        files = list(
            self.github.paginate(
                f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/files"
            )
        )

        python_files = [
            f for f in files if f["filename"].endswith(".py")
        ]

        total_functions = 0
        total_classes = 0
        total_branches = 0
        max_nesting_depth = 0

        for file in python_files:
            patch = file.get("patch")
            if not patch:
                continue

            try:
                tree = ast.parse(patch)
            except SyntaxError:
                # Patch may not be valid standalone Python
                continue

            analyzer = _ASTMetricsVisitor()
            analyzer.visit(tree)

            total_functions += analyzer.function_count
            total_classes += analyzer.class_count
            total_branches += analyzer.branch_count
            max_nesting_depth = max(
                max_nesting_depth, analyzer.max_depth
            )

        complexity_flag = self._complexity_level(
            total_functions, total_branches, max_nesting_depth
        )

        return {
            "files_analyzed": len(python_files),
            "total_functions": total_functions,
            "total_classes": total_classes,
            "total_branches": total_branches,
            "max_nesting_depth": max_nesting_depth,
            "complexity_flag": complexity_flag,
        }

    @staticmethod
    def _complexity_level(
        functions: int, branches: int, depth: int
    ) -> str:
        score = functions + branches + depth

        if score >= 25:
            return "HIGH"
        elif score >= 10:
            return "MEDIUM"
        return "LOW"


class _ASTMetricsVisitor(ast.NodeVisitor):
    """
    AST visitor to compute basic complexity metrics.
    """

    def __init__(self):
        self.function_count = 0
        self.class_count = 0
        self.branch_count = 0
        self.current_depth = 0
        self.max_depth = 0

    def generic_visit(self, node):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.Try)):
            self.branch_count += 1
            self.current_depth += 1
            self.max_depth = max(self.max_depth, self.current_depth)
            super().generic_visit(node)
            self.current_depth -= 1
        else:
            super().generic_visit(node)

    def visit_FunctionDef(self, node):
        self.function_count += 1
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.function_count += 1
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.class_count += 1
        self.generic_visit(node)
