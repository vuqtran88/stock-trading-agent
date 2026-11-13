import React, { useState, useEffect, useRef } from 'react';
import EarningsLab from './EarningsLab';
import { 
  Bot, 
  Sparkles, 
  TrendingUp, 
  TrendingDown, 
  ShieldAlert, 
  Search, 
  CheckCircle2, 
  Loader2, 
  Target, 
  Clock, 
  Layers, 
  ArrowRight,
  History as HistoryIcon,
  Trash2,
  Calendar,
  ChevronRight,
  FileText
} from 'lucide-react';

const SUGGESTED_TICKERS = ['NVDA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META', 'TSLA', 'QQQ'];

const PERSONA_ORDER = [
  'Fundamental Analyst',
  'Technical Analyst',
  'Sentiment Analyst',
  'Bearish Risk Advocate',
];

const PERSONA_WEIGHTS = {
  'Fundamental Analyst': { weight: 0.35, pct: '35%', shortLabel: 'Fundamental', metricLabel: 'Score' },
  'Technical Analyst': { weight: 0.25, pct: '25%', shortLabel: 'Technical', metricLabel: 'Score' },
  'Sentiment Analyst': { weight: 0.20, pct: '20%', shortLabel: 'Sentiment', metricLabel: 'Score' },
  'Bearish Risk Advocate': { weight: 0.20, pct: '20%', shortLabel: 'Risk Safety', metricLabel: 'Risk Safety' },
};

export default function AgentCopilot() {
  const [activeSubTab, setActiveSubTab] = useState('committee'); // 'committee' | 'earnings_lab'
  const [ticker, setTicker] = useState('NVDA');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [streamStatus, setStreamStatus] = useState('');
  const [companySnapshot, setCompanySnapshot] = useState(null);
  const [personaReports, setPersonaReports] = useState([]);
  const [finalDossier, setFinalDossier] = useState(null);
  const [screenerResults, setScreenerResults] = useState(null);
  const [isScreening, setIsScreening] = useState(false);

  // History State
  const [historyList, setHistoryList] = useState([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [filterTicker, setFilterTicker] = useState('');

  const eventSourceRef = useRef(null);

  const fetchHistory = async () => {
    setHistoryLoading(true);
    try {
      const url = filterTicker 
        ? `/api/agent/history?ticker=${encodeURIComponent(filterTicker)}` 
        : '/api/agent/history';
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setHistoryList(data);
      }
    } catch (err) {
      console.error('Failed to load analysis history', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [filterTicker]);

  const handleStartAnalysis = (symbolToAnalyze) => {
    const symbol = (symbolToAnalyze || ticker || '').trim().toUpperCase();
    if (!symbol) return;

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setIsAnalyzing(true);
    setSelectedHistoryId(null);
    setStreamStatus(`Connecting to Investment Committee for ${symbol}...`);
    setCompanySnapshot(null);
    setPersonaReports([]);
    setFinalDossier(null);

    const sse = new EventSource(`/api/agent/stream?ticker=${encodeURIComponent(symbol)}`);
    eventSourceRef.current = sse;

    sse.addEventListener('status', (e) => {
      try {
        const payload = JSON.parse(e.data);
        setStreamStatus(payload.data?.message || 'Processing...');
      } catch (err) {
        console.error(err);
      }
    });

    sse.addEventListener('data_ready', (e) => {
      try {
        const payload = JSON.parse(e.data);
        setCompanySnapshot(payload.data);
      } catch (err) {
        console.error(err);
      }
    });

    sse.addEventListener('persona_report', (e) => {
      try {
        const payload = JSON.parse(e.data);
        if (payload.data) {
          setPersonaReports((prev) => {
            const existing = prev.filter(p => p.persona_name !== payload.data.persona_name);
            const updated = [...existing, payload.data];
            // Sort by deterministic defined order
            return updated.sort((a, b) => {
              const idxA = PERSONA_ORDER.indexOf(a.persona_name);
              const idxB = PERSONA_ORDER.indexOf(b.persona_name);
              return (idxA !== -1 ? idxA : 99) - (idxB !== -1 ? idxB : 99);
            });
          });
        }
      } catch (err) {
        console.error(err);
      }
    });

    sse.addEventListener('final_dossier', (e) => {
      try {
        const payload = JSON.parse(e.data);
        setFinalDossier(payload.data);
      } catch (err) {
        console.error(err);
      }
    });

    sse.addEventListener('complete', () => {
      setIsAnalyzing(false);
      setStreamStatus('Committee deliberation completed.');
      sse.close();
      fetchHistory(); // Refresh history list
    });

    sse.addEventListener('error', (e) => {
      console.warn('SSE stream error/closed', e);
      setIsAnalyzing(false);
      sse.close();
    });
  };

  const handleSelectHistoryRecord = async (record) => {
    setSelectedHistoryId(record.id);
    setTicker(record.ticker);
    setFinalDossier(record.dossier);
    const sortedReports = (record.persona_reports || []).slice().sort((a, b) => {
      const idxA = PERSONA_ORDER.indexOf(a.persona_name);
      const idxB = PERSONA_ORDER.indexOf(b.persona_name);
      return (idxA !== -1 ? idxA : 99) - (idxB !== -1 ? idxB : 99);
    });
    setPersonaReports(sortedReports);
    setCompanySnapshot({
      ticker: record.ticker,
      name: record.company_name,
      sector: record.company_data?.fundamentals?.sector || 'N/A',
      current_price: record.company_data?.fundamentals?.current_price,
    });
  };

  const handleDeleteHistory = async (e, recordId) => {
    e.stopPropagation();
    try {
      const res = await fetch(`/api/agent/history/${recordId}`, { method: 'DELETE' });
      if (res.ok) {
        if (selectedHistoryId === recordId) {
          setSelectedHistoryId(null);
          setFinalDossier(null);
          setPersonaReports([]);
        }
        fetchHistory();
      }
    } catch (err) {
      console.error('Failed to delete analysis history', err);
    }
  };

  const handleRunScreener = async () => {
    setIsScreening(true);
    try {
      const res = await fetch('/api/agent/screen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers: SUGGESTED_TICKERS, limit: 3 }),
      });
      if (res.ok) {
        const data = await res.json();
        setScreenerResults(data);
      }
    } catch (err) {
      console.error('Failed to run universe screener', err);
    } finally {
      setIsScreening(false);
    }
  };

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const getVerdictBadge = (verdict) => {
    switch (verdict) {
      case 'STRONG BUY':
        return 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40';
      case 'ACCUMULATE':
        return 'bg-teal-500/20 text-teal-300 border border-teal-500/40';
      case 'HOLD':
        return 'bg-amber-500/20 text-amber-300 border border-amber-500/40';
      case 'AVOID':
        return 'bg-rose-500/20 text-rose-400 border border-rose-500/40';
      default:
        return 'bg-slate-700 text-slate-300';
    }
  };

  return (
    <div className="space-y-6">
      {/* Sub-view Navigation Pill Bar */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
        <button
          onClick={() => setActiveSubTab('committee')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeSubTab === 'committee'
              ? 'bg-teal-500/15 text-teal-300 border border-teal-500/30 shadow-sm'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <Bot className="w-4 h-4 text-teal-400" />
          Investment Committee
        </button>

        <button
          onClick={() => setActiveSubTab('earnings_lab')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeSubTab === 'earnings_lab'
              ? 'bg-sky-500/15 text-sky-300 border border-sky-500/30 shadow-sm'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <FileText className="w-4 h-4 text-sky-400" />
          Earnings Intelligence Lab
        </button>
      </div>

      {activeSubTab === 'earnings_lab' ? (
        <EarningsLab />
      ) : (
        <>
          {/* Header Banner */}
          <div className="glass-panel p-6 rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-900 via-slate-900/90 to-teal-950/30 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-teal-500/20 border border-teal-500/30 rounded-xl text-teal-400">
                  <Bot className="w-5 h-5" />
                </div>
                <h2 className="text-xl font-bold text-white tracking-tight">AI Investment Committee Copilot</h2>
              </div>
              <p className="text-sm text-slate-400 mt-1">
                Autonomous multi-agent committee: <strong>Fundamental Analyst</strong>, <strong>Technical Analyst</strong>, <strong>Sentiment Analyst</strong>, and <strong>Bearish Risk Advocate</strong> synthesized by the <strong>Chief Investment Officer (CIO)</strong>.
              </p>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-3 w-full md:w-auto">
              <button
                onClick={handleRunScreener}
                disabled={isScreening || isAnalyzing}
                className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-white rounded-xl text-sm font-semibold transition-all disabled:opacity-50 cursor-pointer shadow-sm"
              >
                {isScreening ? <Loader2 className="w-4 h-4 animate-spin text-teal-400" /> : <Layers className="w-4 h-4 text-teal-400" />}
                Screen Tracked Universe
              </button>
            </div>
          </div>

      {/* Main Workspace Grid (Left: Active Deliberation / Dossier, Right: History Drawer) */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
        
        {/* Left 3 Columns: Analysis Controls & Dossier View */}
        <div className="lg:col-span-3 space-y-6">
          
          {/* Ticker Search Bar */}
          <div className="glass-panel p-4 rounded-xl border border-slate-800 flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                onKeyDown={(e) => e.key === 'Enter' && handleStartAnalysis(ticker)}
                placeholder="Enter US Ticker (e.g. NVDA, AAPL, MSFT)..."
                className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 transition-colors"
              />
            </div>

            {/* Quick Tickers */}
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-xs text-slate-500 mr-1">Quick:</span>
              {SUGGESTED_TICKERS.map((sym) => (
                <button
                  key={sym}
                  onClick={() => {
                    setTicker(sym);
                    handleStartAnalysis(sym);
                  }}
                  className="px-2.5 py-1 bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 rounded-lg text-xs font-mono transition-colors cursor-pointer"
                >
                  {sym}
                </button>
              ))}
            </div>

            <button
              onClick={() => handleStartAnalysis(ticker)}
              disabled={isAnalyzing || !ticker}
              className="flex items-center gap-2 px-5 py-2 bg-teal-500 hover:bg-teal-400 text-slate-950 rounded-xl text-sm font-bold transition-all disabled:opacity-50 cursor-pointer shadow-lg shadow-teal-500/20"
            >
              {isAnalyzing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Deliberating...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Convene Committee
                </>
              )}
            </button>
          </div>

          {/* Stream Status Bar */}
          {isAnalyzing && (
            <div className="p-3.5 rounded-xl border border-teal-500/30 bg-teal-500/10 flex items-center justify-between text-teal-300 text-xs animate-pulse">
              <div className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>{streamStatus}</span>
              </div>
              {companySnapshot && (
                <span className="font-semibold text-white">
                  {companySnapshot.name} ({companySnapshot.ticker}) — ${companySnapshot.current_price?.toFixed(2)}
                </span>
              )}
            </div>
          )}

          {/* Reviewing Saved Record Alert Banner */}
          {selectedHistoryId && !isAnalyzing && (
            <div className="p-3.5 rounded-xl border border-slate-800 bg-slate-900/80 flex items-center justify-between text-xs text-slate-300">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-teal-400" />
                <span>Reviewing historical analysis snapshot <strong>#{selectedHistoryId}</strong></span>
              </div>
              <button
                onClick={() => {
                  setSelectedHistoryId(null);
                  setFinalDossier(null);
                  setPersonaReports([]);
                }}
                className="text-xs text-teal-400 hover:underline cursor-pointer"
              >
                Clear / New Query
              </button>
            </div>
          )}

          {/* Screener Results Panel (if triggered) */}
          {screenerResults && (
            <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-teal-400" />
                  Universe Screener: Top Conviction Picks
                </h3>
                <span className="text-xs text-slate-400">
                  Evaluated {screenerResults.screened_count} Equities
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {screenerResults.top_picks?.map((pick) => (
                  <div 
                    key={pick.ticker} 
                    onClick={() => { setTicker(pick.ticker); handleStartAnalysis(pick.ticker); }}
                    className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 hover:border-teal-500/40 transition-all cursor-pointer group"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="font-mono font-bold text-white text-lg group-hover:text-teal-400 transition-colors">
                        {pick.ticker}
                      </div>
                      <span className={`px-2 py-0.5 rounded-md text-xs font-bold ${getVerdictBadge(pick.verdict)}`}>
                        {pick.verdict}
                      </span>
                    </div>
                    <div className="text-xs text-slate-400 mb-2">{pick.company_name}</div>
                    <p className="text-xs text-slate-300 line-clamp-3 leading-relaxed mb-3">
                      {pick.executive_thesis}
                    </p>
                    <div className="flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-800/80 pt-2">
                      <span>Conviction: <strong className="text-teal-400 font-mono">{pick.conviction_score}/10</strong></span>
                      <span className="flex items-center gap-1 text-teal-400 group-hover:translate-x-0.5 transition-transform">
                        Deep Dive <ArrowRight className="w-3 h-3" />
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* CIO Final Investment Dossier */}
          {finalDossier && (
            <div className="glass-panel p-6 rounded-2xl border border-teal-500/40 bg-gradient-to-b from-slate-900 via-slate-900/90 to-teal-950/20 shadow-xl space-y-6">
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 border-b border-slate-800/80 pb-4">
                <div>
                  <div className="flex items-center gap-3">
                    <h3 className="text-2xl font-black text-white font-mono">{finalDossier.ticker}</h3>
                    <span className="text-base text-slate-400 font-medium">{finalDossier.company_name}</span>
                    <span className={`px-3 py-1 rounded-lg text-xs font-black tracking-wide ${getVerdictBadge(finalDossier.verdict)}`}>
                      {finalDossier.verdict}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1 flex items-center gap-2">
                    <Clock className="w-3.5 h-3.5 text-teal-400" />
                    Suggested Horizon: <strong className="text-slate-200">{finalDossier.suggested_horizon}</strong>
                  </p>
                </div>

                <div className="flex items-center gap-4 bg-slate-950/80 px-4 py-2 rounded-xl border border-slate-800">
                  <div className="text-right">
                    <div className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Conviction Rating</div>
                    <div className="text-2xl font-black font-mono text-teal-400">
                      {finalDossier.conviction_score} <span className="text-xs text-slate-500">/ 10</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Conviction Score Formula & Breakdown */}
              <div className="p-4 rounded-xl border border-teal-500/25 bg-slate-950/70 space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 border-b border-slate-800/80 pb-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-teal-400">
                    Conviction Score Formula &amp; Weighted Breakdown
                  </span>
                  <span className="text-[11px] font-mono text-slate-400">
                    0.35×Fundamental + 0.25×Technical + 0.20×Sentiment + 0.20×Risk Safety = <strong className="text-teal-300">{finalDossier.conviction_score}/10</strong>
                  </span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
                  {PERSONA_ORDER.map((pName) => {
                    const meta = PERSONA_WEIGHTS[pName];
                    const reportMatch = personaReports.find((r) => r.persona_name === pName);
                    const rawScore =
                      finalDossier.persona_scores?.[pName] ??
                      reportMatch?.score ??
                      null;
                    const contrib = rawScore !== null ? (Number(rawScore) * meta.weight).toFixed(2) : null;
                    return (
                      <div
                        key={pName}
                        className="p-2.5 rounded-lg border border-slate-800/90 bg-slate-900/70 flex flex-col justify-between"
                      >
                        <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
                          <span className="font-semibold text-slate-200 truncate">{meta.shortLabel}</span>
                          <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-teal-300">
                            {meta.pct}
                          </span>
                        </div>
                        {rawScore !== null ? (
                          <div className="flex items-baseline justify-between font-mono">
                            <span className="text-xs text-slate-400">
                              {Number(rawScore).toFixed(1)}/10
                            </span>
                            <span className="text-sm font-bold text-teal-400">
                              +{contrib} pts
                            </span>
                          </div>
                        ) : (
                          <span className="text-xs font-mono text-slate-500">N/A</span>
                        )}
                      </div>
                    );
                  })}
                </div>

                {finalDossier.conviction_score_breakdown?.length > 0 && (
                  <ul className="text-xs text-slate-300 space-y-1 list-disc list-inside pt-1 border-t border-slate-800/60">
                    {finalDossier.conviction_score_breakdown.map((item, idx) => (
                      <li key={idx} className="leading-relaxed">{item}</li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Executive Thesis */}
              <div className="space-y-1.5">
                <h4 className="text-xs font-bold uppercase tracking-wider text-teal-400">Executive Investment Thesis</h4>
                <p className="text-sm text-slate-200 leading-relaxed bg-slate-950/50 p-4 rounded-xl border border-slate-800/80">
                  {finalDossier.executive_thesis}
                </p>
              </div>

              {/* Action Zones */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-3.5 rounded-xl border border-slate-800 bg-slate-950/60 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Target className="w-4 h-4 text-emerald-400" />
                    <span className="text-xs text-slate-400 font-semibold">Target Entry Zone</span>
                  </div>
                  <span className="font-mono text-sm font-bold text-emerald-400">{finalDossier.target_entry_zone || 'Market / Pullback'}</span>
                </div>
                <div className="p-3.5 rounded-xl border border-slate-800 bg-slate-950/60 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-rose-400" />
                    <span className="text-xs text-slate-400 font-semibold">Recommended Stop-Loss</span>
                  </div>
                  <span className="font-mono text-sm font-bold text-rose-400">{finalDossier.stop_loss_level || 'N/A'}</span>
                </div>
              </div>

              {/* Catalysts & Risks Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                <div className="p-4 rounded-xl border border-emerald-950/50 bg-emerald-950/10 space-y-2">
                  <h5 className="text-xs font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
                    <TrendingUp className="w-3.5 h-3.5" /> Key Catalysts & Upside Drivers
                  </h5>
                  <ul className="text-xs text-slate-300 space-y-1.5 list-disc list-inside">
                    {finalDossier.key_catalysts?.map((c, i) => (
                      <li key={i} className="leading-relaxed">{c}</li>
                    ))}
                  </ul>
                </div>

                <div className="p-4 rounded-xl border border-rose-950/50 bg-rose-950/10 space-y-2">
                  <h5 className="text-xs font-bold text-rose-400 uppercase tracking-wider flex items-center gap-1.5">
                    <TrendingDown className="w-3.5 h-3.5" /> Primary Downside Risks (Bear Case)
                  </h5>
                  <ul className="text-xs text-slate-300 space-y-1.5 list-disc list-inside">
                    {finalDossier.primary_risks?.map((r, i) => (
                      <li key={i} className="leading-relaxed">{r}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* Specialist Personas Grid */}
          {personaReports.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-bold text-slate-300 uppercase tracking-wider">
                  Committee Specialist Deliberation ({personaReports.length}/4)
                </h4>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {personaReports.map((report) => (
                  <div 
                    key={report.persona_name} 
                    className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 flex flex-col justify-between space-y-3 shadow-md"
                  >
                    <div>
                      <div className="flex items-center justify-between border-b border-slate-800 pb-2.5 mb-2.5">
                        <div>
                          <span className="font-bold text-white text-base">{report.persona_name}</span>
                          <span className={`ml-2.5 px-2 py-0.5 rounded text-[10px] font-black uppercase ${
                            report.stance === 'BULLISH' ? 'bg-emerald-500/20 text-emerald-400' :
                            report.stance === 'BEARISH' ? 'bg-rose-500/20 text-rose-400' :
                            'bg-amber-500/20 text-amber-300'
                          }`}>
                            {report.stance}
                          </span>
                          {PERSONA_WEIGHTS[report.persona_name] && (
                            <span className="ml-1.5 px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono text-[10px]">
                              {PERSONA_WEIGHTS[report.persona_name].pct} wt
                            </span>
                          )}
                        </div>
                        <div className="text-right">
                          <div className="font-mono font-black text-sm text-slate-200">
                            {PERSONA_WEIGHTS[report.persona_name]?.metricLabel || 'Score'}:{' '}
                            <span className="text-teal-400">{report.score}</span>/10
                          </div>
                          {report.persona_name === 'Bearish Risk Advocate' && (
                            <div className="text-[10px] text-slate-500">1=High Risk, 10=Safe</div>
                          )}
                        </div>
                      </div>

                      <p className="text-xs text-slate-300 italic mb-3 leading-relaxed">
                        "{report.summary}"
                      </p>

                      <div className="space-y-1">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Key Observations:</span>
                        <ul className="text-xs text-slate-400 space-y-1 list-disc list-inside">
                          {report.key_findings?.map((k, i) => (
                            <li key={i} className="leading-snug">{k}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right 1 Column: Analysis History Log & Review Drawer */}
        <div className="lg:col-span-1 space-y-4">
          <div className="glass-panel p-4 rounded-2xl border border-slate-800 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
              <div className="flex items-center gap-2">
                <HistoryIcon className="w-4 h-4 text-teal-400" />
                <h3 className="text-sm font-bold text-white">Analysis History</h3>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 bg-slate-800 text-slate-400 rounded-full">
                {historyList.length}
              </span>
            </div>

            {/* Quick Filter */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={filterTicker}
                onChange={(e) => setFilterTicker(e.target.value.toUpperCase())}
                placeholder="Filter symbol..."
                className="w-full bg-slate-950 border border-slate-800/80 rounded-lg pl-8 pr-2 py-1 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-teal-500"
              />
            </div>

            {/* History List */}
            <div className="space-y-2 max-h-[620px] overflow-y-auto pr-1">
              {historyLoading ? (
                <div className="p-4 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-teal-400" /> Loading...
                </div>
              ) : historyList.length === 0 ? (
                <div className="p-4 text-center text-xs text-slate-500">
                  No saved analyses yet. Convene a committee to generate your first dossier.
                </div>
              ) : (
                historyList.map((item) => {
                  const isSelected = selectedHistoryId === item.id;
                  const dateStr = item.timestamp ? new Date(item.timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
                  return (
                    <div
                      key={item.id}
                      onClick={() => handleSelectHistoryRecord(item)}
                      className={`p-3 rounded-xl border transition-all cursor-pointer text-left group ${
                        isSelected 
                          ? 'border-teal-500 bg-teal-500/10 shadow-sm' 
                          : 'border-slate-800/80 bg-slate-900/40 hover:bg-slate-900/80 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="font-mono font-bold text-white text-sm group-hover:text-teal-300 transition-colors">
                          {item.ticker}
                        </span>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${getVerdictBadge(item.verdict)}`}>
                          {item.verdict}
                        </span>
                      </div>

                      <div className="text-[11px] text-slate-400 line-clamp-1 mb-2">
                        {item.company_name}
                      </div>

                      <div className="flex items-center justify-between text-[10px] text-slate-500 border-t border-slate-800/60 pt-1.5">
                        <span>Conviction: <strong className="text-teal-400 font-mono">{item.conviction_score}/10</strong></span>
                        <div className="flex items-center gap-1.5">
                          <span>{dateStr}</span>
                          <button
                            onClick={(e) => handleDeleteHistory(e, item.id)}
                            className="text-slate-600 hover:text-rose-400 p-0.5 transition-colors"
                            title="Delete snapshot"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

      </div>
        </>
      )}
    </div>
  );
}
