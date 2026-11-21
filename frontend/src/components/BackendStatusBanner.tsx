import React, { useState, useEffect } from 'react';
import { AlertCircle, RefreshCw, CheckCircle2, WifiOff } from 'lucide-react';
import { api } from '../services/api';

export const BackendStatusBanner: React.FC = () => {
  const [status, setStatus] = useState<'checking' | 'connected' | 'offline'>('checking');
  const [retryCount, setRetryCount] = useState(0);
  const [isRetrying, setIsRetrying] = useState(false);

  const checkConnection = async (manual = false) => {
    if (manual) setIsRetrying(true);
    try {
      await api.getReadiness();
      setStatus('connected');
    } catch {
      setStatus('offline');
      setRetryCount((c) => c + 1);
    } finally {
      if (manual) setIsRetrying(false);
    }
  };

  useEffect(() => {
    checkConnection();
    // Poll health every 20s if connected, or every 8s if offline/waking up
    const intervalTime = status === 'offline' ? 8000 : 25000;
    const interval = setInterval(() => checkConnection(), intervalTime);
    return () => clearInterval(interval);
  }, [status]);

  if (status === 'connected') {
    return null; // Clean, non-intrusive when backend is operational
  }

  return (
    <div className="bg-amber-950/80 border-b border-amber-800/80 text-amber-200 px-4 py-2.5 text-xs font-mono flex items-center justify-between transition-all duration-300">
      <div className="flex items-center space-x-2.5">
        {status === 'offline' ? (
          <WifiOff className="w-4 h-4 text-amber-400 shrink-0 animate-pulse" />
        ) : (
          <RefreshCw className="w-4 h-4 text-amber-400 shrink-0 animate-spin" />
        )}
        <span>
          {status === 'checking'
            ? 'Connecting to DataNexus Backend API...'
            : 'Backend service is starting up (Render containers take ~30s on cold boot). Automatically retrying...'}
        </span>
        {retryCount > 0 && status === 'offline' && (
          <span className="text-amber-400/80 text-[11px]">(Attempt #{retryCount})</span>
        )}
      </div>

      <button
        onClick={() => checkConnection(true)}
        disabled={isRetrying}
        className="flex items-center space-x-1.5 px-2.5 py-1 bg-amber-900/60 hover:bg-amber-800 border border-amber-700/60 rounded text-amber-100 transition disabled:opacity-50"
      >
        <RefreshCw className={`w-3 h-3 ${isRetrying ? 'animate-spin' : ''}`} />
        <span>{isRetrying ? 'Checking...' : 'Retry Now'}</span>
      </button>
    </div>
  );
};
