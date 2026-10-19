"""Discord Webhook notification service for real-time trade alerts."""

import logging
from typing import Dict, List, Optional
import requests

from config.settings import settings

logger = logging.getLogger(__name__)


class DiscordNotifier:
    """Sends rich embed notifications to a configured Discord webhook."""

    def __init__(self, webhook_url: Optional[str] = None, env: Optional[str] = None):
        target_env = (env or settings.ENV).lower()
        if webhook_url:
            self.webhook_url = webhook_url
        elif target_env == "live" and settings.DISCORD_LIVE_WEBHOOK_URL:
            self.webhook_url = settings.DISCORD_LIVE_WEBHOOK_URL
        elif target_env == "paper" and settings.DISCORD_PAPER_WEBHOOK_URL:
            self.webhook_url = settings.DISCORD_PAPER_WEBHOOK_URL
        else:
            self.webhook_url = settings.DISCORD_WEBHOOK_URL or settings.DISCORD_PAPER_WEBHOOK_URL or settings.DISCORD_LIVE_WEBHOOK_URL

    def is_configured(self) -> bool:
        """Check if a webhook URL is provided."""
        return bool(self.webhook_url and self.webhook_url.startswith("https://discord.com/api/webhooks/"))

    def _get_webhook_for_env(self, env: Optional[str] = None) -> str:
        target_env = (env or settings.ENV).lower()
        if target_env == "live" and settings.DISCORD_LIVE_WEBHOOK_URL:
            return settings.DISCORD_LIVE_WEBHOOK_URL
        elif target_env == "paper" and settings.DISCORD_PAPER_WEBHOOK_URL:
            return settings.DISCORD_PAPER_WEBHOOK_URL
        return self.webhook_url or settings.DISCORD_WEBHOOK_URL

    def send_message(self, content: str, embed: Optional[Dict] = None, webhook_url: Optional[str] = None) -> bool:
        """Send message or embed to Discord."""
        target_url = webhook_url or self.webhook_url
        if not target_url or not target_url.startswith("https://discord.com/api/webhooks/"):
            logger.debug("Discord webhook not configured; skipping notification.")
            return False

        payload = {"content": content}
        if embed:
            payload["embeds"] = [embed]

        try:
            resp = requests.post(target_url, json=payload, timeout=10)
            if resp.status_code in (200, 204):
                logger.debug("Discord notification sent successfully.")
                return True
            else:
                logger.warning(f"Failed to post to Discord (HTTP {resp.status_code}): {resp.text}")
                return False
        except Exception as e:
            logger.warning(f"Discord notification error: {e}")
            return False

    def notify_buy_orders(self, orders: List[Dict], regime_info: str, total_cost: float, env: str = "live"):
        """Notify Discord when buy orders are placed near close."""
        fields = []
        for o in orders:
            fields.append({
                "name": f"{o['ticker']} (BUY)",
                "value": f"{o['shares']} shares @ ${o['fill_price']:.2f} = **${o['total_value']:,.2f}**",
                "inline": True,
            })

        embed = {
            "title": f"🔔 Market Close Buy Routine Executed [{env.upper()}]",
            "description": f"**Market Regime:** {regime_info}\n**Total Deployed:** ${total_cost:,.2f}",
            "color": 3066993,  # Green
            "fields": fields,
            "footer": {"text": "Stock Trading Agent • Buy-at-Close"},
        }
        url = self._get_webhook_for_env(env)
        self.send_message(content="", embed=embed, webhook_url=url)

    def notify_sell_orders(self, reports: List[Dict], total_pnl: float, cash_balance: float, env: str = "live"):
        """Notify Discord when overnight positions are sold at open."""
        fields = []
        for r in reports:
            pnl = r.get("realized_pnl", 0.0)
            pnl_str = f"${pnl:+,.2f}"
            fields.append({
                "name": f"{r['ticker']} (SELL)",
                "value": f"{r['shares']} shares @ ${r['fill_price']:.2f}\nP&L: **{pnl_str}**",
                "inline": True,
            })

        color = 3066993 if total_pnl >= 0 else 15158332  # Green if profit, Red if loss
        embed = {
            "title": f"☀️ Market Open Sell Routine Executed [{env.upper()}]",
            "description": f"**Total Overnight Realized P&L:** **${total_pnl:+,.2f}**\n**Settled Cash Balance:** ${cash_balance:,.2f}",
            "color": color,
            "fields": fields,
            "footer": {"text": "Stock Trading Agent • Sell-at-Open (100% Cash)"},
        }
        url = self._get_webhook_for_env(env)
        self.send_message(content="", embed=embed, webhook_url=url)

    def notify_routine_status(self, routine_name: str, message: str, trigger_source: str = "SCHEDULED", env: str = "paper", details: Optional[List[Dict]] = None):
        """Notify Discord when a routine executes even if 0 trades are made (heartbeat & audit)."""
        source_badge = "⏱️ SCHEDULED (Cron)" if trigger_source.upper() == "SCHEDULED" else "👤 MANUAL (Dashboard)"
        embed = {
            "title": f"📋 {routine_name} Completed [{env.upper()}]",
            "description": f"**Triggered By:** {source_badge}\n**Status:** {message}",
            "color": 3447003,  # Blue/Informational
            "fields": details or [],
            "footer": {"text": f"Stock Trading Agent • {source_badge}"},
        }
        url = self._get_webhook_for_env(env)
        self.send_message(content="", embed=embed, webhook_url=url)

    def notify_emergency_stop(self, reason: str, flattened_count: int, cash_balance: float):
        """Notify Discord when the emergency kill switch is tripped."""
        embed = {
            "title": "🚨 EMERGENCY KILL SWITCH TRIPPED",
            "description": f"**Reason:** {reason}\n**Positions Liquidated:** {flattened_count}\n**Cash Balance:** ${cash_balance:,.2f}",
            "color": 15158332,  # Red
            "footer": {"text": "Stock Trading Agent • Emergency Halt"},
        }
        self.send_message(content="@everyone 🚨 **Emergency Halt Triggered!**", embed=embed)
