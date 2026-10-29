import React from 'react';
import {
  Sparkles,
  Layers,
  Clock,
  ShieldCheck,
  Target,
  Sliders,
  DollarSign,
  Play,
  Pause,
  ExternalLink,
} from 'lucide-react';

export default function StrategyOverview({ config, currentEnv, onNavigateSettings }) {
  if (!config) return null;

  const envData = (config[currentEnv] && typeof config[currentEnv] === 'object')
    ? config[currentEnv]
    : config;

  const availableStrategies = config.available_strategies || [];
  const activeStratId = envData.active_strategy || config.active_strategy || 'overnight_drift';
  const selectedStrat = availableStrategies.find((s) => s.id === activeStratId) || {
    id: activeStratId,
    name: activeStratId === 'overnight_drift' ? 'Overnight Drift Anomaly' : activeStratId,
    description: 'Enters high-momentum dips at Market Close (3:50 PM ET) and exits at Market Open (9:28 AM ET). Captures the structural overnight market drift.',
    status: 'active',
  };

  const isEnabled = envData.strategy_enabled ?? config.strategy_enabled ?? true;
  const isLive = currentEnv === 'live';
  const tickers = envData.tickers || config.tickers || [];
  const topN = envData.top_n ?? config.top_n ?? 3;
  const maxPos = envData.max_position_size_usd ?? config.max_position_size_usd ?? 1000;
  const pilotBudget = envData.live_pilot_budget_usd ?? config.live_pilot_budget_usd ?? 2000;
  const useRegime = envData.use_regime_filter ?? config.use_regime_filter ?? true;
  const regimePeriod = envData.regime_ema_period ?? config.regime_ema_period ?? 20;
  const closeTime = envData.close_routine_time || config.close_routine_time || '15:50';
  const openTime = envData.open_routine_time || config.open_routine_time || '09:28';

  return (
    <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800/90 rounded-2xl p-5 shadow-xl relative overflow-hidden">
      {/* Decorative gradient flare */}
      <div className="absolute top-0 right-0 w-80 h-32 bg-indigo-500/5 rounded-full blur-3xl pointer-events-none -mr-16 -mt-10" />

      {/* Header Row: Title, Status Badge & Quick Settings Link */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-800/80 relative">
        <div className="flex items-start gap-3">
          <div className="p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 shrink-0 mt-0.5">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[11px] font-bold text-indigo-400 uppercase tracking-wider">
                Active Trading Model & Parameters
              </span>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider ${
                isLive
                  ? 'bg-rose-500/15 text-rose-300 border border-rose-500/30'
                  : 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
              }`}>
                {currentEnv.toUpperCase()} SCOPE
              </span>
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                isEnabled
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                  : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
              }`}>
                {isEnabled ? <Play className="w-2.5 h-2.5 fill-current" /> : <Pause className="w-2.5 h-2.5 fill-current" />}
                {isEnabled ? 'Engine Running' : 'Engine Paused'}
              </span>
            </div>
            <h3 className="text-base font-bold text-white mt-0.5 flex items-center gap-2">
              {selectedStrat.name}
            </h3>
          </div>
        </div>

        {onNavigateSettings && (
          <button
            type="button"
            onClick={onNavigateSettings}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-950/80 border border-slate-800 text-slate-300 hover:text-white hover:border-slate-700 transition cursor-pointer self-start sm:self-auto"
            title="Jump directly to Strategy Settings tab to edit parameters"
          >
            <Sliders className="w-3.5 h-3.5 text-indigo-400" />
            <span>Edit Settings</span>
            <ExternalLink className="w-3 h-3 text-slate-500" />
          </button>
        )}
      </div>

      {/* Description Text */}
      <div className="mt-3.5 text-xs text-slate-300 leading-relaxed bg-slate-950/40 border border-slate-800/60 rounded-xl p-3">
        <p className="flex items-start gap-2">
          <Sparkles className="w-4 h-4 text-teal-400 shrink-0 mt-0.5" />
          <span>{selectedStrat.description}</span>
        </p>
      </div>

      {/* Strategy Information Grid */}
      <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {/* Universe */}
        <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-3">
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px] font-medium">
            <Target className="w-3.5 h-3.5 text-teal-400" />
            <span>Universe</span>
          </div>
          <div className="mt-1 text-sm font-bold text-white font-mono">
            {tickers.length} stocks
          </div>
          <div className="text-[10px] text-slate-400 truncate mt-0.5" title={tickers.join(', ')}>
            {tickers.slice(0, 4).join(', ')}{tickers.length > 4 ? '…' : ''}
          </div>
        </div>

        {/* Top N Allocation */}
        <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-3">
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px] font-medium">
            <Sliders className="w-3.5 h-3.5 text-indigo-400" />
            <span>Holdings Limit</span>
          </div>
          <div className="mt-1 text-sm font-bold text-white font-mono">
            Top {topN} Stocks
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            Max concurrent
          </div>
        </div>

        {/* Max Position Size */}
        <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-3">
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px] font-medium">
            <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
            <span>Max Position</span>
          </div>
          <div className="mt-1 text-sm font-bold text-emerald-400 font-mono">
            ${Number(maxPos).toLocaleString('en-US')}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            Hard cap per ticker
          </div>
        </div>

        {/* Pilot Budget */}
        <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-3">
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px] font-medium">
            <DollarSign className="w-3.5 h-3.5 text-indigo-400" />
            <span>Pilot Budget</span>
          </div>
          <div className="mt-1 text-sm font-bold text-white font-mono">
            ${Number(pilotBudget).toLocaleString('en-US')}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            Total active ceiling
          </div>
        </div>

        {/* Market Regime Filter */}
        <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-3">
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px] font-medium">
            <ShieldCheck className="w-3.5 h-3.5 text-sky-400" />
            <span>Regime Filter</span>
          </div>
          <div className="mt-1 text-sm font-bold text-white font-mono flex items-center gap-1">
            {useRegime ? (
              <span className="text-emerald-400">QQQ &gt; {regimePeriod} EMA</span>
            ) : (
              <span className="text-amber-400">Bypassed</span>
            )}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            {useRegime ? 'Cash if Bearish' : 'Always Trade'}
          </div>
        </div>

        {/* Schedule & Routine Timers */}
        <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-3">
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px] font-medium">
            <Clock className="w-3.5 h-3.5 text-amber-400" />
            <span>Scan Timers</span>
          </div>
          <div className="mt-1 text-sm font-bold text-white font-mono">
            {closeTime} / {openTime}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            Buy ET / Sell ET
          </div>
        </div>
      </div>
    </div>
  );
}
