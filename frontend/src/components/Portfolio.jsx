import React from 'react';
import { Wallet, DollarSign, Layers, ArrowUpRight, ArrowDownRight, XCircle } from 'lucide-react';

export default function Portfolio({ portfolio, onSellPosition }) {
  const positions = portfolio?.positions || [];
  const cash = portfolio?.cash || 0;
  const marketVal = portfolio?.total_market_value || 0;
  const totalVal = portfolio?.total_portfolio_value || (cash + marketVal);
  const exposure = portfolio?.total_exposure || 0;

  // Total unrealized P&L
  const totalUnrealizedPnl = positions.reduce((acc, p) => acc + p.unrealized_pnl, 0);

  return (
    <div className="space-y-5">
      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Equity Card */}
        <div className="glass-panel p-4.5 rounded-2xl relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Total Portfolio Value</span>
            <Wallet className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-2 text-2xl font-bold tracking-tight text-white">
            ${totalVal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="mt-1 flex items-center space-x-1.5 text-xs">
            <span className={totalUnrealizedPnl >= 0 ? 'text-emerald-400 font-semibold' : 'text-rose-400 font-semibold'}>
              {totalUnrealizedPnl >= 0 ? '+' : ''}${totalUnrealizedPnl.toFixed(2)}
            </span>
            <span className="text-slate-500">unrealized P&L</span>
          </div>
        </div>

        {/* Settled Cash */}
        <div className="glass-panel p-4.5 rounded-2xl relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Settled Cash</span>
            <DollarSign className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="mt-2 text-2xl font-bold tracking-tight text-white">
            ${cash.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="mt-1 text-slate-500 text-xs">
            {((cash / (totalVal || 1)) * 100).toFixed(1)}% liquid reserve
          </div>
        </div>

        {/* Active Exposure */}
        <div className="glass-panel p-4.5 rounded-2xl relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Overnight Exposure</span>
            <Layers className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="mt-2 text-2xl font-bold tracking-tight text-white">
            ${exposure.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="mt-1 text-slate-500 text-xs">
            {positions.length} active overnight {positions.length === 1 ? 'position' : 'positions'}
          </div>
        </div>

        {/* Market Value */}
        <div className="glass-panel p-4.5 rounded-2xl relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Holdings Market Value</span>
            <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300">Live Quote</span>
          </div>
          <div className="mt-2 text-2xl font-bold tracking-tight text-white">
            ${marketVal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="mt-1 text-slate-500 text-xs">
            Exits automatically at 9:30 AM open
          </div>
        </div>
      </div>

      {/* Active Holdings Table */}
      <div className="glass-panel rounded-2xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-800/80 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-sm text-white">Active Overnight Positions</h3>
            <p className="text-xs text-slate-400">Positions bought at market close held for overnight drift</p>
          </div>
          <span className="text-xs px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 font-medium">
            {positions.length} Holdings
          </span>
        </div>

        {positions.length === 0 ? (
          <div className="p-8 text-center">
            <div className="w-12 h-12 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center mx-auto text-slate-500">
              <Layers className="w-5 h-5" />
            </div>
            <p className="mt-3 text-sm font-medium text-slate-300">Account is 100% in Cash</p>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              No open overnight positions. The bot sits in cash during the day and scans at 3:50 PM ET before close.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900/50 text-slate-400 font-medium uppercase text-[10px] tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-3 px-5">Symbol</th>
                  <th className="py-3 px-5">Shares</th>
                  <th className="py-3 px-5">Entry Close</th>
                  <th className="py-3 px-5">Live Price</th>
                  <th className="py-3 px-5">Market Value</th>
                  <th className="py-3 px-5">Unrealized P&L</th>
                  <th className="py-3 px-5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-medium">
                {positions.map((p) => {
                  const isProfit = p.unrealized_pnl >= 0;
                  return (
                    <tr key={p.ticker} className="hover:bg-slate-800/30 transition">
                      <td className="py-3.5 px-5 font-bold text-white flex items-center space-x-2">
                        <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                        <span>{p.ticker}</span>
                      </td>
                      <td className="py-3.5 px-5 text-slate-300">{p.shares}</td>
                      <td className="py-3.5 px-5 text-slate-400">${p.entry_price.toFixed(2)}</td>
                      <td className="py-3.5 px-5 text-white font-semibold">${p.current_price.toFixed(2)}</td>
                      <td className="py-3.5 px-5 text-slate-300 font-semibold">${p.market_value.toFixed(2)}</td>
                      <td className="py-3.5 px-5">
                        <div className={`flex items-center space-x-1 font-semibold ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {isProfit ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
                          <span>{isProfit ? '+' : ''}${p.unrealized_pnl.toFixed(2)} ({isProfit ? '+' : ''}{p.unrealized_pnl_pct.toFixed(2)}%)</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-5 text-right">
                        <button
                          onClick={() => onSellPosition(p.ticker, p.shares)}
                          className="px-2.5 py-1 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 font-semibold text-[11px] transition cursor-pointer"
                        >
                          Close Out
                        </button>
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
