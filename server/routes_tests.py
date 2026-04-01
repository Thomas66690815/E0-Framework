"""REST routes for test/explore file discovery and execution.

Provides endpoints to list all test_*.py and explore_*.py files
from e0_controller/ and run them individually via pytest subprocess.

C86.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/tests", tags=["tests"])

# Resolve e0_controller directory relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONTROLLER_DIR = _PROJECT_ROOT / "e0_controller"
_SERVER_DIR = _PROJECT_ROOT / "server"


# ── Models ───────────────────────────────────────────────

class TestFileInfo(BaseModel):
    name: str
    path: str
    category: str           # "test" | "explore"
    docstring: Optional[str] = None


class TestResult(BaseModel):
    name: str
    passed: int
    failed: int
    errors: int
    skipped: int
    total: int
    duration: float         # seconds
    success: bool
    output: str             # captured stdout/stderr (truncated)
    items: List[dict]       # individual test results


# ── Discovery ────────────────────────────────────────────

def _extract_docstring(filepath: Path) -> Optional[str]:
    """Extract the module-level docstring (first triple-quoted string)."""
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
        # Quick parse: find first triple-quote block
        for delim in ('"""', "'''"):
            idx = text.find(delim)
            if idx != -1:
                end = text.find(delim, idx + 3)
                if end != -1:
                    doc = text[idx + 3:end].strip()
                    # Return first line only
                    return doc.split("\n")[0].strip()
    except Exception:
        pass
    return None


def _discover_files() -> List[TestFileInfo]:
    """Find all test_*.py and explore_*.py files."""
    files = []

    for pattern, category in [("test_*.py", "test"), ("explore_*.py", "explore")]:
        for p in sorted(_CONTROLLER_DIR.glob(pattern)):
            files.append(TestFileInfo(
                name=p.stem,
                path=f"e0_controller/{p.name}",
                category=category,
                docstring=_extract_docstring(p),
            ))

    # Also include server tests
    for p in sorted(_SERVER_DIR.glob("test_*.py")):
        files.append(TestFileInfo(
            name=p.stem,
            path=f"server/{p.name}",
            category="test",
            docstring=_extract_docstring(p),
        ))

    return files


# ── Execution ────────────────────────────────────────────

def _run_pytest(filepath: str) -> TestResult:
    """Run pytest on a single file and parse results."""
    abs_path = _PROJECT_ROOT / filepath
    if not abs_path.is_file():
        raise FileNotFoundError(f"File not found: {filepath}")

    # Use JSON report via --tb=short and parse output
    start = time.time()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(abs_path),
         "--tb=short", "-q", "--no-header"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(_PROJECT_ROOT),
    )
    duration = time.time() - start

    stdout = result.stdout
    stderr = result.stderr

    # Parse the summary line: "N passed, M failed, K error in Xs"
    passed = failed = errors = skipped = 0
    import re
    summary_match = re.search(
        r"(\d+)\s+passed", stdout
    )
    if summary_match:
        passed = int(summary_match.group(1))
    fail_match = re.search(r"(\d+)\s+failed", stdout)
    if fail_match:
        failed = int(fail_match.group(1))
    err_match = re.search(r"(\d+)\s+error", stdout)
    if err_match:
        errors = int(err_match.group(1))
    skip_match = re.search(r"(\d+)\s+skipped", stdout)
    if skip_match:
        skipped = int(skip_match.group(1))

    total = passed + failed + errors + skipped

    # Parse individual test lines: "PASSED", "FAILED", etc.
    items = []
    for line in stdout.splitlines():
        # Lines like: "test_something.py::TestClass::test_method PASSED"
        if " PASSED" in line or " FAILED" in line or " ERROR" in line or " SKIPPED" in line:
            parts = line.rsplit(" ", 1)
            if len(parts) == 2:
                test_id = parts[0].strip()
                status = parts[1].strip()
                items.append({"test": test_id, "status": status.lower()})

    # If no individual items parsed (quiet mode), try to get from verbose run
    # For -q mode, we get dots/F/E — parse differently
    if not items and total > 0:
        # Rerun with -v if we need individual items (only for small files)
        if total <= 200:
            verbose_result = subprocess.run(
                [sys.executable, "-m", "pytest", str(abs_path),
                 "-v", "--tb=no", "--no-header"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(_PROJECT_ROOT),
            )
            for line in verbose_result.stdout.splitlines():
                if " PASSED" in line or " FAILED" in line or " ERROR" in line or " SKIPPED" in line:
                    parts = line.rsplit(" ", 1)
                    if len(parts) == 2:
                        test_name = parts[0].strip()
                        status = parts[1].strip()
                        items.append({"test": test_name, "status": status.lower()})

    # Truncate output to avoid huge payloads
    combined = stdout + ("\n--- STDERR ---\n" + stderr if stderr.strip() else "")
    if len(combined) > 10000:
        combined = combined[:10000] + "\n... (truncated)"

    return TestResult(
        name=Path(filepath).stem,
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
        total=total,
        duration=round(duration, 2),
        success=(failed == 0 and errors == 0),
        output=combined,
        items=items,
    )


# ── Endpoints ────────────────────────────────────────────

@router.get("", response_model=List[TestFileInfo])
def list_tests():
    """Discover all test and explore files."""
    return _discover_files()


@router.post("/{name}/run", response_model=TestResult)
def run_test(name: str):
    """Run a specific test or explore file and return results."""
    files = _discover_files()
    match = next((f for f in files if f.name == name), None)
    if match is None:
        raise HTTPException(404, f"Test file {name!r} not found")

    try:
        return _run_pytest(match.path)
    except subprocess.TimeoutExpired:
        raise HTTPException(408, f"Test {name!r} timed out after 120s")
    except Exception as exc:
        raise HTTPException(500, f"Error running {name!r}: {exc}")
