import React, { useEffect, useState } from 'react';
import {
  FileText,
  CheckCircle2,
  AlertCircle,
  Clock,
  DollarSign,
  ShieldCheck,
  Search,
  Activity,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';
import { api } from '../services/api';
import { OverviewMetrics, ProcessingPerformanceMetric } from '../types';

interface OverviewPageProps {
  onNavigate: (workspace: 'documents' | 'search' | 'data_platform' | 'analytics') => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({ onNavigate }) => {
  const [metrics, setMetrics] = useState<OverviewMetrics | null>(null);
  const [performance, setPerformance] = useState<ProcessingPerformanceMetric[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [m, p] = await Promise.all([
        api.getOverviewMetrics(),
        api.getProcessingPerformance(),
      ]);
      setMetrics(m);
      setPerformance(p);
    } catch (err: any) {
      setError(err.message || 'Failed to load operational overview');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="p-8 space-y-6 animate-pulse">
        <div className="h-8 w-64 bg-slate-800 rounded"></div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 bg-slate-850 rounded-lg border border-slate-800"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error || !metrics) {
    return (
      <div className="p-8">
        <div className="bg-rose-950/40 border border-rose-800 text-rose-300 p-4 rounded-lg flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
            <span>{error || 'Unable to load overview records'}</span>
          </div>
          <button
            onClick={loadData}
            className="px-3 py-1.5 bg-rose-900/60 hover:bg-rose-900 rounded text-xs font-mono"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
            <span>Operational & Platform Overview</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Real-time ingestion health, dimensional pipeline metrics, extraction scorecard, and semantic retrieval coverage.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={loadData}
            className="flex items-center space-x-2 px-3 py-1.5 rounded bg-slate-850 hover:bg-slate-800 border border-slate-700 text-xs font-mono text-slate-300 transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Sync Stats</span>
          </button>
          <button
            onClick={() => onNavigate('documents')}
            className="flex items-center space-x-2 px-3 py-1.5 rounded bg-brand-600 hover:bg-brand-500 text-white text-xs font-medium transition shadow-sm"
          >
            <span>Upload Document</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Primary KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Documents */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono uppercase tracking-wider">
            <span>Total Ingested</span>
            <FileText className="w-4 h-4 text-slate-400" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-3xl font-bold text-white font-mono">{metrics.total_documents}</span>
            <span className="text-xs text-slate-400">files</span>
          </div>
          <div className="mt-3 flex items-center space-x-2 text-xs text-slate-400 border-t border-slate-800/80 pt-2 font-mono">
            <span className="text-emerald-400 font-medium">{metrics.completed_documents} completed</span>
            <span>•</span>
            <span className={metrics.failed_documents > 0 ? 'text-rose-400' : 'text-slate-400'}>
              {metrics.failed_documents} failed
            </span>
          </div>
        </div>

        {/* Total Spend Fact */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono uppercase tracking-wider">
            <span>Verified Spend (USD)</span>
            <DollarSign className="w-4 h-4 text-brand-400" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-3xl font-bold text-brand-400 font-mono">
              ${metrics.total_spend_usd.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </span>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-slate-400 border-t border-slate-800/80 pt-2 font-mono">
            <span>Active Vendors:</span>
            <span className="text-white font-medium">{metrics.active_vendors_count}</span>
          </div>
        </div>

        {/* Quality Scorecard */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono uppercase tracking-wider">
            <span>Data Quality Rate</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-3xl font-bold text-emerald-400 font-mono">{metrics.data_quality_pass_rate}%</span>
            <span className="text-xs text-emerald-500 font-mono">Pass Rate</span>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-slate-400 border-t border-slate-800/80 pt-2 font-mono">
            <span>Deterministic Rules:</span>
            <span className="text-slate-300">8 Active</span>
          </div>
        </div>

        {/* Search Coverage */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono uppercase tracking-wider">
            <span>Indexing Coverage</span>
            <Search className="w-4 h-4 text-sky-400" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-3xl font-bold text-sky-400 font-mono">{metrics.indexing_coverage_rate}%</span>
            <span className="text-xs text-slate-400">Indexed</span>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-slate-400 border-t border-slate-800/80 pt-2 font-mono">
            <span>Backlog Queue:</span>
            <span className={metrics.processing_backlog > 0 ? 'text-amber-400 font-bold' : 'text-slate-400'}>
              {metrics.processing_backlog} waiting
            </span>
          </div>
        </div>
      </div>

      {/* Second Row: Processing Latency & Performance Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Processing Performance by Type */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-lg p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-white">Document Processing Performance by Engine</h3>
              <p className="text-xs text-slate-400 mt-0.5">Average latency, OCR invocation, and search indexing status by file format.</p>
            </div>
            <span className="text-xs font-mono text-slate-400 bg-slate-800 px-2 py-1 rounded">
              Avg Latency: {metrics.avg_processing_time_ms}ms
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-850/80 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">File Format</th>
                  <th className="py-2.5 px-3 text-right">Processed</th>
                  <th className="py-2.5 px-3 text-right">Success</th>
                  <th className="py-2.5 px-3 text-right">Avg Latency</th>
                  <th className="py-2.5 px-3 text-right">Indexed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {performance.map((item, idx) => (
                  <tr key={idx} className="hover:bg-slate-850/40">
                    <td className="py-2.5 px-3 font-semibold text-slate-200">{item.file_type}</td>
                    <td className="py-2.5 px-3 text-right text-slate-300">{item.total_processed}</td>
                    <td className="py-2.5 px-3 text-right text-emerald-400">{item.success_count}</td>
                    <td className="py-2.5 px-3 text-right text-slate-300">{item.avg_duration_ms} ms</td>
                    <td className="py-2.5 px-3 text-right text-sky-400">{item.indexed_count}</td>
                  </tr>
                ))}
                {performance.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-4 text-center text-slate-500">
                      No document processing records found yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Quick Navigation Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 flex flex-col justify-between space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-white">System Architecture & Lineage</h3>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              Every dashboard fact and query in DataNexus is strictly traceable back to its extracted field, page number, and original file hash.
            </p>
          </div>

          <div className="space-y-2 text-xs">
            <button
              onClick={() => onNavigate('search')}
              className="w-full flex items-center justify-between p-3 rounded-md bg-slate-850 hover:bg-slate-800 border border-slate-750 text-slate-200 transition group"
            >
              <div className="flex items-center space-x-2.5">
                <Search className="w-4 h-4 text-brand-400" />
                <span className="font-medium">Hybrid Semantic Search & QA</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-white transition" />
            </button>

            <button
              onClick={() => onNavigate('data_platform')}
              className="w-full flex items-center justify-between p-3 rounded-md bg-slate-850 hover:bg-slate-800 border border-slate-750 text-slate-200 transition group"
            >
              <div className="flex items-center space-x-2.5">
                <Activity className="w-4 h-4 text-emerald-400" />
                <span className="font-medium">ETL Pipeline & Lineage Explorer</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-white transition" />
            </button>

            <button
              onClick={() => onNavigate('analytics')}
              className="w-full flex items-center justify-between p-3 rounded-md bg-slate-850 hover:bg-slate-800 border border-slate-750 text-slate-200 transition group"
            >
              <div className="flex items-center space-x-2.5">
                <DollarSign className="w-4 h-4 text-amber-400" />
                <span className="font-medium">Spend Dashboards & Power BI</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-white transition" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
