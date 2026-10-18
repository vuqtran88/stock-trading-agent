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

export default function BacktestStudio() {
  const [startDate, setStartDate] = useState('2024-01-01');
  const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0]);
  const [topN, setTopN] = useState(3);
  const [regimeFilter, setRegimeFilter] = useState(true);
  const [initialCapital, setInitialCapital] = useState(10000);
  const [positionSize, setPositionSize] = useState(1000);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);

  const handleRunBacktest = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/backtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start_date: startDate,
          end_date: endDate || null,
          top_n: Number(topN),
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
        className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-2xl p-5 shadow-xl grid grid-cols-1 md:grid-cols-6 gap-4 items-end"
      >
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
            Position Size ($)
          </label>
          <input
            type="number"
            min="100"
            max="10000"
            step="100"
            value={positionSize}
            onChange={(e) => setPositionSize(e.target.value)}
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
            Filter by 20 EMA Regime
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
