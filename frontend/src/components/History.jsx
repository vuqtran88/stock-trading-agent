import React, { useState, useEffect } from 'react';
import { History as HistoryIcon, ArrowDownRight, ArrowUpRight, Clock, RefreshCw } from 'lucide-react';

export default function History() {
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchHistory = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/trading/trade-history');
      if (res.ok) {
        const data = await res.json();
        setTrades(data.trades || []);
      }
    } catch (err) {
      console.error('Failed to load trade history:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <HistoryIcon className="w-5 h-5 text-indigo-400" />
            Trade Execution History
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Complete audit trail of paper and live filled orders recorded in the trade log.
          </p>
        </div>
        <button
          onClick={fetchHistory}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-2xl p-5 shadow-xl">
        {loading ? (
          <div className="py-12 text-center text-slate-500 text-xs">Loading execution logs...</div>
        ) : trades.length === 0 ? (
          <div className="py-12 text-center text-slate-500 text-xs">
            No executed trades recorded yet. Place manual paper trades or run automated routines to populate history.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400">
                  <th className="py-3 px-3">Timestamp</th>
                  <th className="py-3 px-3">Symbol</th>
                  <th className="py-3 px-3">Side</th>
                  <th className="py-3 px-3">Shares</th>
                  <th className="py-3 px-3">Execution Price</th>
                  <th className="py-3 px-3">Total Value</th>
                  <th className="py-3 px-3">Mode</th>
                </tr>
              </thead>
              <tbody className="text-xs divide-y divide-slate-800/60">
                {trades.map((t, idx) => {
                  const isBuy = t.action?.toUpperCase() === 'BUY';
                  const totalVal = (t.shares || 0) * (t.price || 0);

                  return (
                    <tr key={idx} className="hover:bg-slate-800/20 transition-colors">
                      <td className="py-2.5 px-3 font-mono text-slate-400 text-[11px] flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-slate-600" />
                        {t.timestamp}
                      </td>
                      <td className="py-2.5 px-3 font-mono font-bold text-white">{t.symbol}</td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold ${
                            isBuy
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                              : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                          }`}
                        >
                          {isBuy ? (
                            <ArrowUpRight className="w-3 h-3" />
                          ) : (
                            <ArrowDownRight className="w-3 h-3" />
                          )}
                          {t.action}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-mono text-slate-300">{t.shares}</td>
                      <td className="py-2.5 px-3 font-mono text-slate-300">
                        ${Number(t.price || 0).toFixed(2)}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-slate-300">
                        ${Number(totalVal).toFixed(2)}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                          {t.mode || 'paper'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
