import React, { useState } from 'react';
import { ShoppingCart, Send, Loader2 } from 'lucide-react';

export default function OrderForm({ onPlaceOrder, isLive }) {
  const [ticker, setTicker] = useState('AAPL');
  const [shares, setShares] = useState(1);
  const [side, setSide] = useState('BUY');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (shares <= 0) return;

    setLoading(true);
    setStatus(null);
    try {
      await onPlaceOrder({ ticker: ticker.toUpperCase(), shares: parseInt(shares), side });
      setStatus({ type: 'success', text: `Order executed: ${side} ${shares} ${ticker.toUpperCase()}` });
    } catch (err) {
      setStatus({ type: 'error', text: err.message || 'Order failed' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-panel p-5 rounded-2xl space-y-4">
      <div>
        <h3 className="font-semibold text-sm text-white">Manual Paper Order Execution</h3>
        <p className="text-xs text-slate-400">Execute custom simulated market orders</p>
      </div>

      {isLive && (
        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs">
          Notice: Manual order entry is disabled in LIVE mode to prevent accidental real-money fills. Switch to PAPER mode to test manual orders.
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-3.5">
        <div className="grid grid-cols-2 gap-2 p-1 rounded-xl bg-slate-900 border border-slate-800">
          <button
            type="button"
            onClick={() => setSide('BUY')}
            className={`py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
              side === 'BUY' ? 'bg-emerald-600 text-white shadow' : 'text-slate-400 hover:text-white'
            }`}
          >
            BUY
          </button>
          <button
            type="button"
            onClick={() => setSide('SELL')}
            className={`py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
              side === 'SELL' ? 'bg-rose-600 text-white shadow' : 'text-slate-400 hover:text-white'
            }`}
          >
            SELL
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Ticker</label>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="AAPL"
              disabled={isLive}
              className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-white text-xs focus:outline-none focus:border-emerald-500 uppercase font-semibold"
            />
          </div>
          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Shares</label>
            <input
              type="number"
              min="1"
              value={shares}
              onChange={(e) => setShares(e.target.value)}
              disabled={isLive}
              className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-white text-xs focus:outline-none focus:border-emerald-500 font-semibold"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading || isLive}
          className={`w-full py-2.5 rounded-lg text-xs font-semibold flex items-center justify-center space-x-2 transition cursor-pointer ${
            side === 'BUY' 
              ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/20' 
              : 'bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-600/20'
          } disabled:opacity-50`}
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
          <span>Submit {side} Order</span>
        </button>

        {status && (
          <div className={`p-2.5 rounded-lg text-xs font-medium text-center ${
            status.type === 'success' ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-300 border border-rose-500/20'
          }`}>
            {status.text}
          </div>
        )}
      </form>
    </div>
  );
}
