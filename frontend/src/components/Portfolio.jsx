import React, { useState } from 'react';
import { Wallet, DollarSign, Layers, ArrowUpRight, ArrowDownRight, XCircle, Landmark, TrendingUp, History, ChevronDown, ChevronUp } from 'lucide-react';

export default function Portfolio({ portfolio, onSellPosition }) {
  const [showCashFlows, setShowCashFlows] = useState(false);

  const positions = portfolio?.positions || [];
  const cash = portfolio?.cash || 0;
  const marketVal = portfolio?.total_market_value || 0;
  const totalVal = portfolio?.total_portfolio_value || (cash + marketVal);
  const exposure = portfolio?.total_exposure || 0;

  // Capital Ledger Metrics
  const netContributed = portfolio?.net_contributed_capital || totalVal;
  const truePnl = portfolio?.true_strategy_pnl ?? 0;
  const truePnlPct = portfolio?.true_strategy_pnl_pct ?? 0;
  const twrPct = portfolio?.twr_pct ?? 0;
  const cashFlows = portfolio?.cash_flows || [];

  // Active unrealized P&L
  const totalUnrealizedPnl = positions.reduce((acc, p) => acc + p.unrealized_pnl, 0);

  const isPositiveGain = truePnl >= 0;

  return (
    <div className="space-y-5">
      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Equity Card with True Strategy Gain */}
        <div className="glass-panel p-4.5 rounded-2xl relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Total Portfolio Value</span>
            <Wallet className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-2 text-2xl font-bold tracking-tight text-white">
            ${totalVal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="mt-1 flex items-center justify-between text-xs">
            <div className="flex items-center space-x-1.5">
              <span className={`font-semibold ${isPositiveGain ? 'text-emerald-400' : 'text-rose-400'}`}>
                {isPositiveGain ? '+' : ''}${truePnl.toFixed(2)} ({isPositiveGain ? '+' : ''}{truePnlPct.toFixed(2)}%)
              </span>
              <span className="text-slate-500">True Gain</span>
            </div>
            {positions.length > 0 && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded ${totalUnrealizedPnl >= 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
                {totalUnrealizedPnl >= 0 ? '+' : ''}${totalUnrealizedPnl.toFixed(2)} active
              </span>
            )}
          </div>
        </div>

        {/* Net Contributed Capital */}
        <div className="glass-panel p-4.5 rounded-2xl relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Contributed Capital</span>
            <Landmark className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="mt-2 text-2xl font-bold tracking-tight text-white">
            ${netContributed.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="mt-1 text-slate-500 text-xs flex items-center justify-between">
            <span>External Bank Transfers</span>
            <span className="font-mono text-slate-400 text-[11px]">{cashFlows.length} record(s)</span>
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
            <Layers className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-2 text-2xl font-bold tracking-tight text-white">
            ${exposure.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="mt-1 text-slate-500 text-xs">
            {positions.length} active overnight {positions.length === 1 ? 'position' : 'positions'}
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

      {/* Capital Cash Flow Activity & Bank Ledger */}
      <div className="glass-panel rounded-2xl overflow-hidden">
        <div 
          onClick={() => setShowCashFlows(!showCashFlows)}
          className="px-5 py-4 border-b border-slate-800/80 flex items-center justify-between cursor-pointer hover:bg-slate-850/40 transition"
        >
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <History className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-sm text-white">Capital Cash Flow & Bank Transfer Ledger</h3>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                  {cashFlows.length} Events
                </span>
              </div>
              <p className="text-xs text-slate-400">
                External bank transfers auto-detected from Schwab to preserve true Time-Weighted Return (TWR: {twrPct >= 0 ? '+' : ''}{twrPct.toFixed(2)}%)
              </p>
            </div>
          </div>
          <button type="button" className="text-slate-400 hover:text-white p-1">
            {showCashFlows ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>

        {showCashFlows && (
          <div className="overflow-x-auto">
            {cashFlows.length === 0 ? (
              <div className="p-6 text-center text-slate-500 text-xs">
                No external bank transfers recorded.
              </div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900/50 text-slate-400 font-medium uppercase text-[10px] tracking-wider border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-5">Date / Time</th>
                    <th className="py-2.5 px-5">Event Type</th>
                    <th className="py-2.5 px-5">Description</th>
                    <th className="py-2.5 px-5 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-medium">
                  {cashFlows.map((cf) => {
                    const isDeposit = cf.type === 'INITIAL_DEPOSIT' || cf.type === 'DEPOSIT';
                    return (
                      <tr key={cf.id} className="hover:bg-slate-800/30 transition">
                        <td className="py-3 px-5 text-slate-400 font-mono text-[11px]">
                          {new Date(cf.date).toLocaleString()}
                        </td>
                        <td className="py-3 px-5">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                            isDeposit ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                          }`}>
                            {cf.type.replace('_', ' ')}
                          </span>
                        </td>
                        <td className="py-3 px-5 text-slate-300">
                          {cf.description}
                        </td>
                        <td className={`py-3 px-5 text-right font-semibold ${isDeposit ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {isDeposit ? '+' : '-'}${Number(cf.amount).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
