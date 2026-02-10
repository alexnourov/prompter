"""End-to-end tests for Prompter.

These tests require the real Claude CLI to be installed and available.
Run with: pytest tests/test_e2e.py -v -m e2e

Test cases:
- TC-04: Full development cycle with .adoc format
- TC-19: Full development cycle with .md format
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.e2e
def test_full_cycle(tmp_path):
    """TC-04: Full development cycle using real Claude CLI with .adoc format.

    Requirements:
    - ORC-01: Full orchestration from prompts to execution
    - End-to-end verification with real Claude CLI
    - Uses specs/test_prompts.adoc (tstutil utility prompts)

    Test approach:
    - Skip if claude CLI is not available
    - Run prompter with specs/test_prompts.adoc
    - Verify src/tstutil/cli.py is created
    - Verify report.json contains successful results
    - Verify no permission denials in logs
    """
    # Check if claude CLI is available
    if shutil.which("claude") is None:
        pytest.skip("claude CLI not found in PATH")

    # Verify test_prompts.adoc exists
    test_prompts = Path("specs/test_prompts.adoc")
    if not test_prompts.exists():
        pytest.skip(f"{test_prompts} not found")

    # Setup output paths
    output_report = tmp_path / "report.json"
    log_file = tmp_path / "prompter.log"

    # Expected output file from tstutil prompts
    expected_output = Path("src/tstutil/cli.py")

    # Clean up any existing output from previous runs
    if expected_output.exists():
        expected_output.unlink()
    if expected_output.parent.exists():
        import shutil as sh
        sh.rmtree(expected_output.parent)

    # Run prompter with real claude CLI
    result = subprocess.run(
        [
            "poetry", "run", "python", "-m", "prompter",
            str(test_prompts),
            "-o", str(output_report)
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=600  # 10 minutes for full E2E test
    )

    # Verify exit code
    assert result.returncode == 0, (
        f"Prompter exited with code {result.returncode}.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    # Verify src/tstutil/cli.py was created
    assert expected_output.exists(), (
        f"Expected output file {expected_output} not created"
    )

    # Verify report.json exists and is valid
    assert output_report.exists(), "report.json not created"

    with open(output_report, encoding="utf-8") as f:
        report_data = json.load(f)

    # Verify report structure
    assert isinstance(report_data, list), "Report should be a JSON array"
    assert len(report_data) > 0, "Report should contain at least one result"

    # Verify all prompts succeeded
    for i, result_entry in enumerate(report_data):
        assert "status" in result_entry, f"Result {i} missing 'status' field"
        assert result_entry["status"] == "success", (
            f"Result {i} failed with status '{result_entry['status']}': "
            f"{result_entry.get('error', 'No error message')}"
        )
        assert "prompt" in result_entry, f"Result {i} missing 'prompt' field"
        assert "timestamp" in result_entry, f"Result {i} missing 'timestamp' field"
        assert "claude_response" in result_entry, f"Result {i} missing 'claude_response' field"

    # Verify no permission denials in logs (if log file exists in default location)
    default_log = Path.cwd() / "prompter.log"
    if default_log.exists():
        log_content = default_log.read_text()
        assert "permission_denials" not in log_content.lower(), (
            "Found permission denials in log file"
        )


@pytest.mark.e2e
def test_full_cycle_md(tmp_path):
    """TC-19: Full development cycle using real Claude CLI with .md format.

    Requirements:
    - ORC-01: Full orchestration from prompts to execution
    - INP-01: Support for .md format with --- separator
    - End-to-end verification with real Claude CLI

    Test approach:
    - Skip if claude CLI is not available
    - Run prompter with specs/test_prompts.md
    - Verify src/tstutil/cli.py is created
    - Verify report.json contains successful results
    - Verify exit code is 0
    """
    # Check if claude CLI is available
    if shutil.which("claude") is None:
        pytest.skip("claude CLI not found in PATH")

    # Verify test_prompts.md exists
    test_prompts = Path("specs/test_prompts.md")
    if not test_prompts.exists():
        pytest.skip(f"{test_prompts} not found")

    # Setup output paths
    output_report = tmp_path / "report-md.json"

    # Expected output file from tstutil prompts
    expected_output = Path("src/tstutil/cli.py")

    # Clean up any existing output from previous runs
    if expected_output.exists():
        expected_output.unlink()
    if expected_output.parent.exists():
        import shutil as sh
        sh.rmtree(expected_output.parent)

    # Run prompter with real claude CLI
    result = subprocess.run(
        [
            "poetry", "run", "python", "-m", "prompter",
            str(test_prompts),
            "-o", str(output_report)
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=600  # 10 minutes for full E2E test
    )

    # Verify exit code is 0
    assert result.returncode == 0, (
        f"Prompter exited with code {result.returncode}.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    # Verify src/tstutil/cli.py was created
    assert expected_output.exists(), (
        f"Expected output file {expected_output} not created"
    )

    # Verify report.json exists and is valid
    assert output_report.exists(), "report.json not created"

    with open(output_report, encoding="utf-8") as f:
        report_data = json.load(f)

    # Verify report structure
    assert isinstance(report_data, list), "Report should be a JSON array"
    assert len(report_data) > 0, "Report should contain at least one result"

    # Verify all prompts succeeded
    for i, result_entry in enumerate(report_data):
        assert "status" in result_entry, f"Result {i} missing 'status' field"
        assert result_entry["status"] == "success", (
            f"Result {i} failed with status '{result_entry['status']}': "
            f"{result_entry.get('error', 'No error message')}"
        )

    # Verify report has expected number of results
    # (both test_prompts.adoc and test_prompts.md should have same prompts)
    assert len(report_data) >= 3, (
        f"Expected at least 3 prompts in report, got {len(report_data)}"
    )
