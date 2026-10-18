import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Portfolio from './components/Portfolio';
import Routines from './components/Routines';
import OrderForm from './components/OrderForm';
import Universe from './components/Universe';
import BacktestStudio from './components/BacktestStudio';
import History from './components/History';
import LoginModal from './components/LoginModal';
import {
  LayoutDashboard,
  TrendingUp,
  Sliders,
  History as HistoryIcon,
  ShieldAlert,
} from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authChecking, setAuthChecking] = useState(true);

  // Portfolio & Market Data
  const [portfolio, setPortfolio] = useState(null);
  const [portfolioLoading, setPortfolioLoading] = useState(true);
  const [config, setConfig] = useState(null);

  // Routine execution logs (persisted in localStorage)
  const [routineLogs, setRoutineLogs] = useState(() => {
    try {
      const saved = localStorage.getItem('action_output_logs');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [runningRoutine, setRunningRoutine] = useState(null);

  useEffect(() => {
    try {
      localStorage.setItem('action_output_logs', JSON.stringify(routineLogs));
    } catch (e) {
      console.error('Failed to save logs to localStorage', e);
    }
  }, [routineLogs]);

  // Check Auth Status on mount
  const checkAuth = async () => {
    try {
      const res = await fetch('/api/auth/status');
      const data = await res.json();
      setIsAuthenticated(Boolean(data.authenticated));
    } catch (err) {
      setIsAuthenticated(false);
    } finally {
      setAuthChecking(false);
    }
  };

  // Fetch config (for global env status)
  const fetchConfig = async () => {
    try {
      const res = await fetch('/api/config');
      if (res.ok) {
        const data = await res.json();
        setConfig(data);
      }
    } catch (err) {
      console.error('Error fetching config:', err);
    }
  };

  // Fetch live portfolio & regime
  const fetchPortfolio = async () => {
    try {
      const res = await fetch('/api/trading/portfolio');
      if (res.status === 401) {
        setIsAuthenticated(false);
        return;
      }
      if (res.ok) {
        const data = await res.json();
        setPortfolio(data);
      }
    } catch (err) {
      console.error('Error fetching portfolio:', err);
    } finally {
      setPortfolioLoading(false);
    }
  };

  useEffect(() => {
    checkAuth();
  }, []);

  // Poll portfolio & config every 6s when authenticated
  useEffect(() => {
    if (!isAuthenticated) return;
    fetchPortfolio();
    fetchConfig();
    const interval = setInterval(() => {
      fetchPortfolio();
      fetchConfig();
    }, 6000);
    return () => clearInterval(interval);
  }, [isAuthenticated]);

  const handleLogout = async () => {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
    } catch (err) {
      console.error(err);
    }
    setIsAuthenticated(false);
  };

  // Toggle Environment (Paper <-> Live)
  const handleToggleEnv = async () => {
    const currentEnv = config?.env || portfolio?.env || 'paper';
    const nextEnv = currentEnv === 'paper' ? 'live' : 'paper';

    if (nextEnv === 'live') {
      const confirmed = confirm(
        '⚠️ ATTENTION: You are about to switch to LIVE Trading Mode.\n\nReal money Schwab orders will be executed automatically by the trading engine.\n\nAre you sure you want to proceed?'
      );
      if (!confirmed) return;
    }

    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ env: nextEnv }),
      });
      if (res.ok) {
        addLog(`Switched trading environment to ${nextEnv.toUpperCase()} mode.`);
        fetchConfig();
        fetchPortfolio();
      } else {
        const err = await res.json();
        alert(err.detail || 'Failed to switch environment');
      }
    } catch (e) {
      alert('Network error switching environment');
    }
  };

  // Close out single position
  const handleClosePosition = async (sym) => {
    if (!confirm(`Liquidate active position for ${sym}?`)) return;
    try {
      const res = await fetch(`/api/trading/positions/${sym}`, { method: 'DELETE' });
      const data = await res.json();
      if (res.ok) {
        addLog(`Closed position ${sym}: ${data.detail || 'Success'}`);
        fetchPortfolio();
      } else {
        alert(data.detail || 'Failed to close position');
      }
    } catch (err) {
      alert('Network error closing position');
    }
  };

  // Trigger automated routines
  const handleTriggerRoutine = async (routineType) => {
    if (routineType === 'refresh') {
      fetchPortfolio();
      return;
    }

    setRunningRoutine(routineType);
    const endpoint =
      routineType === 'buy' ? '/api/trading/run-close-routine' : '/api/trading/run-open-routine';
    const label = routineType === 'buy' ? '3:50 PM Buy Entry' : '9:28 AM Morning Exit';


    addLog(`Initiating ${label}...`, 'info');

    try {
      const res = await fetch(endpoint, { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        addLog(`Completed ${label}: ${data.message || data.summary || 'Finished'}`, 'success');
        fetchPortfolio();
      } else {
        addLog(`Error in ${label}: ${data.detail || 'Execution failed'}`, 'error');
      }

    } catch (err) {
      addLog(`Network failure running ${label}`, 'error');
    } finally {
      setRunningRoutine(null);
    }
  };

  // Emergency flatten
  const handleEmergencyFlatten = async () => {
    if (!confirm('EMERGENCY: Immediately liquidate all open positions and engage kill switch?')) return;
    try {
      const res = await fetch('/api/trading/emergency-stop', { method: 'POST' });
      const data = await res.json();
      addLog(`KILL SWITCH ENGAGED: ${data.message || 'All positions flattened'}`, 'error');
      fetchPortfolio();
    } catch (err) {
      alert('Error triggering emergency stop');
    }
  };

  // Reset emergency state
  const handleResetEmergency = async () => {
    try {
      const res = await fetch('/api/trading/reset-emergency', { method: 'POST' });
      const data = await res.json();
      addLog(`Emergency state reset: ${data.status}`, 'info');
      fetchPortfolio();
    } catch (err) {
      alert('Error resetting emergency state');
    }
  };

  const addLog = (msg, type = 'info') => {
    const time = new Date().toLocaleTimeString();
    setRoutineLogs((prev) => [
      { id: Date.now() + Math.random(), time, text: msg, type },
      ...prev.slice(0, 499), // Store up to 500 historical activities
    ]);
  };

  const handleClearLogs = () => {
    setRoutineLogs([]);
    try {
      localStorage.removeItem('action_output_logs');
    } catch {}
  };

  if (authChecking) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-500 font-mono text-xs">
        Initializing terminal...
      </div>
    );
  }

  const currentEnv = config?.env || portfolio?.env || 'paper';
  const isLive = currentEnv === 'live';

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-teal-500/30 selection:text-teal-200">
      {/* Auth Modal if unauthenticated */}
      {!isAuthenticated && (
        <LoginModal
          onLoginSuccess={() => {
            setIsAuthenticated(true);
            fetchPortfolio();
            fetchConfig();
          }}
        />
      )}

      {/* Top Navigation */}
      <Navbar
        portfolio={portfolio}
        config={config}
        onToggleEnv={handleToggleEnv}
        onEmergencyFlatten={handleEmergencyFlatten}
        onResetEmergency={handleResetEmergency}
        onLogout={handleLogout}
      />

      {/* Main Container */}
      <div className="flex-1 max-w-7xl w-full mx-auto px-4 py-6 space-y-6">
        {/* Emergency Alert Banner if kill switch engaged */}
        {portfolio?.emergency_stop && (
          <div className="p-4 rounded-2xl bg-rose-500/15 border border-rose-500/40 text-rose-300 flex items-center justify-between shadow-xl">
            <div className="flex items-center gap-3">
              <ShieldAlert className="w-5 h-5 text-rose-400 shrink-0" />
              <div>
                <span className="font-bold text-sm">EMERGENCY KILL SWITCH ACTIVE</span>
                <p className="text-xs text-rose-300/80">
                  Automated routines and new order executions are halted until explicitly cleared.
                </p>
              </div>
            </div>
            <button
              onClick={handleResetEmergency}
              className="px-3 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-medium text-xs transition-colors cursor-pointer"
            >
              Reset Safety Lock
            </button>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'dashboard'
                  ? 'bg-teal-500/15 text-teal-300 border border-teal-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-900'
              }`}
            >
              <LayoutDashboard className="w-4 h-4" />
              Live & Paper Dashboard
            </button>

            <button
              onClick={() => setActiveTab('backtest')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'backtest'
                  ? 'bg-teal-500/15 text-teal-300 border border-teal-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-900'
              }`}
            >
              <TrendingUp className="w-4 h-4" />
              Backtest Studio
            </button>

            <button
              onClick={() => setActiveTab('universe')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'universe'
                  ? 'bg-teal-500/15 text-teal-300 border border-teal-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-900'
              }`}
            >
              <Sliders className="w-4 h-4" />
              Universe & Strategy
            </button>

            <button
              onClick={() => setActiveTab('history')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'history'
                  ? 'bg-teal-500/15 text-teal-300 border border-teal-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-900'
              }`}
            >
              <HistoryIcon className="w-4 h-4" />
              Audit Log
            </button>
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            {/* Top row: Portfolio overview & holdings */}
            <Portfolio
              portfolio={portfolio}
              loading={portfolioLoading}
              onClosePosition={handleClosePosition}
            />

            {/* Bottom 2 columns: Automated Routine Actions & Manual Paper Order Desk */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Routines
                onTrigger={handleTriggerRoutine}
                runningRoutine={runningRoutine}
                logs={routineLogs}
                onClearLogs={handleClearLogs}
                isLive={isLive}
                env={currentEnv}
              />
              <OrderForm
                isLive={isLive}
                onOrderSuccess={(msg) => {
                  addLog(msg);
                  fetchPortfolio();
                }}
              />
            </div>
          </div>
        )}

        {activeTab === 'backtest' && <BacktestStudio />}

        {activeTab === 'universe' && <Universe />}

        {activeTab === 'history' && <History />}
      </div>
    </div>
  );
}
