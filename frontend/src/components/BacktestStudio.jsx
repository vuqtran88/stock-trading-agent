import React, { useState } from 'react';
import {
  TrendingUp,
  Play,
  RotateCcw,
  CheckCircle2,
  Calendar,
  AlertTriangle,
  ArrowUpRight,
  ArrowDownRight,
  Layers,
  Percent,
  DollarSign,
  Activity,
  Plus,
  X,
  Sliders,
  Sparkles,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from 'recharts';

const POPULAR_TICKERS = [
  'AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'AMD',
  'NFLX', 'PLTR', 'AVGO', 'SMCI', 'COIN', 'ARM', 'UBER', 'CRWD'
];

export default function BacktestStudio() {
  const [startDate, setStartDate] = useState('2024-01-01');
  const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0]);
  const [topN, setTopN] = useState(3);
  const [regimeFilter, setRegimeFilter] = useState(true);
  const [regimeEma, setRegimeEma] = useState(20);
  const [initialCapital, setInitialCapital] = useState(10000);
  const [positionSize, setPositionSize] = useState(1000);

  // Independent backtest universe
  const [backtestTickers, setBacktestTickers] = useState([
    'AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'AMD'
  ]);
  const [customTickerInput, setCustomTickerInput] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);

  // Optionally load live universe on initial mount as a starting suggestion ONLY
  React.useEffect(() => {
    fetch('/api/config')
      .then((r) => r.json())
      .then((cfg) => {
        if (cfg?.tickers && Array.isArray(cfg.tickers) && cfg.tickers.length > 0) {
          setBacktestTickers(cfg.tickers);
        }
        if (cfg?.regime_ema_period) {
          setRegimeEma(cfg.regime_ema_period);
        }
      })
      .catch(() => {});
  }, []);

  const handleAddTicker = (tickerToAdd) => {
    const sym = (tickerToAdd || customTickerInput).trim().toUpperCase();
    if (!sym) return;
    if (!backtestTickers.includes(sym)) {
      setBacktestTickers([...backtestTickers, sym]);
    }
    setCustomTickerInput('');
  };

  const handleRemoveTicker = (sym) => {
    setBacktestTickers(backtestTickers.filter((t) => t !== sym));
  };

  const handleRunBacktest = async (e) => {
    if (e) e.preventDefault();
    if (backtestTickers.length === 0) {
      setError('Please add at least one stock to the backtest universe.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/backtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tickers: backtestTickers,
          start_date: startDate,
          end_date: endDate || null,
          top_n: Number(topN),
          regime_ema_period: Number(regimeEma),
          use_regime_filter: Boolean(regimeFilter),
          initial_capital: Number(initialCapital),
        }),
      });

      const text = await res.text();
      let data;
      try {
        data = JSON.parse(text);
      } catch (parseErr) {
        throw new Error(text || `Server error (${res.status})`);
      }

      if (!res.ok) {
        throw new Error(data.detail || 'Failed to complete backtest');
      }

      setResults(data);
    } catch (err) {
      setError(err.message || 'Backtest failed to execute');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-teal-400" />
            Interactive Backtest Studio
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Simulate the overnight momentum anomaly over historical market periods against the QQQ benchmark.
          </p>
        </div>
      </div>

      {/* Configuration Form */}
      <form
        onSubmit={handleRunBacktest}
        className="space-y-4"
      >
        {/* Backtest Universe Selector (Completely Isolated from Live/Paper Settings) */}
        <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-2xl p-5 shadow-xl">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
            <div>
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-teal-400" />
                <h3 className="text-sm font-semibold text-white">Backtest Target Universe</h3>
                <span className="text-[10px] bg-teal-500/10 text-teal-400 border border-teal-500/20 px-2 py-0.5 rounded-full font-mono">
                  {backtestTickers.length} stocks
                </span>
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Configure stocks to test exclusively for this simulation. Changes made here <strong className="text-emerald-400">do not affect</strong> your Paper or Live trading settings.
              </p>
            </div>

            {/* Quick Add Input */}
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="Add symbol e.g. TSM..."
                value={customTickerInput}
                onChange={(e) => setCustomTickerInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAddTicker();
                  }
                }}
                className="bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white uppercase focus:outline-none focus:border-teal-500 font-mono w-44"
              />
              <button
                type="button"
                onClick={() => handleAddTicker()}
                className="bg-teal-500/20 hover:bg-teal-500/30 text-teal-300 border border-teal-500/30 px-3 py-1.5 rounded-xl text-xs font-medium flex items-center gap-1 transition-all cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                Add
              </button>
            </div>
          </div>

          {/* Active Backtest Tickers Chips */}
          <div className="flex flex-wrap gap-1.5 mb-3">
            {backtestTickers.map((sym) => (
              <span
                key={sym}
                className="inline-flex items-center gap-1.5 bg-slate-950 border border-slate-800/80 hover:border-slate-700 text-slate-200 px-2.5 py-1 rounded-lg text-xs font-mono transition-all"
              >
                {sym}
                <button
                  type="button"
                  onClick={() => handleRemoveTicker(sym)}
                  className="text-slate-500 hover:text-rose-400 transition-colors cursor-pointer"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
            {backtestTickers.length === 0 && (
              <span className="text-xs text-amber-400/90 py-1 italic">
                No stocks selected. Please add stocks or click a preset below.
              </span>
            )}
          </div>

          {/* Popular Presets */}
          <div className="pt-2 border-t border-slate-800/60 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-400">
            <span className="flex items-center gap-1 text-slate-500 mr-1">
              <Sparkles className="w-3 h-3 text-amber-400/80" />
              Quick add:
            </span>
            {POPULAR_TICKERS.filter((sym) => !backtestTickers.includes(sym)).map((sym) => (
              <button
                key={sym}
                type="button"
                onClick={() => handleAddTicker(sym)}
                className="bg-slate-950/60 hover:bg-slate-800 text-slate-400 hover:text-teal-300 border border-slate-800/60 px-2 py-0.5 rounded text-[10px] font-mono transition-all cursor-pointer"
              >
                +{sym}
              </button>
            ))}
          </div>
        </div>

        {/* Backtest Simulation Parameters */}
        <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-2xl p-5 shadow-xl grid grid-cols-1 md:grid-cols-6 gap-4 items-end">
          <div>
            <label className="block text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-1">
              Start Date
            </label>
            <div className="relative">
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-teal-500 font-mono"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-1">
              End Date
            </label>
            <div className="relative">
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-teal-500 font-mono"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-1">
              Top N Stocks
            </label>
            <select
              value={topN}
              onChange={(e) => setTopN(e.target.value)}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-teal-500"
            >
              <option value={1}>Top 1 Highest Momentum</option>
              <option value={2}>Top 2 Highest Momentum</option>
              <option value={3}>Top 3 Highest Momentum</option>
              <option value={5}>Top 5 Highest Momentum</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-1">
              Initial Capital ($)
            </label>
            <input
              type="number"
              min="1000"
              max="1000000"
              step="1000"
              value={initialCapital}
              onChange={(e) => setInitialCapital(e.target.value)}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-teal-500 font-mono"
            />
          </div>

          <div className="flex items-center gap-2 pb-2">
            <input
              type="checkbox"
              id="regime"
              checked={regimeFilter}
              onChange={(e) => setRegimeFilter(e.target.checked)}
              className="w-4 h-4 rounded bg-slate-950 border-slate-800 text-teal-500 focus:ring-0 focus:ring-offset-0 cursor-pointer"
            />
            <label htmlFor="regime" className="text-xs text-slate-300 font-medium cursor-pointer">
              Filter by {regimeEma} EMA Regime
            </label>
          </div>

          <div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-teal-500 to-emerald-500 hover:from-teal-600 hover:to-emerald-600 text-white font-medium py-2 rounded-xl text-xs transition-all shadow-lg shadow-teal-500/20 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RotateCcw className="w-4 h-4 animate-spin" />
                  Simulating...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-white" />
                  Run Backtest
                </>
              )}
            </button>
          </div>
        </div>
      </form>

      {error && (
        <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Results Section */}
      {results && (
        <div className="space-y-6">
          {/* Summary KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-2xl p-4 shadow-xl">
              <span className="text-[11px] font-medium text-slate-400 flex items-center gap-1.5 uppercase tracking-wider">
                <Percent className="w-3.5 h-3.5 text-teal-400" />
                Strategy Return
              </span>
              <div
                className={`text-2xl font-bold font-mono mt-1 ${
                  (results.metrics["Total Return (%)"] || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {(results.metrics["Total Return (%)"] || 0) >= 0 ? '+' : ''}
                {Number(results.metrics["Total Return (%)"] || 0).toFixed(2)}%
              </div>
              <span className="text-[10px] text-slate-500">
                vs. QQQ Buy & Hold: {(results.metrics["Benchmark Total Return (%)"] || 0) >= 0 ? '+' : ''}
                {Number(results.metrics["Benchmark Total Return (%)"] || 0).toFixed(2)}%
              </span>
            </div>

            <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-2xl p-4 shadow-xl">
              <span className="text-[11px] font-medium text-slate-400 flex items-center gap-1.5 uppercase tracking-wider">
                <Activity className="w-3.5 h-3.5 text-indigo-400" />
                Sharpe Ratio
              </span>
              <div className="text-2xl font-bold font-mono text-white mt-1">
                {Number(results.metrics["Sharpe Ratio"] || 0).toFixed(2)}
              </div>
              <span className="text-[10px] text-slate-500">
                Annualized risk-adjusted performance
              </span>
            </div>

            <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-2xl p-4 shadow-xl">
              <span className="text-[11px] font-medium text-slate-400 flex items-center gap-1.5 uppercase tracking-wider">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                Win Rate
              </span>
              <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">
                {Number(results.metrics["Win Rate (%)"] || 0).toFixed(1)}%
              </div>
              <span className="text-[10px] text-slate-500">
                {results.trade_history?.length || 0} total overnight roundtrips
              </span>
            </div>

            <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-2xl p-4 shadow-xl">
              <span className="text-[11px] font-medium text-slate-400 flex items-center gap-1.5 uppercase tracking-wider">
                <DollarSign className="w-3.5 h-3.5 text-amber-400" />
                Profit Factor & Max DD
              </span>
              <div className="text-2xl font-bold font-mono text-white mt-1">
                {Number(results.metrics["Profit Factor"] || 0).toFixed(2)}x
              </div>
              <span className="text-[10px] text-rose-400">
                Max Drawdown: {Number(results.metrics["Max Drawdown (%)"] || 0).toFixed(1)}%
              </span>
            </div>
          </div>

          {/* Equity Curve Chart */}
          <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-2xl p-5 shadow-xl">
            <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
              <Layers className="w-4 h-4 text-teal-400" />
              Cumulative Equity Curve vs. Benchmark
            </h3>

            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={results.equity_curve}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" stroke="#64748b" tick={{ fontSize: 10 }} />
                  <YAxis
                    stroke="#64748b"
                    tick={{ fontSize: 10 }}
                    domain={['auto', 'auto']}
                    tickFormatter={(v) => `$${v.toLocaleString()}`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      border: '1px solid #334155',
                      borderRadius: '0.75rem',
                      fontSize: '11px',
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                  <Line
                    type="monotone"
                    dataKey="strategy"
                    name="Strategy Equity"
                    stroke="#14b8a6"
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="benchmark"
                    name="QQQ Benchmark"
                    stroke="#6366f1"
                    strokeWidth={1.5}
                    strokeDasharray="4 4"
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Granular Trade Audit Table */}
          <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-2xl p-5 shadow-xl">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">
              Trade Execution Log ({results.trade_history?.length || 0} Trades)
            </h3>
            <div className="overflow-x-auto max-h-80 overflow-y-auto">
              <table className="w-full text-left border-collapse">
                <thead className="sticky top-0 bg-slate-950/90 backdrop-blur text-[11px] uppercase tracking-wider text-slate-400">
                  <tr className="border-b border-slate-800">
                    <th className="py-2 px-3">Entry Date</th>
                    <th className="py-2 px-3">Symbol</th>
                    <th className="py-2 px-3">Entry Close (3:50 PM)</th>
                    <th className="py-2 px-3">Exit Open (9:30 AM)</th>
                    <th className="py-2 px-3">Net P&L ($)</th>
                    <th className="py-2 px-3">Return (%)</th>
                  </tr>
                </thead>
                <tbody className="text-xs divide-y divide-slate-800/60">
                  {(results.trade_history || []).map((t, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/20 transition-colors">
                      <td className="py-2 px-3 font-mono text-slate-400">{t.date}</td>
                      <td className="py-2 px-3 font-mono font-bold text-teal-400">{t.ticker}</td>
                      <td className="py-2 px-3 font-mono text-slate-200">${Number(t.entry_close).toFixed(2)}</td>
                      <td className="py-2 px-3 font-mono text-slate-200">${Number(t.exit_open).toFixed(2)}</td>
                      <td
                        className={`py-2 px-3 font-mono font-medium ${
                          t.pnl_usd >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {t.pnl_usd >= 0 ? '+' : ''}${Number(t.pnl_usd).toFixed(2)}
                      </td>
                      <td
                        className={`py-2 px-3 font-mono font-medium ${
                          t.return_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {t.return_pct >= 0 ? '+' : ''}{Number(t.return_pct).toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
