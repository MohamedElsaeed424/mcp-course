#!/usr/bin/env python3
"""
Module 1: Basic MCP Server - Starter Code (fixed)
Implements tools for analyzing git changes and suggesting PR templates.
"""

import os
import json
import subprocess
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Initialize the FastMCP server
mcp = FastMCP("pr-agent")

# PR template directory (shared across all modules)
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"

# default PR templates
DEFAULT_TEMPLATES = {
    "bug.md": "Bug Fix",
    "feature.md": "Feature",
    "docs.md": "Documentation",
    "refactor.md": "Refactor",
    "test.md": "Test",
    "performance.md": "Performance",
    "security.md": "Security",
}


TYPE_MAPPING = {
    "bug": "bug.md",
    "fix": "bug.md",
    "feature": "feature.md",
    "enhancement": "feature.md",
    "docs": "docs.md",
    "documentation": "docs.md",
    "refactor": "refactor.md",
    "cleanup": "refactor.md",
    "test": "test.md",
    "testing": "test.md",
    "performance": "performance.md",
    "optimization": "performance.md",
    "security": "security.md",
}


@mcp.tool()
async def analyze_file_changes(
    base_branch: str = "main",
    include_diff: bool = True,
    max_diff_lines: int = 500,
    working_directory: Optional[str] = None,
) -> str:
    """Get the full diff and list of changed files in the current git repository.

    Args:
        base_branch: Base branch to compare against (default: main)
        include_diff: Include the full diff content (default: True)
        max_diff_lines: Truncate diff output after this many lines (default: 500)
        working_directory: Repository path to run git commands in (defaults to current working dir or MCP root)
    """
    try:
        if working_directory is None:
            try:
                context = mcp.get_context()
                roots_result = await context.session.list_roots()
                root = roots_result.roots[0]
                working_directory = root.uri.path
            except Exception:
                pass

        cwd = working_directory if working_directory else os.getcwd()

        # 1) Get list of changed files
        files_result = subprocess.run(
            ["git", "diff", "--name-status", f"{base_branch}...HEAD"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )

        # 2) Get diff statistics
        stat_result = subprocess.run(
            ["git", "diff", "--stat", f"{base_branch}...HEAD"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )

        # 3) Optional full diff
        diff_content = ""
        truncated = False
        total_diff_lines = 0
        if include_diff:
            diff_result = subprocess.run(
                ["git", "diff", f"{base_branch}...HEAD"],
                capture_output=True,
                text=True,
                cwd=cwd,
            )
            diff_lines = diff_result.stdout.splitlines()
            total_diff_lines = len(diff_lines)
            if total_diff_lines > max_diff_lines:
                diff_content = "\n".join(diff_lines[:max_diff_lines])
                diff_content += (
                    f"\n\n... Output truncated. Showing {max_diff_lines} of {total_diff_lines} lines ..."
                    "\n... Use max_diff_lines parameter to see more ..."
                )
                truncated = True
            else:
                diff_content = diff_result.stdout

        # 4) Get commit messages for context
        commits_result = subprocess.run(
            ["git", "log", "--oneline", f"{base_branch}..HEAD"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )

        analysis = {
            "base_branch": base_branch,
            "files_changed": files_result.stdout,
            "statistics": stat_result.stdout,
            "commits": commits_result.stdout,
            "diff": diff_content if include_diff else "Diff not included (set include_diff=true to see full diff)",
            "truncated": truncated,
            "total_diff_lines": total_diff_lines,
            "_debug": {"cwd": cwd},
        }

        return json.dumps(analysis, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_pr_templates() -> str:
    """List available PR templates with their content."""
    templates = []
    for filename, template_type in DEFAULT_TEMPLATES.items():
        path = TEMPLATES_DIR / filename
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            content = ""
        templates.append(
            {
                "filename": filename,
                "type": template_type,
                "content": content,
            }
        )
    return json.dumps(templates, indent=2)


@mcp.tool()
async def suggest_template(changes_summary: str, change_type: str) -> str:
    """Analyze the changes and suggest the most appropriate PR template.

    Args:
        changes_summary: Your analysis of what the changes do
        change_type: The type of change you've identified (bug, feature, docs, refactor, test, etc.)
    """
    templates = json.loads(await get_pr_templates())

    template_file = TYPE_MAPPING.get(change_type.lower().strip(), "feature.md")
    selected_template = next(
        (t for t in templates if t["filename"] == template_file),
        templates[0], 
    )

    suggestion = {
        "recommended_template": selected_template,
        "reasoning": f"Based on your analysis: '{changes_summary}', this appears to be a {change_type} change.",
        "template_content": selected_template["content"],
        "usage_hint": "Claude can help you fill out this template based on the specific changes in your PR.",
    }

    return json.dumps(suggestion, indent=2)


if __name__ == "__main__":
    mcp.run()
