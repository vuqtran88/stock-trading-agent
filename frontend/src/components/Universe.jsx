import React, { useState, useEffect } from 'react';
import {
  Sliders,
  Plus,
  X,
  Save,
  AlertCircle,
  CheckCircle2,
  Play,
  Pause,
  Clock,
  Layers,
  Sparkles,
} from 'lucide-react';

const POPULAR_TICKERS = [
  'AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'AMD',
  'NFLX', 'PLTR', 'AVGO', 'SMCI', 'COIN', 'ARM', 'UBER', 'CRWD'
];

export default function Universe() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);
  const [newTickerInput, setNewTickerInput] = useState('');

  // Editable local state
  const [env, setEnv] = useState('paper');
  const [tickers, setTickers] = useState([]);
  const [maxPositionSize, setMaxPositionSize] = useState(1000);
  const [pilotBudget, setPilotBudget] = useState(5000);
  const [emaPeriod, setEmaPeriod] = useState(20);
  const [maxHoldings, setMaxHoldings] = useState(3);

  // Strategy Execution & Scheduling Controls
  const [activeStrategy, setActiveStrategy] = useState('overnight_drift');
  const [strategyEnabled, setStrategyEnabled] = useState(true);
  const [useRegimeFilter, setUseRegimeFilter] = useState(true);
  const [closeRoutineTime, setCloseRoutineTime] = useState('15:50');
  const [openRoutineTime, setOpenRoutineTime] = useState('09:28');
  const [availableStrategies, setAvailableStrategies] = useState([]);
  const [schwabData, setSchwabData] = useState(null);

  const fetchConfig = async () => {
    try {
      setLoading(true);
      const [res, sRes] = await Promise.all([
        fetch('/api/config'),
        fetch('/api/trading/schwab-status'),
      ]);
      if (res.ok) {
        const data = await res.json();
        setConfig(data);
        setEnv(data.env || 'paper');
        setTickers(data.tickers || []);
        setMaxPositionSize(data.max_position_size_usd || 1000);
        setPilotBudget(data.live_pilot_budget_usd || 5000);
        setEmaPeriod(data.regime_ema_period || 20);
        setMaxHoldings(data.top_n || 2);
        setActiveStrategy(data.active_strategy || 'overnight_drift');
        setStrategyEnabled(data.strategy_enabled ?? true);
        setUseRegimeFilter(data.use_regime_filter ?? true);
        setCloseRoutineTime(data.close_routine_time || '15:50');
        setOpenRoutineTime(data.open_routine_time || '09:28');
        setAvailableStrategies(data.available_strategies || []);
      }
      if (sRes.ok) {
        const sData = await sRes.json();
        setSchwabData(sData);
      }
    } catch (err) {
      console.error('Failed to load config or Schwab status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConfig();
  }, []);

  const handleAddTicker = (tickerToAdd) => {
    const sym = (tickerToAdd || newTickerInput).trim().toUpperCase();
    if (!sym) return;
    if (!tickers.includes(sym)) {
      setTickers([...tickers, sym]);
    }
    setNewTickerInput('');
  };

  const handleRemoveTicker = (sym) => {
    setTickers(tickers.filter((t) => t !== sym));
  };

  const handleSave = async (e) => {
    if (e) e.preventDefault();
    setSaving(true);
    setStatusMsg(null);

    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          env,
          tickers,
          max_position_size_usd: Number(maxPositionSize),
          live_pilot_budget_usd: Number(pilotBudget),
          regime_ema_period: Number(emaPeriod),
          top_n: Number(maxHoldings),
          active_strategy: activeStrategy,
          strategy_enabled: Boolean(strategyEnabled),
          use_regime_filter: Boolean(useRegimeFilter),
          close_routine_time: closeRoutineTime,
          open_routine_time: openRoutineTime,
        }),
      });

      const data = await res.json();
      if (res.ok) {
        setStatusMsg({ type: 'success', text: 'Strategy, timing & universe controls saved successfully!' });
        fetchConfig();
      } else {
        setStatusMsg({ type: 'error', text: data.detail || 'Failed to update config' });
      }
    } catch (err) {
      setStatusMsg({ type: 'error', text: 'Network error updating strategy configuration' });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-slate-400">
        Loading target universe & settings...
      </div>
    );
  }

  const selectedStratObj = availableStrategies.find((s) => s.id === activeStrategy);
  const isLive = env === 'live';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Sliders className="w-5 h-5 text-indigo-400" />
            Strategy Selection & Execution Controls
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Pick active quantitative strategies, start/stop automated execution, configure market scan times, and set guardrails.
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white font-medium px-4 py-2 rounded-xl text-sm transition-all shadow-lg shadow-emerald-500/20 disabled:opacity-50 cursor-pointer"
        >
          <Save className="w-4 h-4" />
          {saving ? 'Saving...' : 'Save All Changes'}
        </button>
      </div>

      {statusMsg && (
        <div
          className={`p-3 rounded-xl border text-sm flex items-center gap-2 ${
            statusMsg.type === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
              : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
          }`}
        >
          {statusMsg.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0" />
          )}
          <span>{statusMsg.text}</span>
        </div>
      )}

      {/* Target Trading Environment (PAPER vs LIVE) */}
      <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-2xl p-5 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
              Trading Execution Target Environment
            </span>
            <h3 className="text-sm font-bold text-white mt-0.5">
              Active Environment: <span className={isLive ? 'text-rose-400 font-mono' : 'text-emerald-400 font-mono'}>{env.toUpperCase()}</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {isLive
                ? 'Orders execute directly through your authenticated Charles Schwab brokerage account.'
                : 'Orders execute against the deterministic simulated paper ledger with zero financial risk.'}
            </p>
          </div>

          <div className="flex items-center gap-2 bg-slate-950/85 border border-slate-800 p-1.5 rounded-xl shrink-0">
            <button
              type="button"
              onClick={() => setEnv('paper')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                !isLive
                  ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              SIMULATED PAPER
            </button>
            <button
              type="button"
              onClick={() => {
                if (confirm('⚠️ Switch to LIVE Trading? All automated routine scans and orders will use real money.')) {
                  setEnv('live');
                }
              }}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                isLive
                  ? 'bg-rose-500 text-white shadow-md shadow-rose-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              LIVE SCHWAB BROKER
            </button>
          </div>
        </div>

        {/* Live Schwab Account Diagnostic Card */}
        {schwabData && (
          <div className="mt-4 pt-4 border-t border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2.5">
              <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                schwabData.connected ? 'bg-sky-400 shadow-[0_0_8px_rgba(56,189,248,0.7)] animate-pulse' : 'bg-rose-500'
              }`} />
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-slate-200">Charles Schwab Trader API</span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                    schwabData.connected ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                  }`}>
                    {schwabData.connected ? 'CONNECTED' : 'DISCONNECTED'}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  {schwabData.connected
                    ? `Account Hash: ${schwabData.account_hash_short || 'Active'} • Token: Secret Manager (${schwabData.has_refresh_token ? 'Refreshable' : 'Static'})`
                    : schwabData.error || 'Failed to authenticate with Schwab'}
                </p>
              </div>
            </div>

            {schwabData.connected && (
              <div className="flex items-center gap-4 bg-slate-950/80 border border-slate-800 px-3.5 py-2 rounded-xl">
                <div>
                  <span className="text-[10px] text-slate-500 block uppercase font-medium">Settled Cash</span>
                  <span className="text-sm font-bold font-mono text-emerald-400">
                    ${Number(schwabData.settled_cash || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="w-[1px] h-6 bg-slate-800" />
                <div>
                  <span className="text-[10px] text-slate-500 block uppercase font-medium">Open Positions</span>
                  <span className="text-sm font-bold font-mono text-white">
                    {schwabData.positions_count || 0}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* STRATEGY SELECTION & LIFECYCLE (Issue 1 & 2) */}
      <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-2xl p-5 shadow-xl space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800/80">
          <div>
            <span className="text-xs font-semibold text-indigo-400 uppercase tracking-wider flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5" />
              Automated Trading Engine Control
            </span>
            <h3 className="text-base font-bold text-white mt-0.5">Strategy Lifecycle & Model Selection</h3>
            <p className="text-xs text-slate-400">
              Control whether the scheduler executes trades in PAPER / LIVE and switch between trading models.
            </p>
          </div>

          {/* Master Start / Stop Toggle Switch */}
          <div className="flex items-center gap-3 bg-slate-950/80 border border-slate-800 p-2 rounded-2xl shrink-0">
            <button
              type="button"
              onClick={() => setStrategyEnabled(true)}
              className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                strategyEnabled
                  ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>ACTIVE / RUN</span>
            </button>
            <button
              type="button"
              onClick={() => setStrategyEnabled(false)}
              className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                !strategyEnabled
                  ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Pause className="w-3.5 h-3.5 fill-current" />
              <span>PAUSED / STOP</span>
            </button>
          </div>
        </div>

        {/* Strategy Selector & Timers Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* Strategy Picker Card */}
          <div className="space-y-3">
            <label className="block text-xs font-semibold text-slate-300">
              Active Strategy Model
            </label>
            <select
              value={activeStrategy}
              onChange={(e) => {
                setActiveStrategy(e.target.value);
                const strat = availableStrategies.find((s) => s.id === e.target.value);
                if (strat?.default_open_time) setOpenRoutineTime(strat.default_open_time);
                if (strat?.default_close_time) setCloseRoutineTime(strat.default_close_time);
              }}
              className="w-full bg-slate-950/90 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 cursor-pointer"
            >
              {availableStrategies.map((strat) => (
                <option key={strat.id} value={strat.id} disabled={strat.status === 'coming_soon'}>
                  {strat.name} {strat.status === 'coming_soon' ? '(Coming Soon)' : '✓ Active'}
                </option>
              ))}
            </select>

            {selectedStratObj && (
              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-indigo-300">{selectedStratObj.name}</span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                    {selectedStratObj.status.toUpperCase()}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  {selectedStratObj.description}
                </p>
              </div>
            )}
          </div>

          {/* Configurable Routine Times (Issue 2) */}
          <div className="space-y-3">
            <label className="block text-xs font-semibold text-slate-300 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-indigo-400" />
              Configurable Market Scan Timers (US Eastern Time)
            </label>

            <div className="grid grid-cols-2 gap-3">
              {/* Morning Open Routine Time */}
              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1.5">
                <span className="text-[11px] font-medium text-amber-400 block">Morning Exit Scan</span>
                <input
                  type="time"
                  value={openRoutineTime}
                  onChange={(e) => setOpenRoutineTime(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-amber-500"
                />
                <span className="text-[10px] text-slate-500 block">Default: 09:28 AM ET (Pre-open)</span>
              </div>

              {/* Afternoon Close Routine Time */}
              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1.5">
                <span className="text-[11px] font-medium text-indigo-400 block">Afternoon Entry Scan</span>
                <input
                  type="time"
                  value={closeRoutineTime}
                  onChange={(e) => setCloseRoutineTime(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                />
                <span className="text-[10px] text-slate-500 block">Default: 15:50 PM ET (10m pre-close)</span>
              </div>
            </div>

            <p className="text-[11px] text-slate-500 italic">
              These timers govern when the scheduler or background daemon executes scans. Changes take effect on the next check.
            </p>
          </div>
        </div>
      </div>

      {/* Target Tickers Section */}
      <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-2xl p-5 shadow-xl">
        <h3 className="text-sm font-semibold text-slate-200 mb-2">Target Stock Universe ({tickers.length})</h3>
        <p className="text-xs text-slate-400 mb-4">
          Stocks screened daily for top momentum rank prior to the entry scan.
        </p>

        {/* Selected chips */}
        <div className="flex flex-wrap gap-2 mb-4">
          {tickers.map((sym) => (
            <span
              key={sym}
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 font-mono font-medium text-xs shadow-sm hover:bg-indigo-500/20 transition-all"
            >
              {sym}
              <button
                type="button"
                onClick={() => handleRemoveTicker(sym)}
                className="text-indigo-400 hover:text-rose-400 transition-colors cursor-pointer"
                title={`Remove ${sym}`}
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </span>
          ))}
          {tickers.length === 0 && (
            <span className="text-xs text-slate-500 italic">No tickers in universe. Add symbols below.</span>
          )}
        </div>

        {/* Add custom ticker input */}
        <div className="flex gap-2 max-w-sm mb-4">
          <input
            type="text"
            value={newTickerInput}
            onChange={(e) => setNewTickerInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleAddTicker();
              }
            }}
            placeholder="Add ticker (e.g. QCOM)"
            className="flex-1 bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white uppercase focus:outline-none focus:border-indigo-500"
          />
          <button
            type="button"
            onClick={() => handleAddTicker()}
            className="flex items-center gap-1 bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded-xl text-xs font-medium transition-colors cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            Add
          </button>
        </div>

        {/* Quick add popular suggestions */}
        <div>
          <span className="text-[11px] text-slate-400 font-medium mr-2">Quick Add:</span>
          <div className="inline-flex flex-wrap gap-1.5 mt-1">
            {POPULAR_TICKERS.filter((sym) => !tickers.includes(sym)).map((sym) => (
              <button
                key={sym}
                type="button"
                onClick={() => handleAddTicker(sym)}
                className="px-2 py-0.5 rounded-md bg-slate-800/80 hover:bg-slate-700 border border-slate-700/50 text-slate-300 font-mono text-[11px] transition-colors cursor-pointer"
              >
                + {sym}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Safety & Risk Controls */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Position & Budget limits */}
        <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
          <h3 className="text-sm font-semibold text-slate-200">Capital & Sizing Guardrails</h3>

          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-400">Max Position Size</span>
              <span className="font-mono text-white font-medium">${Number(maxPositionSize).toLocaleString()}</span>
            </div>
            <input
              type="range"
              min="100"
              max="5000"
              step="50"
              value={maxPositionSize}
              onChange={(e) => setMaxPositionSize(e.target.value)}
              className="w-full accent-indigo-500 cursor-pointer"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              Hard ceiling per stock position. Limits single-name shock exposure.
            </p>
          </div>

          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-400">Total Pilot Portfolio Budget</span>
              <span className="font-mono text-white font-medium">${Number(pilotBudget).toLocaleString()}</span>
            </div>
            <input
              type="range"
              min="1000"
              max="25000"
              step="500"
              value={pilotBudget}
              onChange={(e) => setPilotBudget(e.target.value)}
              className="w-full accent-indigo-500 cursor-pointer"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              Total maximum capital allocated across all active paper/pilot positions.
            </p>
          </div>

          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-400">Top N Stocks (Simultaneous Holdings)</span>
              <span className="font-mono text-white font-medium">{maxHoldings} tickers</span>
            </div>
            <input
              type="range"
              min="1"
              max="5"
              step="1"
              value={maxHoldings}
              onChange={(e) => setMaxHoldings(e.target.value)}
              className="w-full accent-indigo-500 cursor-pointer"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              Max number of simultaneous overnight stocks entered on any given day.
            </p>
          </div>
        </div>

        {/* Market Regime Filter */}
        <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800/80">
            <div>
              <h3 className="text-sm font-semibold text-slate-200">Market Regime Filter</h3>
              <p className="text-[11px] text-slate-400">QQQ Trend Filter Guardrail</p>
            </div>
            {/* Enable/Disable Toggle */}
            <div className="flex items-center gap-1.5 p-1 rounded-xl bg-slate-950 border border-slate-800">
              <button
                type="button"
                onClick={() => setUseRegimeFilter(true)}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition cursor-pointer ${
                  useRegimeFilter
                    ? 'bg-emerald-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                ENABLED
              </button>
              <button
                type="button"
                onClick={() => setUseRegimeFilter(false)}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition cursor-pointer ${
                  !useRegimeFilter
                    ? 'bg-amber-500 text-slate-950 shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                BYPASSED
              </button>
            </div>
          </div>

          {!useRegimeFilter && (
            <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-start gap-2">
              <span className="text-sm">⚠️</span>
              <div>
                <strong className="font-semibold">Regime Filter is BYPASSED:</strong>
                <p className="text-[11px] text-amber-200/80 mt-0.5">
                  Overnight drift buy orders will execute regardless of whether QQQ is above or below its EMA. Use this for testing and pilot execution during bearish regimes.
                </p>
              </div>
            </div>
          )}

          <div className={!useRegimeFilter ? 'opacity-50 pointer-events-none' : ''}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-400">QQQ Trend EMA Period</span>
              <span className="font-mono text-white font-medium">{emaPeriod} Days</span>
            </div>
            <input
              type="range"
              min="5"
              max="50"
              step="1"
              value={emaPeriod}
              onChange={(e) => setEmaPeriod(e.target.value)}
              disabled={!useRegimeFilter}
              className="w-full accent-indigo-500 cursor-pointer"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              When QQQ closes below this EMA, new entries are strictly skipped to preserve capital.
            </p>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800/80 text-xs space-y-1.5">
            <span className="font-semibold text-slate-300">How Regime Filtering Works:</span>
            <p className="text-slate-400 leading-relaxed text-[11px]">
              The Overnight Anomaly historically has positive expected value during bullish market regimes. If QQQ closes below its
              configurable {emaPeriod}-day EMA, buy orders at market close will stand down automatically, avoiding heavy downside market drift.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
