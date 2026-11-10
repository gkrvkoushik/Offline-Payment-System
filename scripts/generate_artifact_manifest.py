"""Generate authoritative artifact_manifest.csv for all project files."""

import csv
import hashlib
import os
import subprocess


def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_git_info():
    try:
        branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
    except Exception:
        branch = "main"

    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        commit = "UNCOMMITTED_INITIAL (No commits yet on branch 'main')"

    return branch, commit


def categorize_file(rel_path: str) -> str:
    norm = rel_path.replace("\\", "/")
    if norm.startswith("src/"):
        return "Source Code"
    elif norm.startswith("tests/"):
        return "Test Suite"
    elif norm.startswith("scripts/"):
        return "Executable Script"
    elif norm.startswith("blockchain/contracts/"):
        return "Smart Contract"
    elif norm.startswith("blockchain/"):
        return "Blockchain Build/Config"
    elif norm.startswith("results/adversarial_evaluation/"):
        return "Adversarial Experiment Telemetry"
    elif norm.startswith("results/"):
        return "Baseline Experiment Telemetry"
    elif norm.endswith(".lock") or norm.endswith(".toml") or norm.endswith(".json"):
        return "Package/Config"
    else:
        return "Root / Documentation"


def main():
    branch, commit = get_git_info()
    manifest_rows = []

    # Directories to scan
    scan_dirs = ["src", "tests", "scripts", "blockchain", "results"]
    root_files = [
        "pyproject.toml",
        "uv.lock",
        "package.json",
        "package-lock.json",
        "hardhat.config.js",
        "README.md",
        "test_execution.log",
        "experiment_reconciliation.csv",
        "RESEARCH_EXPERIMENT_COVERAGE.md",
        "HYPOTHESIS_EVIDENCE_MATRIX.md",
        "RESEARCH_READINESS_REPORT.md",
        "EXPERIMENT_COVERAGE_MATRIX.csv",
        "METRIC_AND_INVARIANT_AUDIT.md",
        "ADDITIONAL_EXPERIMENT_PLAN.md",
        "REPRODUCIBILITY_AUDIT.md",
        "unresolved_issues.md",
        "invariant_verification.md",
        "blockchain_verification.md",
    ]

    tracked_files = []
    for d in scan_dirs:
        for root, dirs, files in os.walk(d):
            # Skip node_modules, cache, plots
            if "node_modules" in root or "__pycache__" in root or "reproduced_adversarial_evaluation" in root:
                continue
            for f in files:
                tracked_files.append(os.path.join(root, f))

    for rf in root_files:
        if os.path.exists(rf):
            tracked_files.append(rf)

    tracked_files.sort()

    for fp in tracked_files:
        rel_p = os.path.relpath(fp, ".").replace("\\", "/")
        size = os.path.getsize(fp)
        sha = compute_sha256(fp)
        cat = categorize_file(rel_p)

        manifest_rows.append({
            "relative_path": rel_p,
            "category": cat,
            "size_bytes": size,
            "sha256": sha,
            "git_branch": branch,
            "git_commit": commit,
        })

    with open("artifact_manifest.csv", mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "relative_path",
                "category",
                "size_bytes",
                "sha256",
                "git_branch",
                "git_commit",
            ],
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"Generated artifact_manifest.csv with {len(manifest_rows)} tracked files.")


if __name__ == "__main__":
    main()
