"""Performance analytics and financial risk metrics."""

from typing import Dict, Optional
import numpy as np
import pandas as pd


class PerformanceMetrics:
    """Calculates risk-adjusted return and drawdown statistics."""

    @staticmethod
    def calculate_cagr(equity_curve: pd.Series, trading_days_per_year: int = 252) -> float:
        """Calculate Compound Annual Growth Rate (CAGR)."""
        if equity_curve.empty or len(equity_curve) < 2:
            return 0.0
        start_val = equity_curve.iloc[0]
        end_val = equity_curve.iloc[-1]
        n_days = len(equity_curve)
        if start_val <= 0 or end_val <= 0 or n_days <= 0:
            return 0.0
        years = n_days / trading_days_per_year
        if years <= 0:
            return 0.0
        return float((end_val / start_val) ** (1.0 / years) - 1.0)

    @staticmethod
    def calculate_drawdown_series(equity_curve: pd.Series) -> pd.Series:
        """Calculate underwater drawdown series as a percentage (negative or 0)."""
        if equity_curve.empty:
            return pd.Series(dtype=float)
        running_max = equity_curve.cummax()
        drawdown = (equity_curve - running_max) / running_max
        return drawdown

    @staticmethod
    def calculate_max_drawdown(equity_curve: pd.Series) -> float:
        """Calculate Maximum Drawdown (as a negative percentage, e.g. -0.15 for -15%)."""
        dd = PerformanceMetrics.calculate_drawdown_series(equity_curve)
        if dd.empty:
            return 0.0
        return float(dd.min())

    @staticmethod
    def calculate_sharpe_ratio(
        daily_returns: pd.Series,
        risk_free_rate: float = 0.0,
        trading_days_per_year: int = 252,
    ) -> float:
        """Calculate Annualized Sharpe Ratio."""
        clean_ret = daily_returns.dropna()
        if len(clean_ret) < 5 or clean_ret.std() == 0:
            return 0.0
        excess_daily_ret = clean_ret.mean() - (risk_free_rate / trading_days_per_year)
        annualized_sharpe = (excess_daily_ret / clean_ret.std()) * np.sqrt(trading_days_per_year)
        return float(annualized_sharpe)

    @staticmethod
    def calculate_sortino_ratio(
        daily_returns: pd.Series,
        risk_free_rate: float = 0.0,
        trading_days_per_year: int = 252,
    ) -> float:
        """Calculate Annualized Sortino Ratio (downside deviation only)."""
        clean_ret = daily_returns.dropna()
        if len(clean_ret) < 5:
            return 0.0
        downside = clean_ret[clean_ret < 0]
        if len(downside) == 0 or downside.std() == 0:
            return 0.0
        downside_std = np.sqrt(np.mean(downside**2))
        excess_daily_ret = clean_ret.mean() - (risk_free_rate / trading_days_per_year)
        return float((excess_daily_ret / downside_std) * np.sqrt(trading_days_per_year))

    @staticmethod
    def calculate_win_rate(daily_returns: pd.Series) -> float:
        """Percentage of active trading days with positive return."""
        active = daily_returns[daily_returns != 0].dropna()
        if len(active) == 0:
            return 0.0
        wins = active[active > 0]
        return float(len(wins) / len(active))

    @staticmethod
    def calculate_profit_factor(daily_returns: pd.Series) -> float:
        """Gross profits divided by gross losses."""
        clean = daily_returns.dropna()
        gains = clean[clean > 0].sum()
        losses = abs(clean[clean < 0].sum())
        if losses == 0:
            return float("inf") if gains > 0 else 0.0
        return float(gains / losses)

    @staticmethod
    def calculate_expected_value(daily_returns: pd.Series) -> float:
        """Expected value per active trade: (win_rate * avg_win) - (loss_rate * abs(avg_loss))."""
        active = daily_returns[daily_returns != 0].dropna()
        if len(active) == 0:
            return 0.0
        wins = active[active > 0]
        losses = active[active < 0]
        win_rate = len(wins) / len(active)
        loss_rate = len(losses) / len(active)
        avg_win = wins.mean() if len(wins) > 0 else 0.0
        avg_loss = abs(losses.mean()) if len(losses) > 0 else 0.0
        return float((win_rate * avg_win) - (loss_rate * avg_loss))

    @classmethod
    def compute_all_metrics(
        cls,
        equity_curve: pd.Series,
        daily_returns: pd.Series,
        benchmark_equity: Optional[pd.Series] = None,
    ) -> Dict[str, float]:
        """Compute full summary dictionary of performance metrics."""
        tot_return = float((equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1.0)
        cagr = cls.calculate_cagr(equity_curve)
        max_dd = cls.calculate_max_drawdown(equity_curve)
        sharpe = cls.calculate_sharpe_ratio(daily_returns)
        sortino = cls.calculate_sortino_ratio(daily_returns)
        win_rate = cls.calculate_win_rate(daily_returns)
        profit_factor = cls.calculate_profit_factor(daily_returns)
        ev = cls.calculate_expected_value(daily_returns)
        active_days = int((daily_returns != 0).sum())

        results = {
            "Total Return (%)": tot_return * 100.0,
            "CAGR (%)": cagr * 100.0,
            "Max Drawdown (%)": max_dd * 100.0,
            "Sharpe Ratio": sharpe,
            "Sortino Ratio": sortino,
            "Win Rate (%)": win_rate * 100.0,
            "Profit Factor": profit_factor,
            "Expected Value per Trade (%)": ev * 100.0,
            "Total Active Trading Days": active_days,
        }

        if benchmark_equity is not None and not benchmark_equity.empty:
            bench_ret = float((benchmark_equity.iloc[-1] / benchmark_equity.iloc[0]) - 1.0)
            bench_cagr = cls.calculate_cagr(benchmark_equity)
            bench_dd = cls.calculate_max_drawdown(benchmark_equity)
            bench_daily_ret = benchmark_equity.pct_change().dropna()
            bench_sharpe = cls.calculate_sharpe_ratio(bench_daily_ret)

            results["Benchmark Total Return (%)"] = bench_ret * 100.0
            results["Benchmark CAGR (%)"] = bench_cagr * 100.0
            results["Benchmark Max Drawdown (%)"] = bench_dd * 100.0
            results["Benchmark Sharpe"] = bench_sharpe

        return results
