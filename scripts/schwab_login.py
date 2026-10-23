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
    
    import argparse
    parser = argparse.ArgumentParser(description="Authenticate or renew Charles Schwab OAuth2 tokens.")
    parser.add_argument("--force", action="store_true", help="Force new login even if current token appears active")
    args = parser.parse_args()

    # 1. Check if we already have valid or refreshable tokens (unless --force is passed)
    if not args.force and auth.tokens and "refresh_token" in auth.tokens:
        try:
            print("\nFound existing Schwab token in data_cache/schwab_token.json.")
            print("Verifying connection and testing token refresh...")
            token = auth.get_access_token()
            
            from execution.schwab_broker import SchwabBroker
            broker = SchwabBroker(auth=auth)
            cash = broker.get_cash_balance()

            print("\n" + "=" * 70)
            print("✅ EXISTING TOKEN IS ACTIVE & VALID!")
            print("=" * 70)
            print(f"Schwab Account Hash: {broker.account_hash}")
            print(f"Settled Cash Balance: ${cash:,.2f}")
            print("No login needed. Your bot is already authorized to trade.")
            print("(Pass --force if you want to request a brand new refresh token.)")
            print("=" * 70 + "\n")
            return
        except Exception as e:
            print(f"Existing token could not be refreshed ({e}). Proceeding to re-authenticate...\n")

    try:
        # Run login flow with automatic browser URL / clipboard detection and auto-sync
        token_data = auth.login_interactive()

        print("\n" + "=" * 70)
        print("✅ SUCCESS! Schwab Tokens acquired and updated.")
        print("=" * 70)
        print("• Saved to local cache: data_cache/schwab_token.json")
        print("• Automatically synchronized to GCP Secret Manager (schwab-token-data)")

        # Print account hash and current cash balance
        from execution.schwab_broker import SchwabBroker
        broker = SchwabBroker(auth=auth)
        print(f"\nYour Schwab Account Hash: {broker.account_hash}")
        print(f"Settled Cash Balance: ${broker.get_cash_balance():,.2f}\n")

    except Exception as e:
        print(f"\nAuthentication Failed: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
