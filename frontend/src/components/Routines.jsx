import React, { useState, useEffect, useMemo } from 'react';
import { Play, Sunrise, Sunset, Loader2, CheckCircle2, AlertCircle, Clock, ShieldCheck, PauseCircle, Trash2, ArrowUpDown, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';

export default function Routines({
  onRunClose,
  onRunOpen,
  onTrigger,
  loadingRoutine,
  runningRoutine,
  logs: externalLogs = [],
  onClearLogs,
  isLive = false,
  env = 'paper',
}) {
  const [internalLogs, setInternalLogs] = useState(() => {
    try {
      const saved = localStorage.getItem('internal_action_logs');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [serverLogs, setServerLogs] = useState([]);
  const [daemonStatus, setDaemonStatus] = useState(null);
  const [config, setConfig] = useState(null);
  const [pageSize, setPageSize] = useState(10);
  const [currentPage, setCurrentPage] = useState(1);
  const [sortOrder, setSortOrder] = useState('newest_first'); // 'newest_first' | 'newest_last'

  useEffect(() => {
    try {
      localStorage.setItem('internal_action_logs', JSON.stringify(internalLogs));
    } catch {}
  }, [internalLogs]);
  const activeLoading = loadingRoutine || runningRoutine;

  const fetchStatusAndConfig = async () => {
    try {
      const [dRes, cRes, aRes] = await Promise.all([
        fetch('/api/trading/daemon-status'),
        fetch('/api/config'),
        fetch('/api/trading/activity-logs'),
      ]);
      if (dRes.ok) {
        const dData = await dRes.json();
        setDaemonStatus(dData);
      }
      if (cRes.ok) {
        const cData = await cRes.json();
        setConfig(cData);
      }
      if (aRes.ok) {
        const aData = await aRes.json();
        if (Array.isArray(aData)) {
          setServerLogs(aData);
        }
      }
    } catch (e) {
      console.error('Error fetching routine status:', e);
    }
  };

  useEffect(() => {
    fetchStatusAndConfig();
    const interval = setInterval(fetchStatusAndConfig, 5000);
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
      { id: Date.now() + Math.random(), time: new Date().toLocaleTimeString(), text, type },
      ...prev.slice(0, 499),
    ]);
  };

  const handleClearAllLogs = async () => {
    if (confirm('Clear all action output logs?')) {
      setInternalLogs([]);
      setServerLogs([]);
      try {
        localStorage.removeItem('internal_action_logs');
        await fetch('/api/trading/activity-logs/clear', { method: 'POST' });
      } catch {}
      if (onClearLogs) onClearLogs();
    }
  };

  // Combine and normalize external, internal, and server activity logs
  const allLogs = useMemo(() => {
    const normalizedExt = (externalLogs || []).map((l, idx) => {
      if (typeof l === 'string') {
        const timeMatch = l.match(/^\[(.*?)\]\s*(.*)$/);
        return {
          id: `ext-${idx}`,
          time: timeMatch ? timeMatch[1] : '',
          text: timeMatch ? timeMatch[2] : l,
          type: l.toLowerCase().includes('error') || l.toLowerCase().includes('fail')
            ? 'error'
            : l.toLowerCase().includes('completed') || l.toLowerCase().includes('success')
            ? 'success'
            : 'info',
        };
      }
      return l;
    });

    // Merge serverLogs, internal logs, and external logs
    const combined = [...serverLogs, ...internalLogs, ...normalizedExt];
    // Remove exact duplicate text+time if any
    const seen = new Set();
    const unique = [];
    for (const item of combined) {
      const cleanText = (item.text || '').replace(/^\[(CRON|MANUAL)\]\s*/, '');
      const key = `${item.time}-${cleanText}`;
      if (!seen.has(key)) {
        seen.add(key);
        unique.push(item);
      }
    }

    if (sortOrder === 'newest_last') {
      return [...unique].reverse();
    }
    return unique;
  }, [serverLogs, internalLogs, externalLogs, sortOrder]);

  const totalPages = Math.max(1, Math.ceil(allLogs.length / pageSize));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const pagedLogs = useMemo(() => {
    const start = (safeCurrentPage - 1) * pageSize;
    return allLogs.slice(start, start + pageSize);
  }, [allLogs, safeCurrentPage, pageSize]);

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

        {/* Paper-Exclusive Testing Toolbar (Hidden completely in LIVE mode) */}
        {!isLive && (
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

      {/* Routine Log Feed / Action Output */}
      {allLogs.length > 0 && (
        <div className="pt-2 border-t border-slate-800/60 mt-1">
          {/* Action Output Header & Controls */}
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">
                Action Output
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                {allLogs.length} {allLogs.length === 1 ? 'event' : 'events'}
              </span>
            </div>

            {/* Toolbar: Sort toggle, Page size, Pagination, Clear */}
            <div className="flex items-center gap-2 text-[11px]">
              {/* Sort Order Toggle */}
              <button
                onClick={() => setSortOrder((prev) => (prev === 'newest_first' ? 'newest_last' : 'newest_first'))}
                className="flex items-center gap-1 px-2 py-1 rounded bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 text-[10px] font-medium transition cursor-pointer"
                title="Toggle Sort Order"
              >
                <ArrowUpDown className="w-3 h-3 text-indigo-400" />
                <span>{sortOrder === 'newest_first' ? 'Newest First' : 'Oldest First'}</span>
              </button>

              {/* Page size dropdown */}
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setCurrentPage(1);
                }}
                className="bg-slate-800/80 border border-slate-700/60 rounded px-1.5 py-0.5 text-slate-300 text-[10px] font-mono focus:outline-none cursor-pointer"
              >
                <option value={5}>5 / page</option>
                <option value={10}>10 / page</option>
                <option value={25}>25 / page</option>
                <option value={50}>50 / page</option>
              </select>

              {/* Clear logs button */}
              <button
                onClick={handleClearAllLogs}
                className="flex items-center gap-1 px-2 py-1 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 hover:text-rose-300 text-[10px] font-medium transition border border-rose-500/20 cursor-pointer"
                title="Clear all activity history"
              >
                <Trash2 className="w-3 h-3" />
                <span>Clear</span>
              </button>
            </div>
          </div>

          {/* Log Window */}
          <div className="space-y-1.5 bg-slate-950/90 p-3 rounded-lg border border-slate-800/80 min-h-24 max-h-56 overflow-y-auto font-mono text-[11px]">
            {pagedLogs.map((l) => {
              const isCron = (l.source === 'SCHEDULED') || (l.text && l.text.startsWith('[CRON]'));
              const isManual = (l.source === 'MANUAL') || (l.text && l.text.startsWith('[MANUAL]'));
              const displayText = (l.text || '').replace(/^\[(CRON|MANUAL)\]\s*/, '');

              return (
                <div key={l.id} className="flex items-start space-x-2 py-0.5 border-b border-slate-900/50 last:border-0">
                  {l.time && <span className="text-slate-500 shrink-0 font-mono text-[10px] pt-0.5">[{l.time}]</span>}
                  
                  {isCron ? (
                    <span className="shrink-0 px-1 py-0.2 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-[9px] font-sans font-bold">
                      CRON
                    </span>
                  ) : isManual ? (
                    <span className="shrink-0 px-1 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[9px] font-sans font-bold">
                      MANUAL
                    </span>
                  ) : null}

                  {l.type === 'success' ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                  ) : l.type === 'error' ? (
                    <AlertCircle className="w-3.5 h-3.5 text-rose-400 shrink-0 mt-0.5" />
                  ) : (
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0 mt-1.5 mr-1 ml-0.5" />
                  )}

                  <span className={`break-all ${
                    l.type === 'success'
                      ? 'text-emerald-200'
                      : l.type === 'error'
                      ? 'text-rose-300'
                      : 'text-slate-300'
                  }`}>
                    {displayText}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Pagination Navigation Footer */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between text-[11px] text-slate-400 pt-2 px-1">
              <span>
                Page <strong className="text-slate-200 font-mono">{safeCurrentPage}</strong> of{' '}
                <strong className="text-slate-200 font-mono">{totalPages}</strong>
              </span>

              <div className="flex items-center space-x-1">
                <button
                  disabled={safeCurrentPage <= 1}
                  onClick={() => setCurrentPage(1)}
                  className="p-1 rounded bg-slate-800/60 hover:bg-slate-700/60 disabled:opacity-30 disabled:cursor-not-allowed transition cursor-pointer"
                  title="First Page"
                >
                  <ChevronsLeft className="w-3.5 h-3.5" />
                </button>
                <button
                  disabled={safeCurrentPage <= 1}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  className="p-1 rounded bg-slate-800/60 hover:bg-slate-700/60 disabled:opacity-30 disabled:cursor-not-allowed transition cursor-pointer"
                  title="Previous Page"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                </button>
                <button
                  disabled={safeCurrentPage >= totalPages}
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  className="p-1 rounded bg-slate-800/60 hover:bg-slate-700/60 disabled:opacity-30 disabled:cursor-not-allowed transition cursor-pointer"
                  title="Next Page"
                >
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
                <button
                  disabled={safeCurrentPage >= totalPages}
                  onClick={() => setCurrentPage(totalPages)}
                  className="p-1 rounded bg-slate-800/60 hover:bg-slate-700/60 disabled:opacity-30 disabled:cursor-not-allowed transition cursor-pointer"
                  title="Last Page"
                >
                  <ChevronsRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
