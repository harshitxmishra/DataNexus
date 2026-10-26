import React, { useEffect, useState } from 'react';
import { Database, Search, Cpu, RefreshCw, CheckCircle2, AlertTriangle, Layers } from 'lucide-react';
import { api } from '../services/api';
import { SystemReadiness } from '../types';

export const Navbar: React.FC = () => {
  const [readiness, setReadiness] = useState<SystemReadiness | null>(null);
  const [loading, setLoading] = useState(false);

  const checkHealth = async () => {
    try {
      setLoading(true);
      const data = await api.getReadiness();
      setReadiness(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-14 border-b border-slate-800 bg-slate-925 px-5 flex items-center justify-between sticky top-0 z-30 select-none">
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center font-bold text-white shadow-sm ring-1 ring-brand-400/30">
            <Layers className="w-4 h-4 text-white" />
          </div>
          <div>
            <span className="font-bold tracking-tight text-white text-base">DataNexus</span>
            <span className="text-[10px] uppercase font-mono tracking-widest text-brand-400 bg-brand-950/80 px-1.5 py-0.5 ml-2 rounded border border-brand-800/60">
              v1.0.0
            </span>
          </div>
        </div>
        <div className="hidden md:flex items-center space-x-2 pl-3 border-l border-slate-800 text-xs text-slate-400 font-mono">
          <span>Document Intelligence</span>
          <span>•</span>
          <span>Semantic Retrieval</span>
          <span>•</span>
          <span>Analytical Lineage</span>
        </div>
      </div>

      <div className="flex items-center space-x-3">
        {/* Readiness Badges */}
        {readiness && (
          <div className="hidden lg:flex items-center space-x-2 text-xs font-mono">
            {/* Database */}
            <div className="flex items-center space-x-1.5 px-2 py-1 rounded bg-slate-900 border border-slate-800 text-slate-300">
              <Database className="w-3.5 h-3.5 text-emerald-400" />
              <span>{readiness.database.dialect}</span>
              <span className="text-slate-500">({readiness.database.latency_ms}ms)</span>
            </div>

            {/* Elasticsearch / Search Engine */}
            <div className="flex items-center space-x-1.5 px-2 py-1 rounded bg-slate-900 border border-slate-800 text-slate-300">
              <Search className="w-3.5 h-3.5 text-brand-400" />
              <span>
                {readiness.elasticsearch.status === 'connected' ? 'Elasticsearch' : 'Local Search (RRF)'}
              </span>
            </div>

            {/* Embeddings */}
            <div className="flex items-center space-x-1.5 px-2 py-1 rounded bg-slate-900 border border-slate-800 text-slate-300">
              <Cpu className="w-3.5 h-3.5 text-amber-400" />
              <span>{readiness.embedding_provider.dimension}d Vectors</span>
            </div>
          </div>
        )}

        <button
          onClick={checkHealth}
          disabled={loading}
          className="p-1.5 text-slate-400 hover:text-white rounded-md hover:bg-slate-800 transition"
          title="Refresh System Readiness"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-brand-400' : ''}`} />
        </button>
      </div>
    </header>
  );
};
