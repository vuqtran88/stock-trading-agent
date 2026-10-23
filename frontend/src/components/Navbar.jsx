import React from 'react';
import { 
  ShieldAlert, 
  RotateCcw, 
  TrendingUp, 
  TrendingDown, 
  LogOut, 
  Activity, 
  Zap,
  Lock,
  Radio,
  SlidersHorizontal,
  Clock,
  AlertTriangle
} from 'lucide-react';

export default function Navbar({ 
  portfolio, 
  config,
  schwabStatus,
  onToggleEnv,
  onEmergencyFlatten, 
  onResetEmergency, 
  onLogout 
}) {
  const isBull = portfolio?.regime_status === 'BULL';
  const isKillActive = portfolio?.kill_switch_active;
  const env = config?.env || portfolio?.env || 'paper';
  const isLive = env === 'live';

  return (
    <header className="sticky top-0 z-50 glass-panel border-b border-slate-800/80 px-6 py-3.5 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand & Market Status */}
        <div className="flex items-center space-x-6">
          <div className="flex items-center space-x-2.5">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center shadow-lg transition-all ${
              isLive
                ? 'bg-gradient-to-tr from-rose-500 to-amber-500 shadow-rose-500/20'
                : 'bg-gradient-to-tr from-emerald-500 to-teal-400 shadow-emerald-500/20'
            }`}>
              <Zap className="w-5 h-5 text-slate-950 stroke-[2.5]" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                  AlphaDrift
                </span>

                {/* Interactive / Clear Environment Selector Pill */}
                <button
                  type="button"
                  onClick={onToggleEnv}
                  title={`Currently in ${env.toUpperCase()} mode. Click to switch.`}
                  className={`flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full border transition-all cursor-pointer ${
                    isLive 
                      ? 'bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border-rose-500/40 shadow-sm shadow-rose-500/20' 
                      : 'bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border-emerald-500/40 shadow-sm shadow-emerald-500/20'
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${isLive ? 'bg-rose-400 animate-pulse' : 'bg-emerald-400'}`} />
                  <span>{env} MODE</span>
                </button>
              </div>
              <p className="text-[11px] text-slate-400">
                {isLive ? 'Live Schwab Broker Account' : 'Simulated Paper Trading Sandbox'}
              </p>
            </div>
          </div>

          {/* QQQ Regime Pill */}
          {(() => {
            const isBypassed = config?.use_regime_filter === false || portfolio?.use_regime_filter === false;
            return (
              <div 
                title={isBypassed ? "QQQ Regime filter is BYPASSED by user. Trades will execute regardless of market trend." : "QQQ Regime filter is ACTIVE."}
                className="hidden lg:flex items-center space-x-2.5 px-3 py-1.5 rounded-lg bg-slate-900/60 border border-slate-800 text-xs"
              >
                <Activity className="w-3.5 h-3.5 text-slate-400" />
                <span className="text-slate-400 font-medium">QQQ Regime:</span>
                <span className="font-semibold text-white">${portfolio?.qqq_price?.toFixed(2) || '---'}</span>
                <span className="text-slate-500 text-[11px]">
                  / {config?.regime_ema_period || portfolio?.regime_ema_period || 20}EMA ${portfolio?.qqq_ema20?.toFixed(2) || '---'}
                </span>
                {isBypassed ? (
                  <div className="flex items-center space-x-1 font-bold text-[11px] px-2 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30">
                    {isBull ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    <span>{isBull ? 'BULL (BYPASSED)' : 'BEAR (BYPASSED)'}</span>
                  </div>
                ) : (
                  <div className={`flex items-center space-x-1 font-bold text-[11px] px-2 py-0.5 rounded ${
                    isBull ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
                  }`}>
                    {isBull ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    <span>{isBull ? 'BULL (ACTIVE)' : 'BEAR (CASH)'}</span>
                  </div>
                )}
              </div>
            );
          })()}

          {/* Schwab Connection Badge & Expiration Clock */}
          {schwabStatus && (
            <div className="hidden sm:flex items-center space-x-2">
              <div 
                title={
                  schwabStatus.connected
                    ? `Schwab Live API Connected\nAccount: ${schwabStatus.account_hash_short || 'Active'}\nSettled Cash: $${Number(schwabStatus.settled_cash || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}\nActive Positions: ${schwabStatus.positions_count || 0}`
                    : `Schwab Disconnected: ${schwabStatus.error || 'Token expired or invalid credentials'}`
                }
                className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg border text-xs transition-all ${
                  schwabStatus.connected
                    ? 'bg-slate-900/80 border-sky-500/30 text-slate-200'
                    : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                }`}
              >
                <span className={`w-2 h-2 rounded-full ${
                  schwabStatus.connected ? 'bg-sky-400 shadow-[0_0_8px_rgba(56,189,248,0.7)] animate-pulse' : 'bg-rose-500'
                }`} />
                <div className="flex flex-col">
                  <div className="flex items-center gap-1.5 leading-none">
                    <span className="font-bold text-[11px] text-sky-400">SCHWAB</span>
                    <span className={`text-[10px] font-semibold ${schwabStatus.connected ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {schwabStatus.connected ? 'LIVE' : 'OFFLINE'}
                    </span>
                  </div>
                  {schwabStatus.connected && (
                    <span className="text-[10px] text-slate-400 font-mono mt-0.5">
                      ${Number(schwabStatus.settled_cash || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  )}
                </div>
              </div>

              {/* 7-Day OAuth Refresh Token Clock & Expiry Badge */}
              {schwabStatus.token_status?.has_token && (
                <div 
                  title={`Charles Schwab OAuth2 Refresh Token Expiry Clock:\n${schwabStatus.token_status.message}\nRun 'python3 scripts/schwab_login.py --force' to renew.`}
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs transition-all ${
                    schwabStatus.token_status.status === 'CRITICAL'
                      ? 'bg-rose-500/20 text-rose-300 border-rose-500/50 shadow-sm shadow-rose-500/30 animate-pulse'
                      : schwabStatus.token_status.status === 'WARNING'
                      ? 'bg-amber-500/20 text-amber-300 border-amber-500/50 shadow-sm shadow-amber-500/30'
                      : 'bg-slate-900/60 text-slate-300 border-slate-800'
                  }`}
                >
                  {schwabStatus.token_status.is_near_expiry ? (
                    <AlertTriangle className={`w-3.5 h-3.5 shrink-0 ${schwabStatus.token_status.status === 'CRITICAL' ? 'text-rose-400' : 'text-amber-400'}`} />
                  ) : (
                    <Clock className="w-3.5 h-3.5 text-teal-400 shrink-0" />
                  )}
                  <div className="flex flex-col leading-tight">
                    <span className="text-[9px] uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-1">
                      Token Clock
                      {schwabStatus.token_status.is_near_expiry && (
                        <span className={`px-1 py-0.2 rounded text-[8px] font-bold ${
                          schwabStatus.token_status.status === 'CRITICAL' ? 'bg-rose-600 text-white' : 'bg-amber-600 text-white'
                        }`}>
                          RENEW
                        </span>
                      )}
                    </span>
                    <span className="font-mono text-[11px] font-bold">
                      {schwabStatus.token_status.days_remaining > 1
                        ? `${schwabStatus.token_status.days_remaining}d left`
                        : `${schwabStatus.token_status.hours_remaining}h left`}
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Emergency Stop & Controls */}
        <div className="flex items-center space-x-3.5">
          {isKillActive ? (
            <button
              onClick={onResetEmergency}
              className="flex items-center space-x-2 px-3.5 py-1.5 rounded-lg bg-amber-500/15 border border-amber-500/40 text-amber-400 text-xs font-semibold hover:bg-amber-500/25 transition cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5 animate-spin-reverse" />
              <span>Resume Trading</span>
            </button>
          ) : (
            <button
              onClick={onEmergencyFlatten}
              className="flex items-center space-x-2 px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold shadow-lg shadow-rose-600/30 transition cursor-pointer"
            >
              <ShieldAlert className="w-3.5 h-3.5 stroke-[2.5]" />
              <span>Emergency Flatten</span>
            </button>
          )}

          <div className="h-4 w-[1px] bg-slate-800" />

          <button
            onClick={onLogout}
            title="Log Out"
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/60 transition cursor-pointer"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
