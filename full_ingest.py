#!/usr/bin/env python3
"""Full ingestion pipeline — runs ingest → embed → graph sequentially.

Usage:
    python full_ingest.py
    python full_ingest.py --path CustomDocuments/    # override default ingest path

All three steps run to completion before moving to the next. Safe to leave running overnight.
Logs timestamps and progress to console and to full_ingest.log.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def log(message: str, level: str = "INFO") -> None:
    """Print and log a timestamped message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [{level}] {message}"
    print(formatted)
    with open("full_ingest.log", "a", encoding="utf-8") as f:
        f.write(formatted + "\n")


def run_step(step_name: str, command: list[str]) -> bool:
    """Run a single step and return True if successful, False otherwise.

    Args:
        step_name: Human-readable name for logging.
        command: Command list to pass to subprocess.run().

    Returns:
        True if exit code 0, False otherwise.
    """
    log(f"{'='*70}")
    log(f"Starting: {step_name}", level="STEP")
    log(f"Command: {' '.join(command)}")
    log(f"{'='*70}")

    start_time = time.time()

    try:
        result = subprocess.run(command, check=False, text=True)
        elapsed = time.time() - start_time

        if result.returncode == 0:
            log(f"✓ {step_name} completed successfully in {elapsed:.1f}s", level="SUCCESS")
            return True
        else:
            log(
                f"✗ {step_name} FAILED with exit code {result.returncode} "
                f"(elapsed: {elapsed:.1f}s)",
                level="ERROR",
            )
            return False

    except Exception as exc:
        elapsed = time.time() - start_time
        log(f"✗ {step_name} FAILED with exception: {exc} (elapsed: {elapsed:.1f}s)", level="ERROR")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Run full ingestion pipeline (ingest → embed → graph) sequentially."
    )
    parser.add_argument(
        "--path",
        type=str,
        default="Ingest_Documents/",
        help="Path to documents folder for ingest step (default: Ingest_Documents/)",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Skip ingest step (default: False)",
    )
    parser.add_argument(
        "--skip-embed",
        action="store_true",
        help="Skip embed step (default: False)",
    )
    parser.add_argument(
        "--skip-graph",
        action="store_true",
        help="Skip graph step (default: False)",
    )

    args = parser.parse_args()

    log("="*70, level="START")
    log("Full Ingestion Pipeline Started", level="START")
    log(f"Ingest path: {args.path}", level="INFO")
    log("="*70, level="START")

    all_success = True
    pipeline_start = time.time()

    # Step 1: Ingest
    if not args.skip_ingest:
        success = run_step(
            "INGEST",
            ["python", "src/main.py", "ingest", "--path", args.path],
        )
        all_success = all_success and success
        if not success:
            log("Ingest failed. Stopping pipeline.", level="ERROR")
            return 1
    else:
        log("Skipping ingest step.", level="INFO")

    # Step 2: Embed
    if not args.skip_embed:
        success = run_step("EMBED", ["python", "src/main.py", "embed"])
        all_success = all_success and success
        if not success:
            log("Embed failed. Stopping pipeline.", level="ERROR")
            return 1
    else:
        log("Skipping embed step.", level="INFO")

    # Step 3: Graph
    if not args.skip_graph:
        success = run_step("GRAPH", ["python", "src/main.py", "graph"])
        all_success = all_success and success
        if not success:
            log("Graph failed. Stopping pipeline.", level="ERROR")
            return 1
    else:
        log("Skipping graph step.", level="INFO")

    # Summary
    total_elapsed = time.time() - pipeline_start
    log("="*70, level="END")
    if all_success:
        log(
            f"✓ Full ingestion pipeline completed successfully in {total_elapsed:.1f}s",
            level="SUCCESS",
        )
        log("="*70, level="END")
        return 0
    else:
        log(f"✗ Full ingestion pipeline FAILED after {total_elapsed:.1f}s", level="ERROR")
        log("="*70, level="END")
        return 1


if __name__ == "__main__":
    sys.exit(main())
