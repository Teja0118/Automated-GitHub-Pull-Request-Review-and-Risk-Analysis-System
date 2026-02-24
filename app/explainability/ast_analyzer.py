import ast
import base64
import re
from typing import Dict, Set
from urllib.parse import quote

from app.ingestion.github_client import GithubClient


class ASTAnalyzer:
    def __init__(self, owner: str, repo: str):
        self.owner = owner
        self.repo = repo
        self.github = GithubClient()

    def analyze_pr(self, pr_number: int) -> Dict:
        pr = self.github.get(f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}")
        head_sha = pr["head"]["sha"]

        files = list(
            self.github.paginate(
                f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/files"
            )
        )

        python_files = [
            f
            for f in files
            if f.get("filename", "").endswith(".py") and f.get("status") != "removed"
        ]

        total_functions = 0
        total_classes = 0
        total_branches = 0
        max_nesting_depth = 0
        files_parsed = 0

        for f in python_files:
            patch = f.get("patch")
            if not patch:
                continue

            changed_lines = self._extract_changed_newfile_lines(patch)
            if not changed_lines:
                continue

            source = self._fetch_file_content_at_sha(f["filename"], head_sha)
            if not source:
                continue

            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            files_parsed += 1
            visitor = _DiffAwareASTMetricsVisitor(changed_lines)
            visitor.visit(tree)

            total_functions += visitor.function_count
            total_classes += visitor.class_count
            total_branches += visitor.branch_count
            max_nesting_depth = max(max_nesting_depth, visitor.max_depth)

        complexity_flag = self._complexity_level(
            total_functions, total_branches, max_nesting_depth
        )

        return {
            "files_analyzed": len(python_files),
            "files_parsed": files_parsed,
            "total_functions": total_functions,
            "total_classes": total_classes,
            "total_branches": total_branches,
            "max_nesting_depth": max_nesting_depth,
            "complexity_flag": complexity_flag,
        }

    def _fetch_file_content_at_sha(self, path: str, sha: str) -> str | None:
        encoded_path = quote(path, safe="/")
        data = self.github.get(
            f"/repos/{self.owner}/{self.repo}/contents/{encoded_path}",
            params={"ref": sha},
        )

        if isinstance(data, list):
            return None

        if data.get("encoding") != "base64" or "content" not in data:
            return None

        try:
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        except Exception:
            return None

    def _extract_changed_newfile_lines(self, patch: str) -> Set[int]:
        changed: Set[int] = set()
        new_line = 0

        for line in patch.splitlines():
            if line.startswith("@@"):
                # Example: @@ -10,5 +20,7 @@
                m = re.search(r"\+(\d+)(?:,(\d+))?", line)
                if not m:
                    continue
                new_line = int(m.group(1))
                continue

            if line.startswith("+") and not line.startswith("+++"):
                changed.add(new_line)
                new_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                # deletion only affects old file line numbers
                continue
            else:
                # context line
                new_line += 1

        return changed

    @staticmethod
    def _complexity_level(functions: int, branches: int, depth: int) -> str:
        score = functions + branches + depth
        if score >= 25:
            return "HIGH"
        if score >= 10:
            return "MEDIUM"
        return "LOW"


class _DiffAwareASTMetricsVisitor(ast.NodeVisitor):
    def __init__(self, changed_lines: Set[int]):
        self.changed_lines = changed_lines
        self.function_count = 0
        self.class_count = 0
        self.branch_count = 0
        self.current_depth = 0
        self.max_depth = 0

    def _node_touches_changed_lines(self, node: ast.AST) -> bool:
        start = getattr(node, "lineno", None)
        if start is None:
            return False
        end = getattr(node, "end_lineno", start)
        return any(start <= ln <= end for ln in self.changed_lines)

    def generic_visit(self, node):
        is_branch = isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.Match))

        if is_branch:
            self.current_depth += 1
            if self._node_touches_changed_lines(node):
                self.branch_count += 1
                self.max_depth = max(self.max_depth, self.current_depth)

            super().generic_visit(node)
            self.current_depth -= 1
        else:
            super().generic_visit(node)

    def visit_FunctionDef(self, node):
        if self._node_touches_changed_lines(node):
            self.function_count += 1
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        if self._node_touches_changed_lines(node):
            self.function_count += 1
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        if self._node_touches_changed_lines(node):
            self.class_count += 1
        self.generic_visit(node)
