import React, { useState, useEffect } from 'react';
import { Play, Sunrise, Sunset, Loader2, CheckCircle2, AlertCircle, Clock, ShieldCheck, PauseCircle } from 'lucide-react';

export default function Routines({
  onRunClose,
  onRunOpen,
  onTrigger,
  loadingRoutine,
  runningRoutine,
  logs: externalLogs,
  isLive = false,
  env = 'paper',
}) {
  const [internalLogs, setInternalLogs] = useState([]);
  const [daemonStatus, setDaemonStatus] = useState(null);
  const [config, setConfig] = useState(null);
  const activeLoading = loadingRoutine || runningRoutine;

  const fetchStatusAndConfig = async () => {
    try {
      const [dRes, cRes] = await Promise.all([
        fetch('/api/trading/daemon-status'),
        fetch('/api/config'),
      ]);
      if (dRes.ok) {
        const dData = await dRes.json();
        setDaemonStatus(dData);
      }
      if (cRes.ok) {
        const cData = await cRes.json();
        setConfig(cData);
      }
    } catch (e) {
      console.error('Error fetching routine status:', e);
    }
  };

  useEffect(() => {
    fetchStatusAndConfig();
    const interval = setInterval(fetchStatusAndConfig, 8000);
    return () => clearInterval(interval);
  }, []);

  const handleRunClose = async () => {
    if (isLive) {
      const confirmRun = confirm(
        '⚠️ LIVE REAL MONEY ORDER: Are you sure you want to trigger the Afternoon Close Buy Routine now on your live Schwab broker account?'
      );
      if (!confirmRun) return;
    }

    try {
      if (onRunClose) {
        const res = await onRunClose();
        addLog(res?.message || 'Close Buy Routine executed', 'success');
      } else if (onTrigger) {
        await onTrigger('buy');
      }
    } catch (err) {
      addLog(err.message || 'Close Routine failed', 'error');
    }
  };

  const handleRunOpen = async () => {
    if (isLive) {
      const confirmRun = confirm(
        '⚠️ LIVE REAL MONEY ORDER: Are you sure you want to trigger the Morning Open Sell Routine now on your live Schwab broker account?'
      );
      if (!confirmRun) return;
    }

    try {
      if (onRunOpen) {
        const res = await onRunOpen();
        addLog(res?.message || 'Open Sell Routine executed', 'success');
      } else if (onTrigger) {
        await onTrigger('sell');
      }
    } catch (err) {
      addLog(err.message || 'Open Routine failed', 'error');
    }
  };

  const handleSeedPositions = async () => {
    if (isLive) return;
    try {
      addLog('Seeding mock positions (AAPL 4 sh, NVDA 8 sh)...', 'info');
      const res = await fetch('/api/trading/seed-test-positions', { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        addLog(data.message || 'Seeded 2 positions', 'success');
        if (onTrigger) onTrigger('refresh');
      } else {
        addLog(data.detail || 'Seeding failed', 'error');
      }
    } catch (err) {
      addLog('Network error seeding positions', 'error');
    }
  };

  const handleFastForwardCycle = async () => {
    if (isLive) return;
    try {
      addLog('⚡ Initiating 24H Fast-Forward Simulation...', 'info');
      const res = await fetch('/api/trading/run-fast-forward-cycle', { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        addLog(data.message || '24H Cycle complete!', 'success');
        if (onTrigger) onTrigger('refresh');
      } else {
        addLog(data.detail || 'Simulation error', 'error');
      }
    } catch (err) {
      addLog('Network error in fast-forward simulation', 'error');
    }
  };

  const handleResetLedger = async () => {
    if (isLive) return;
    if (!confirm('Reset paper portfolio to clean state ($10,000 cash, 0 positions)?')) return;
    try {
      addLog('Resetting paper portfolio to initial baseline...', 'info');
      const res = await fetch('/api/trading/reset-paper-ledger', { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        addLog(data.message || 'Portfolio reset to $10,000.00 cash', 'success');
        if (onTrigger) onTrigger('refresh');
      } else {
        addLog(data.detail || 'Reset failed', 'error');
      }
    } catch (err) {
      addLog('Network error resetting portfolio', 'error');
    }
  };

  const addLog = (text, type = 'info') => {
    setInternalLogs((prev) => [
      { time: new Date().toLocaleTimeString(), text, type },
      ...prev.slice(0, 9),
    ]);
  };

  const isPaused = config?.strategy_enabled === false;
  const openTimeDisplay = config?.open_routine_time || '09:28';
  const closeTimeDisplay = config?.close_routine_time || '15:50';

  return (
    <div className="glass-panel p-5 rounded-2xl space-y-4">
      {/* 1. Header with Title & Contextual Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-sm text-white">Automated Routine Action Station</h3>
            <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${
              isLive
                ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
            }`}>
              {isLive ? 'LIVE BROKER TARGET' : 'PAPER SANDBOX'}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            {isLive 
              ? 'Real-money routine executions routed to Charles Schwab broker' 
              : 'Simulated trade execution sandbox with deterministic fast-forward'}
          </p>
        </div>

        {/* Paper-Exclusive Testing Toolbar (Hidden in LIVE for safety) */}
        {!isLive ? (
          <div className="flex items-center gap-2">
            <button
              onClick={handleSeedPositions}
              className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition cursor-pointer border border-slate-700/60"
              title="Pre-seed AAPL and NVDA positions into paper ledger to test morning liquidations"
            >
              🌱 Seed Holdings
            </button>
            <button
              onClick={handleResetLedger}
              className="px-2.5 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-medium transition cursor-pointer"
              title="Reset paper portfolio back to $10,000 cash and 0 holdings"
            >
              🔄 Reset
            </button>
            <button
              onClick={handleFastForwardCycle}
              className="px-2.5 py-1.5 rounded-lg bg-teal-500/20 hover:bg-teal-500/30 text-teal-300 border border-teal-500/40 text-xs font-semibold transition cursor-pointer shadow-sm"
              title="Fast-forward full 24H cycle in 2 seconds"
            >
              ⚡ Fast-Forward 24H
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
            <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
            <span>Sandbox Seeding & Fast-Forward Disabled in LIVE</span>
          </div>
        )}
      </div>

      {/* 2. Distinct Informational Status Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-3.5 py-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs">
        {/* Status Pill */}
        <div className="flex items-center gap-2">
          <span className="text-slate-400 font-medium">Scheduler State:</span>
          {isPaused ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-400 text-[11px] font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
              EXECUTION PAUSED
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[11px] font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              AUTO-ACTIVE
            </span>
          )}
        </div>

        {/* Timing Information */}
        <div className="flex items-center gap-3 text-slate-400 text-[11px]">
          <span>
            Morning Exit: <strong className="font-mono text-amber-300">{openTimeDisplay} ET</strong>
          </span>
          <span className="text-slate-700">•</span>
          <span>
            Afternoon Entry: <strong className="font-mono text-indigo-300">{closeTimeDisplay} ET</strong>
          </span>
        </div>
      </div>

      {/* Routine Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        {/* Run Close Routine */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 flex flex-col justify-between space-y-3">
          <div className="flex items-start justify-between">
            <div className="flex items-center space-x-2.5">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                <Sunset className="w-4 h-4" />
              </div>
              <div>
                <h4 className="font-semibold text-xs text-white">Afternoon Buy Routine ({closeTimeDisplay} ET)</h4>
                <p className="text-[11px] text-slate-400">
                  {isLive ? 'Places live real-money market orders' : 'Scan QQQ regime & paper enter top dips'}
                </p>
              </div>
            </div>
          </div>
          <button
            onClick={handleRunClose}
            disabled={Boolean(activeLoading)}
            className={`w-full flex items-center justify-center space-x-2 py-2 rounded-lg text-white text-xs font-semibold shadow-md transition cursor-pointer disabled:opacity-50 ${
              isLive ? 'bg-rose-600 hover:bg-rose-500' : 'bg-indigo-600 hover:bg-indigo-500'
            }`}
          >
            {activeLoading === 'buy' || activeLoading === 'close' ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5" />
            )}
            <span>{isLive ? 'Execute LIVE Afternoon Buy Routine' : 'Run Afternoon Buy Scan'}</span>
          </button>
        </div>

        {/* Run Open Routine */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 flex flex-col justify-between space-y-3">
          <div className="flex items-start justify-between">
            <div className="flex items-center space-x-2.5">
              <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
                <Sunrise className="w-4 h-4" />
              </div>
              <div>
                <h4 className="font-semibold text-xs text-white">Morning Sell Routine ({openTimeDisplay} ET)</h4>
                <p className="text-[11px] text-slate-400">
                  {isLive ? 'Places live real-money exit orders at open' : 'Liquidate overnight holdings at open'}
                </p>
              </div>
            </div>
          </div>
          <button
            onClick={handleRunOpen}
            disabled={Boolean(activeLoading)}
            className="w-full flex items-center justify-center space-x-2 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white text-xs font-semibold shadow-md transition cursor-pointer"
          >
            {activeLoading === 'sell' || activeLoading === 'open' ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5" />
            )}
            <span>{isLive ? 'Execute LIVE Morning Sell Routine' : 'Run Morning Sell Routine'}</span>
          </button>
        </div>
      </div>

      {/* Routine Log Feed */}
      {(externalLogs?.length > 0 || internalLogs?.length > 0) && (
        <div className="pt-2">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Action Output</div>
          <div className="space-y-1 bg-slate-950/80 p-3 rounded-lg border border-slate-800/80 max-h-36 overflow-y-auto font-mono text-[11px]">
            {externalLogs?.map((logStr, idx) => (
              <div key={`ext-${idx}`} className="text-slate-300">
                {logStr}
              </div>
            ))}
            {internalLogs?.map((l, idx) => (
              <div key={`int-${idx}`} className="flex items-start space-x-2">
                <span className="text-slate-500">{l.time}</span>
                {l.type === 'success' ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                ) : (
                  <AlertCircle className="w-3.5 h-3.5 text-rose-400 shrink-0 mt-0.5" />
                )}
                <span className={l.type === 'success' ? 'text-slate-300' : 'text-rose-300'}>{l.text}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
