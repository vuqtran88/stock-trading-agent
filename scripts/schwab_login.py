"""CLI script to authenticate and obtain Charles Schwab OAuth2 tokens."""

import sys
from pathlib import Path

# Ensure project root in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings
from execution.schwab_auth import SchwabAuth


def main():
    if not settings.SCHWAB_APP_KEY or not settings.SCHWAB_APP_SECRET:
        print("\nERROR: SCHWAB_APP_KEY or SCHWAB_APP_SECRET is missing in .env.")
        print("Please edit .env with your approved Charles Schwab Developer credentials.\n")
        sys.exit(1)

    auth = SchwabAuth()
    try:
        auth.login_interactive(port=8080)
        print("Verification: Access Token retrieved successfully:")
        token = auth.get_access_token()
        print(f"Token Prefix: {token[:10]}... (Valid)")
    except Exception as e:
        print(f"\nAuthentication Failed: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
