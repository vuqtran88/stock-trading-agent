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
        import webbrowser
        import urllib.parse

        auth_url = (
            f"https://api.schwabapi.com/v1/oauth/authorize?client_id={auth.app_key}"
            f"&redirect_uri={urllib.parse.quote(auth.callback_url)}"
        )
        print("\n" + "=" * 70)
        print("CHARLES SCHWAB OAUTH2 AUTHORIZATION")
        print("=" * 70)
        print("1. Opening your browser to log into Charles Schwab...")
        print(f"URL: {auth_url}\n")
        webbrowser.open(auth_url)

        print("2. Log into Schwab and approve access.")
        print("3. Your browser will redirect to https://127.0.0.1/?code=... (it may say 'site can't be reached' — this is normal!)")
        print("4. COPY the entire URL from your browser's address bar and paste it below:\n")
        
        redirected_url = input("Paste redirected URL here: ").strip()
        auth.exchange_code_for_tokens(redirected_url)
        
        print("\n" + "=" * 70)
        print("✅ SUCCESS! Schwab Tokens stored in data_cache/schwab_token.json")
        print("=" * 70)

        # Print account hash
        from execution.schwab_broker import SchwabBroker
        broker = SchwabBroker(auth=auth)
        print(f"\nYour Schwab Account Hash: {broker.account_hash}")
        print(f"Settled Cash Balance: ${broker.get_cash_balance():,.2f}\n")

    except Exception as e:
        print(f"\nAuthentication Failed: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
