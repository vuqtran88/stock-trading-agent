#!/usr/bin/env python3
"""Pre-commit secret and sensitive data scanner.

Runs automatically before every `git commit` to block:
1. Accidental staging of .env files or token files.
2. Hardcoded API keys, secrets, Discord webhooks, or private tokens in staged diffs.
"""

import sys
import re
import subprocess

# Regular expressions for patterns that should NEVER be committed
SENSITIVE_PATTERNS = [
    # Discord Webhook URLs
    (re.compile(r"https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_-]+"), "Discord Webhook URL"),
    # Schwab Key/Secret assignments with non-empty values
    (re.compile(r'SCHWAB_APP_KEY\s*=\s*["\'][A-Za-z0-9_\-]{8,}["\']'), "Schwab App Key"),
    (re.compile(r'SCHWAB_APP_SECRET\s*=\s*["\'][A-Za-z0-9_\-]{8,}["\']'), "Schwab App Secret"),
    (re.compile(r'SCHWAB_ACCOUNT_HASH\s*=\s*["\'][A-Za-z0-9_\-]{8,}["\']'), "Schwab Account Hash"),
    # Generic Private Key blocks
    (re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"), "Private Key block"),
    # Generic API Keys / Tokens (AWS, Slack, Github, OpenAI)
    (re.compile(r"(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}"), "AWS Access Key"),
    (re.compile(r"ghp_[A-Za-z0-9_]{36}"), "GitHub Personal Access Token"),
    (re.compile(r"xox[baprs]-[0-9A-Za-z]{10,48}"), "Slack Token"),
    (re.compile(r"sk-[A-Za-z0-9_-]{32,}"), "OpenAI / Generic Secret Key"),
]

BLOCKED_FILES = [
    ".env",
    ".env.local",
    "schwab_token.json",
]


def check_staged_filenames() -> list:
    """Check if any sensitive files are staged."""
    cmd = ["git", "diff", "--cached", "--name-only"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    staged_files = res.stdout.strip().splitlines()

    violations = []
    for f in staged_files:
        basename = f.split("/")[-1]
        if basename in BLOCKED_FILES or f in BLOCKED_FILES:
            violations.append(f"CRITICAL: Staging '{f}' is prohibited! Sensitive environment/token file.")
    return violations


def check_staged_content() -> list:
    """Scan diff lines being added in staged commits."""
    cmd = ["git", "diff", "--cached", "-U0"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    diff_text = res.stdout

    violations = []
    current_file = "Unknown"

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            continue

        # Only inspect added lines
        if line.startswith("+") and not line.startswith("+++"):
            added_content = line[1:].strip()

            # Ignore comment lines in example files or markdown
            if current_file.endswith(".example") or current_file.endswith(".md"):
                continue

            for pattern, desc in SENSITIVE_PATTERNS:
                if pattern.search(added_content):
                    violations.append(
                        f"CRITICAL: Found {desc} in {current_file}:\n   --> {added_content[:60]}..."
                    )

    return violations


def main():
    file_violations = check_staged_filenames()
    content_violations = check_staged_content()
    all_violations = file_violations + content_violations

    if all_violations:
        print("\n" + "!" * 75)
        print("🛑 COMMIT BLOCKED: Sensitive Data / Secret Scan Failed!")
        print("!" * 75)
        for v in all_violations:
            print(f" • {v}")
        print("\nPlease remove the secret from staged files or unstage them (`git reset HEAD <file>`).")
        print("!" * 75 + "\n")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
