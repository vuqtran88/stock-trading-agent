import React, { useState, useEffect } from 'react';
import {
  FileText,
  Search,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Loader2,
  Upload,
  Calendar,
  Layers,
  ShieldAlert,
  ArrowRight,
  ExternalLink,
  Edit3,
  Clock,
  History as HistoryIcon,
  Trash2,
  FileCheck
} from 'lucide-react';

export default function EarningsLab() {
  const [ticker, setTicker] = useState('AAPL');
  const [inputMode, setInputMode] = useState('auto'); // 'auto' | 'upload'

  // Metadata Preview State (Confirmation Gate)
  const [previewMeta, setPreviewMeta] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [selectedPeriod, setSelectedPeriod] = useState('');
  const [isEditingPeriod, setIsEditingPeriod] = useState(false);

  // Upload State
  const [selectedFile, setSelectedFile] = useState(null);
  const [transcriptText, setTranscriptText] = useState('');
  const [isDragging, setIsDragging] = useState(false);

  // Execution & Dossier State
  const [isAuditing, setIsAuditing] = useState(false);
  const [dossier, setDossier] = useState(null);
  const [auditError, setAuditError] = useState(null);

  const fileInputRef = React.useRef(null);
  // History Drawer State
  const [historyList, setHistoryList] = useState([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  const fetchHistory = async () => {
    setHistoryLoading(true);
    try {
      const res = await fetch('/api/agent/earnings/history');
      if (res.ok) {
        const data = await res.json();
        setHistoryList(data);
      }
    } catch (err) {
      console.error('Failed to load earnings audit history', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  // Step 1: Preview Metadata (Lightweight & Instant)
  const handlePreviewMetadata = async (symbol) => {
    const sym = (symbol || ticker || '').trim().toUpperCase();
    if (!sym) return;

    setPreviewLoading(true);
    setPreviewMeta(null);
    setDossier(null);
    setAuditError(null);
    setIsEditingPeriod(false);
    setSelectedHistoryId(null);

    try {
      const res = await fetch(`/api/agent/earnings/preview?ticker=${encodeURIComponent(sym)}`);
      if (res.ok) {
        const data = await res.json();
        setPreviewMeta(data);
        setSelectedPeriod(data.detected_period || 'Latest Reported Quarter');
      } else {
        setAuditError(`Could not find earnings metadata for ${sym}.`);
      }
    } catch (err) {
      setAuditError(`Preview failed: ${err.message}`);
    } finally {
      setPreviewLoading(false);
    }
  };

  // Step 2: Confirm & Launch Deep Audit
  const handleLaunchAudit = async () => {
    if (!previewMeta && inputMode === 'auto') return;

    setIsAuditing(true);
    setAuditError(null);

    try {
      if (inputMode === 'auto') {
        const res = await fetch('/api/agent/earnings/audit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ticker: previewMeta.ticker,
            target_period: selectedPeriod,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          setDossier(data.dossier);
          fetchHistory();
        } else {
          const err = await res.json();
          setAuditError(err.detail || 'Audit execution failed.');
        }
      } else {
        // Mode B: File upload or transcript paste
        const formData = new FormData();
        formData.append('ticker', ticker.toUpperCase());
        formData.append('target_period', selectedPeriod || 'Custom Document');
        if (selectedFile) formData.append('file', selectedFile);
        if (transcriptText) formData.append('transcript_text', transcriptText);

        const res = await fetch('/api/agent/earnings/upload', {
          method: 'POST',
          body: formData,
        });
        if (res.ok) {
          const data = await res.json();
          setDossier(data.dossier);
          fetchHistory();
        } else {
          const err = await res.json();
          setAuditError(err.detail || 'Upload audit failed.');
        }
      }
    } catch (err) {
      setAuditError(`Error running audit: ${err.message}`);
    } finally {
      setIsAuditing(false);
    }
  };

  const handleSelectHistoryRecord = (record) => {
    setSelectedHistoryId(record.id);
    setTicker(record.ticker);
    setDossier(record.dossier);
    setPreviewMeta(null);
  };

  const handleDeleteHistory = async (e, recordId) => {
    e.stopPropagation();
    try {
      const res = await fetch(`/api/agent/earnings/history/${recordId}`, { method: 'DELETE' });
      if (res.ok) {
        if (selectedHistoryId === recordId) {
          setSelectedHistoryId(null);
          setDossier(null);
        }
        fetchHistory();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const getGradeBadge = (grade) => {
    if (grade?.startsWith('A')) return 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40';
    if (grade?.startsWith('B')) return 'bg-teal-500/20 text-teal-300 border border-teal-500/40';
    if (grade?.startsWith('C')) return 'bg-amber-500/20 text-amber-300 border border-amber-500/40';
    return 'bg-rose-500/20 text-rose-400 border border-rose-500/40';
  };

  const getGuidanceBadge = (guidance) => {
    switch (guidance) {
      case 'RAISED':
        return 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40';
      case 'CONFIRMED':
        return 'bg-teal-500/20 text-teal-300 border border-teal-500/40';
      case 'LOWERED':
        return 'bg-rose-500/20 text-rose-400 border border-rose-500/40';
      case 'CAUTIOUS':
        return 'bg-amber-500/20 text-amber-300 border border-amber-500/40';
      default:
        return 'bg-slate-700 text-slate-300';
    }
  };

  return (
    <div className="space-y-6">
      {/* Workspace Header */}
      <div className="glass-panel p-6 rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-900 via-slate-900/90 to-sky-950/30 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-sky-500/20 border border-sky-500/30 rounded-xl text-sky-400">
              <FileText className="w-5 h-5" />
            </div>
            <h2 className="text-xl font-bold text-white tracking-tight">Earnings Intelligence Lab</h2>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Deep forensic audit of quarterly 10-Q/10-K releases, earnings surprises, margin trajectories, and guidance tone with verified metadata confirmation.
          </p>
        </div>

        {/* Input Mode Selector */}
        <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800">
          <button
            onClick={() => { setInputMode('auto'); setDossier(null); }}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${inputMode === 'auto'
                ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30 shadow-sm'
                : 'text-slate-400 hover:text-white'
              }`}
          >
            Auto Ingest (SEC EDGAR)
          </button>
          <button
            onClick={() => { setInputMode('upload'); setDossier(null); }}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${inputMode === 'upload'
                ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30 shadow-sm'
                : 'text-slate-400 hover:text-white'
              }`}
          >
            Custom PDF / Transcript
          </button>
        </div>
      </div>

      {/* Main Grid: Controls & Dossier (Left 3 cols) + History (Right 1 col) */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
        <div className="lg:col-span-3 space-y-6">

          {/* Mode A: Auto-Fetch Ticker Search */}
          {inputMode === 'auto' && (
            <div className="glass-panel p-4 rounded-xl border border-slate-800 flex flex-wrap items-center gap-3">
              <div className="relative flex-1 min-w-[200px]">
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  onKeyDown={(e) => e.key === 'Enter' && handlePreviewMetadata(ticker)}
                  placeholder="Enter US Ticker for Earnings Audit (e.g. AAPL, NVDA, MSFT)..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
                />
              </div>

              <button
                onClick={() => handlePreviewMetadata(ticker)}
                disabled={previewLoading || !ticker}
                className="flex items-center gap-2 px-5 py-2 bg-sky-500 hover:bg-sky-400 text-slate-950 rounded-xl text-sm font-bold transition-all disabled:opacity-50 cursor-pointer shadow-lg shadow-sky-500/20"
              >
                {previewLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Finding Reports...
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4" />
                    Inspect Filings
                  </>
                )}
              </button>
            </div>
          )}

          {/* Mode B: Upload / Paste */}
          {inputMode === 'upload' && (
            <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-bold text-white flex items-center gap-2">
                  <Upload className="w-4 h-4 text-sky-400" />
                  Custom Earnings Release or Conference Call Transcript
                </span>
                <input
                  type="text"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  placeholder="Ticker Symbol (e.g. AAPL)"
                  className="w-32 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1 text-xs text-white uppercase font-mono"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* PDF Dropzone */}
                <div
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setIsDragging(true);
                  }}
                  onDragEnter={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setIsDragging(true);
                  }}
                  onDragLeave={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setIsDragging(false);
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setIsDragging(false);
                    const files = e.dataTransfer?.files;
                    if (files && files.length > 0) {
                      const file = files[0];
                      if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
                        setSelectedFile(file);
                        setAuditError(null);
                      } else {
                        setAuditError('Please drop a valid .pdf file.');
                      }
                    }
                  }}
                  className={`border-2 border-dashed rounded-xl p-6 text-center transition-all cursor-pointer flex flex-col items-center justify-center group ${
                    isDragging
                      ? 'border-sky-400 bg-sky-500/10 scale-[1.01] shadow-lg shadow-sky-500/10'
                      : 'border-slate-800 hover:border-sky-500/40 bg-slate-950/40'
                  }`}
                >
                  <Upload className={`w-8 h-8 transition-colors mb-2 ${
                    isDragging ? 'text-sky-400 animate-bounce' : 'text-slate-500 group-hover:text-sky-400'
                  }`} />
                  <span className="text-xs text-slate-200 font-semibold group-hover:text-white">
                    {selectedFile ? selectedFile.name : (isDragging ? 'Drop your PDF here' : 'Drag & drop or click to select earnings report / filing')}
                  </span>
                  <span className="text-[10px] text-slate-400 mt-1 max-w-xs text-center leading-relaxed">
                    Accepts <strong>10-Q, 10-K, 8-K press release, or investor slide decks</strong> (.pdf)
                  </span>
                  {selectedFile && (
                    <span className="mt-2 text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                      ✓ File Ready: {(selectedFile.size / 1024).toFixed(1)} KB
                    </span>
                  )}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,application/pdf"
                    onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                    className="hidden"
                  />
                </div>

                {/* Paste Transcript */}
                <div>
                  <textarea
                    value={transcriptText}
                    onChange={(e) => setTranscriptText(e.target.value)}
                    placeholder="Or paste earnings call transcript / CEO remarks here..."
                    rows={6}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500 font-mono resize-none"
                  />
                </div>
              </div>

              <div className="flex justify-end">
                <button
                  onClick={handleLaunchAudit}
                  disabled={isAuditing || (!selectedFile && !transcriptText)}
                  className="flex items-center gap-2 px-5 py-2 bg-sky-500 hover:bg-sky-400 text-slate-950 rounded-xl text-sm font-bold transition-all disabled:opacity-50 cursor-pointer shadow-lg shadow-sky-500/20"
                >
                  {isAuditing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  Run Custom Audit
                </button>
              </div>
            </div>
          )}

          {/* User Confirmation Card (The Verification Gate) */}
          {previewMeta && !dossier && !isAuditing && (
            <div className="glass-panel p-6 rounded-2xl border border-sky-500/40 bg-gradient-to-b from-slate-900 via-slate-900/90 to-sky-950/20 shadow-xl space-y-5 animate-in fade-in duration-200">
              <div className="flex items-start justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-xl bg-sky-500/20 border border-sky-500/30 text-sky-400">
                    <FileCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white flex items-center gap-2 font-mono">
                      {previewMeta.ticker} — {previewMeta.company_name}
                    </h3>
                    <p className="text-xs text-slate-400">
                      Discovered SEC periodic filing & earnings metadata. Please verify before analyzing.
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => setIsEditingPeriod(!isEditingPeriod)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                >
                  <Edit3 className="w-3.5 h-3.5 text-sky-400" />
                  {isEditingPeriod ? 'Collapse' : 'Edit / Change Period'}
                </button>
              </div>

              {/* Detected Metadata Summary */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-xl">
                  <span className="text-slate-500 block text-[10px] font-bold uppercase">Target Period</span>
                  <strong className="text-sky-300 font-mono text-sm">{selectedPeriod}</strong>
                </div>
                <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-xl">
                  <span className="text-slate-500 block text-[10px] font-bold uppercase">Primary Document</span>
                  <strong className="text-white font-mono text-sm">{previewMeta.latest_filing?.type || '10-Q'}</strong>
                </div>
                <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-xl">
                  <span className="text-slate-500 block text-[10px] font-bold uppercase">Filing Date</span>
                  <strong className="text-slate-300 font-mono text-sm">{previewMeta.latest_filing?.date || 'Recent'}</strong>
                </div>
                <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-xl">
                  <span className="text-slate-500 block text-[10px] font-bold uppercase">EPS Surprise</span>
                  <strong className="text-emerald-400 font-mono text-sm">
                    {previewMeta.latest_eps?.surprise_pct != null
                      ? `+${previewMeta.latest_eps.surprise_pct}%`
                      : 'N/A'}
                  </strong>
                </div>
              </div>

              {/* Exact Documents That Will Be Ingested */}
              <div className="p-4 bg-slate-950/80 border border-slate-800/90 rounded-xl space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-sky-400" /> Documents & Data Sources Queued for Analysis:
                  </span>
                  <span className="text-[10px] font-mono text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                    {previewMeta.recent_filings?.length || 0} SEC Filings Available
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                  {/* Primary Target Filing */}
                  <div className="p-2.5 bg-slate-900/60 rounded-lg border border-sky-500/30 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-sky-500/20 text-sky-300 border border-sky-500/40">
                        {previewMeta.latest_filing?.type}
                      </span>
                      <div>
                        <div className="font-medium text-white text-[11px] line-clamp-1">
                          {previewMeta.latest_filing?.title || 'Periodic Financial Report'}
                        </div>
                        <div className="text-[10px] text-slate-400">Filed {previewMeta.latest_filing?.date} (Primary Forensic Source)</div>
                      </div>
                    </div>
                    {previewMeta.latest_filing?.edgar_url && (
                      <a
                        href={previewMeta.latest_filing.edgar_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sky-400 hover:text-sky-300 p-1"
                        title="View on SEC EDGAR"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>

                  {/* Supporting Financial Statements Data */}
                  <div className="p-2.5 bg-slate-900/60 rounded-lg border border-slate-800 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-teal-500/20 text-teal-300 border border-teal-500/40">
                        4-Qtr Series
                      </span>
                      <div>
                        <div className="font-medium text-white text-[11px]">Quarterly Income & Cash Flow Statements</div>
                        <div className="text-[10px] text-slate-400">GAAP Revenue, Operating Income, and Free Cash Flow</div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Additional Available Recent SEC Filings */}
                {previewMeta.recent_filings?.length > 1 && (
                  <div className="pt-1.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
                      Supporting Context Filings on EDGAR:
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {previewMeta.recent_filings.slice(1, 4).map((f, i) => (
                        <a
                          key={i}
                          href={f.edgar_url}
                          target="_blank"
                          rel="noreferrer"
                          className="px-2 py-0.5 bg-slate-900 hover:bg-slate-800 border border-slate-800 text-[10px] font-mono text-slate-300 rounded flex items-center gap-1 transition-colors"
                        >
                          <span className="text-sky-400 font-bold">{f.type}</span> ({f.date})
                          <ExternalLink className="w-2.5 h-2.5 opacity-60" />
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Expandable Period Selector (When User Clicks 'Edit') */}
              {isEditingPeriod && (
                <div className="p-4 bg-slate-950 rounded-xl border border-sky-500/30 space-y-3">
                  <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-sky-400" /> Choose Reporting Period to Audit:
                  </span>

                  <div className="flex flex-wrap gap-2">
                    {previewMeta.available_quarters?.map((q, idx) => {
                      const label = `Quarter (${q.date})`;
                      const isSel = selectedPeriod === label;
                      return (
                        <button
                          key={idx}
                          onClick={() => setSelectedPeriod(label)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-all cursor-pointer ${isSel
                              ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 font-bold'
                              : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white'
                            }`}
                        >
                          {q.date} (EPS: ${q.reported_eps})
                        </button>
                      );
                    })}
                  </div>

                  <div className="flex items-center gap-2 pt-2">
                    <span className="text-[11px] text-slate-400">Or type custom period:</span>
                    <input
                      type="text"
                      value={selectedPeriod}
                      onChange={(e) => setSelectedPeriod(e.target.value)}
                      placeholder="e.g. Q2 FY2026"
                      className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-1 text-xs text-white font-mono w-48"
                    />
                  </div>
                </div>
              )}

              {/* Action Confirmation Buttons */}
              <div className="flex items-center justify-between pt-2">
                {previewMeta.latest_filing?.edgar_url ? (
                  <a
                    href={previewMeta.latest_filing.edgar_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-sky-400 hover:underline flex items-center gap-1"
                  >
                    View Filing on SEC EDGAR <ExternalLink className="w-3 h-3" />
                  </a>
                ) : <div />}

                <button
                  onClick={handleLaunchAudit}
                  className="flex items-center gap-2 px-6 py-2.5 bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold rounded-xl text-sm transition-all shadow-lg shadow-sky-500/20 cursor-pointer"
                >
                  <Sparkles className="w-4 h-4" />
                  Confirm & Launch Forensic Audit
                </button>
              </div>
            </div>
          )}

          {/* Audit Loading Indicator */}
          {isAuditing && (
            <div className="p-8 rounded-2xl border border-sky-500/30 bg-sky-500/5 text-center space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-sky-400 mx-auto" />
              <div className="text-base font-bold text-white">Performing 5-Part Forensic Earnings Audit...</div>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                Dissecting revenue quality, GAAP vs non-GAAP cash reconciliation, 4-quarter beat cadence, and SEC accounting red flags for <strong>{ticker}</strong>.
              </p>
            </div>
          )}

          {/* Audit Error Alert */}
          {auditError && (
            <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-300 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{auditError}</span>
            </div>
          )}

          {/* 5-PART FORENSIC EARNINGS DOSSIER */}
          {dossier && !isAuditing && (
            <div className="glass-panel p-6 rounded-2xl border border-sky-500/40 bg-gradient-to-b from-slate-900 via-slate-900/90 to-sky-950/20 shadow-xl space-y-6">

              {/* Top Banner: Grade, Quality Score, Guidance */}
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
                <div>
                  <div className="flex items-center gap-3">
                    <h3 className="text-2xl font-black text-white font-mono">{dossier.ticker}</h3>
                    <span className="text-base text-slate-400">{dossier.company_name}</span>
                    <span className={`px-3 py-1 rounded-lg text-xs font-black tracking-wide ${getGradeBadge(dossier.earnings_grade)}`}>
                      Grade: {dossier.earnings_grade}
                    </span>
                    <span className={`px-2.5 py-1 rounded-lg text-xs font-bold ${getGuidanceBadge(dossier.guidance_trajectory)}`}>
                      Guidance: {dossier.guidance_trajectory}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1 flex items-center gap-2">
                    <Clock className="w-3.5 h-3.5 text-sky-400" />
                    Audited Period: <strong className="text-slate-200">{dossier.reporting_period}</strong>
                  </p>
                </div>

                {/* Dual Score Cards: Quality Score & Management Credibility */}
                <div className="flex flex-wrap items-center gap-3">
                  {/* Score 1: Quality of Earnings */}
                  <div className="bg-slate-950/80 p-3 rounded-xl border border-slate-800 min-w-[150px]">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Quality Score</span>
                      <span className="text-[9px] px-1.5 py-0.2 rounded bg-sky-500/10 text-sky-400 font-mono">Accounting</span>
                    </div>
                    <div className="text-xl font-black font-mono text-sky-400 mt-0.5">
                      {dossier.quality_score} <span className="text-xs text-slate-500 font-normal">/ 10</span>
                    </div>
                    <div className="text-[10px] text-slate-400 mt-1">GAAP vs Real Cash Quality</div>
                  </div>

                  {/* Score 2: Management Credibility */}
                  <div className="bg-slate-950/80 p-3 rounded-xl border border-slate-800 min-w-[150px]">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Credibility</span>
                      <span className="text-[9px] px-1.5 py-0.2 rounded bg-teal-500/10 text-teal-400 font-mono">Guidance</span>
                    </div>
                    <div className="text-xl font-black font-mono text-teal-300 mt-0.5">
                      {dossier.management_credibility_score || 'N/A'} <span className="text-xs text-slate-500 font-normal">/ 10</span>
                    </div>
                    <div className="text-[10px] text-slate-400 mt-1">Guidance Candor & Track Record</div>
                  </div>
                </div>
              </div>

              {/* Score Breakdown Explainer Banner (if provided) */}
              {((dossier.quality_score_breakdown && dossier.quality_score_breakdown.length > 0) ||
                (dossier.management_credibility_breakdown && dossier.management_credibility_breakdown.length > 0)) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-3.5 bg-slate-950/70 border border-slate-800/80 rounded-xl">
                  {dossier.quality_score_breakdown?.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-sky-400 flex items-center gap-1">
                        • Quality Score Drivers ({dossier.quality_score}/10):
                      </span>
                      <ul className="text-[11px] text-slate-300 space-y-0.5 list-disc list-inside">
                        {dossier.quality_score_breakdown.map((item, idx) => (
                          <li key={idx} className="leading-tight">{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {dossier.management_credibility_breakdown?.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-teal-400 flex items-center gap-1">
                        • Credibility Drivers ({dossier.management_credibility_score}/10):
                      </span>
                      <ul className="text-[11px] text-slate-300 space-y-0.5 list-disc list-inside">
                        {dossier.management_credibility_breakdown.map((item, idx) => (
                          <li key={idx} className="leading-tight">{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* 1. Executive Summary */}
              <div className="space-y-1.5">
                <h4 className="text-xs font-bold uppercase tracking-wider text-sky-400">1. Executive Forensic Synthesis</h4>
                <p className="text-sm text-slate-200 leading-relaxed bg-slate-950/50 p-4 rounded-xl border border-slate-800/80">
                  {dossier.executive_summary}
                </p>
              </div>

              {/* 2. Beat / Miss Cadence & Table */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-sky-400">2. Beat / Miss Cadence & Wall Street Expectations</h4>
                <p className="text-xs text-slate-300 leading-relaxed">
                  {dossier.beat_miss_analysis}
                </p>

                {dossier.eps_surprise_summary?.length > 0 && (
                  <div className="overflow-x-auto pt-2">
                    <table className="w-full text-left text-xs border border-slate-800 rounded-xl overflow-hidden">
                      <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
                        <tr>
                          <th className="p-2.5">Quarter / Filing Date</th>
                          <th className="p-2.5">EPS Est</th>
                          <th className="p-2.5">Reported EPS</th>
                          <th className="p-2.5">Surprise %</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60 bg-slate-950/40 font-mono">
                        {dossier.eps_surprise_summary.map((row, i) => {
                          const isCurrent = i === 0 || row.is_current;
                          return (
                            <tr key={i} className={isCurrent ? "bg-sky-500/10 font-bold border-l-2 border-l-sky-400" : "hover:bg-slate-900/40"}>
                              <td className="p-2.5 text-slate-300 flex items-center gap-2">
                                <span>{row.quarter || row.date || row.quarter_date}</span>
                                {isCurrent && (
                                  <span className="px-1.5 py-0.2 rounded text-[9px] uppercase tracking-wider bg-sky-500/20 text-sky-300 border border-sky-500/40 font-sans">
                                    Audited Quarter
                                  </span>
                                )}
                              </td>
                              <td className="p-2.5 text-slate-400">${row.eps_estimate ?? 'N/A'}</td>
                              <td className="p-2.5 text-white font-bold">${row.reported_eps ?? 'N/A'}</td>
                              <td className="p-2.5 text-emerald-400 font-bold">
                                {row.surprise_pct != null
                                  ? (Number(row.surprise_pct) >= 0 ? `+${row.surprise_pct}%` : `${row.surprise_pct}%`)
                                  : 'N/A'}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* 3. Revenue Quality & Cash Flow Conversion */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/60 space-y-2">
                  <h5 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                    <TrendingUp className="w-3.5 h-3.5 text-teal-400" /> Revenue Quality & Margins
                  </h5>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {dossier.revenue_quality_analysis}
                  </p>
                </div>

                <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/60 space-y-2">
                  <h5 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                    <TrendingDown className="w-3.5 h-3.5 text-sky-400" /> Cash Flow Conversion
                  </h5>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {dossier.cash_flow_conversion}
                  </p>
                </div>
              </div>

              {/* 4. Forward Guidance & Management Credibility */}
              <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/60 space-y-2">
                <div className="flex items-center justify-between">
                  <h5 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                    4. Guidance Outlook & Management Credibility
                  </h5>
                  <span className="text-xs font-mono text-sky-400 font-bold">
                    Credibility: {dossier.management_credibility_score}/10
                  </span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  {dossier.forward_guidance_analysis}
                </p>
              </div>

              {/* 5. Red Flags & Accounting Integrity */}
              <div className="p-4 rounded-xl border border-rose-950/50 bg-rose-950/10 space-y-2">
                <div className="flex items-center justify-between">
                  <h5 className="text-xs font-bold text-rose-400 uppercase tracking-wider flex items-center gap-1.5">
                    <ShieldAlert className="w-4 h-4" /> 5. Forensic Red Flags & Accounting Integrity
                  </h5>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase bg-rose-500/20 text-rose-300">
                    {dossier.accounting_integrity_rating}
                  </span>
                </div>
                <ul className="text-xs text-slate-300 space-y-1 list-disc list-inside">
                  {dossier.red_flags?.map((flag, i) => (
                    <li key={i} className="leading-relaxed">{flag}</li>
                  ))}
                </ul>
              </div>

              {/* Direct SEC Edgar Links */}
              {dossier.sec_filing_links?.length > 0 && (
                <div className="pt-2 border-t border-slate-800/80">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 block mb-2">
                    Verified SEC Edgar Documents:
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {dossier.sec_filing_links.map((link, idx) => (
                      <a
                        key={idx}
                        href={link.url}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1.5 px-3 py-1 bg-slate-900 hover:bg-slate-800 border border-slate-800 text-sky-400 rounded-lg text-xs font-mono transition-colors"
                      >
                        {link.type}: {link.title} <ExternalLink className="w-3 h-3" />
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Column: Earnings History Drawer */}
        <div className="lg:col-span-1 space-y-4">
          <div className="glass-panel p-4 rounded-2xl border border-slate-800 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
              <div className="flex items-center gap-2">
                <HistoryIcon className="w-4 h-4 text-sky-400" />
                <h3 className="text-sm font-bold text-white">Earnings Audits</h3>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 bg-slate-800 text-slate-400 rounded-full">
                {historyList.length}
              </span>
            </div>

            <div className="space-y-2 max-h-[620px] overflow-y-auto pr-1">
              {historyLoading ? (
                <div className="p-4 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-sky-400" /> Loading...
                </div>
              ) : historyList.length === 0 ? (
                <div className="p-4 text-center text-xs text-slate-500">
                  No saved earnings audits yet. Run an inspection to save your first forensic snapshot.
                </div>
              ) : (
                historyList.map((item) => {
                  const isSel = selectedHistoryId === item.id;
                  const dateStr = item.timestamp
                    ? new Date(item.timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
                    : '';
                  return (
                    <div
                      key={item.id}
                      onClick={() => handleSelectHistoryRecord(item)}
                      className={`p-3 rounded-xl border transition-all cursor-pointer text-left group ${isSel
                          ? 'border-sky-500 bg-sky-500/10 shadow-sm'
                          : 'border-slate-800/80 bg-slate-900/40 hover:bg-slate-900/80 hover:border-slate-700'
                        }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-mono font-bold text-white text-sm group-hover:text-sky-300 transition-colors">
                          {item.ticker}
                        </span>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${getGradeBadge(item.earnings_grade)}`}>
                          Grade: {item.earnings_grade}
                        </span>
                      </div>

                      <div className="text-[11px] text-slate-400 line-clamp-1 mb-1.5">
                        {item.reporting_period}
                      </div>

                      <div className="flex items-center justify-between text-[10px] text-slate-500 border-t border-slate-800/60 pt-1.5">
                        <span>Quality: <strong className="text-sky-400 font-mono">{item.quality_score}/10</strong></span>
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
    </div>
  );
}

