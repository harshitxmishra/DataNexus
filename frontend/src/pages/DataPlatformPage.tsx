import React, { useEffect, useState } from 'react';
import {
  Database,
  Play,
  ShieldCheck,
  GitBranch,
  FileSpreadsheet,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  Layers,
  ArrowRight,
  Upload,
} from 'lucide-react';
import { api } from '../services/api';
import { PipelineRun, DataQualityResult, LineageGraph, DocumentItem } from '../types';

interface DataPlatformPageProps {
  initialDocumentId?: string;
}

export const DataPlatformPage: React.FC<DataPlatformPageProps> = ({ initialDocumentId }) => {
  const [activeTab, setActiveTab] = useState<'pipelines' | 'quality' | 'lineage' | 'csv'>('pipelines');
  const [pipelineRuns, setPipelineRuns] = useState<PipelineRun[]>([]);
  const [qualityResults, setQualityResults] = useState<DataQualityResult[]>([]);
  const [qualityScorecard, setQualityScorecard] = useState<any>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>(initialDocumentId || '');
  const [lineageGraph, setLineageGraph] = useState<LineageGraph | null>(null);

  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvUploadResult, setCsvUploadResult] = useState<any>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const [runs, qRes, scorecard, docs] = await Promise.all([
        api.listPipelineRuns(),
        api.listQualityResults(),
        api.getQualityScorecard(),
        api.listDocuments(),
      ]);
      setPipelineRuns(runs);
      setQualityResults(qRes);
      setQualityScorecard(scorecard);
      setDocuments(docs);

      const targetId = selectedDocId || (docs.length > 0 ? docs[0].id : '');
      if (targetId) {
        setSelectedDocId(targetId);
        const lin = await api.getDocumentLineage(targetId);
        setLineageGraph(lin);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSelectLineageDoc = async (id: string) => {
    setSelectedDocId(id);
    try {
      const lin = await api.getDocumentLineage(id);
      setLineageGraph(lin);
    } catch (e) {
      console.error(e);
    }
  };

  const handleTriggerPipeline = async () => {
    try {
      setTriggering(true);
      await api.triggerPipeline();
      await loadData();
    } catch (e: any) {
      alert(`Pipeline error: ${e.message}`);
    } finally {
      setTriggering(false);
    }
  };

  const handleCsvSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!csvFile) return;
    try {
      const formData = new FormData();
      formData.append('file', csvFile);
      const res = await api.ingestCsv(formData);
      setCsvUploadResult(res);
      await loadData();
    } catch (e: any) {
      alert(`CSV ingest failed: ${e.message}`);
    }
  };

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
            <span>Data Engineering & Lineage Platform</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Reproducible dimensional SQL transformations, automated data quality evaluations, and complete trace lineage.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={loadData}
            className="p-2 rounded bg-slate-850 hover:bg-slate-800 border border-slate-700 text-slate-300 transition"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-brand-400' : ''}`} />
          </button>
          <button
            onClick={handleTriggerPipeline}
            disabled={triggering}
            className="flex items-center space-x-2 px-3.5 py-2 rounded bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold font-mono transition shadow-sm"
          >
            <Play className={`w-3.5 h-3.5 ${triggering ? 'animate-pulse' : ''}`} />
            <span>{triggering ? 'Executing Batch...' : 'Trigger ETL Pipeline'}</span>
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center space-x-2 border-b border-slate-800 pb-2 text-xs font-mono">
        <button
          onClick={() => setActiveTab('pipelines')}
          className={`px-3.5 py-1.5 rounded-md transition ${
            activeTab === 'pipelines'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          ETL Pipelines ({pipelineRuns.length})
        </button>
        <button
          onClick={() => setActiveTab('quality')}
          className={`px-3.5 py-1.5 rounded-md transition ${
            activeTab === 'quality'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Data Quality Scorecard ({qualityResults.length})
        </button>
        <button
          onClick={() => setActiveTab('lineage')}
          className={`px-3.5 py-1.5 rounded-md transition ${
            activeTab === 'lineage'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Trace Lineage Explorer
        </button>
        <button
          onClick={() => setActiveTab('csv')}
          className={`px-3.5 py-1.5 rounded-md transition ${
            activeTab === 'csv'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          CSV Ingest & Staging
        </button>
      </div>

      {/* TAB 1: PIPELINE RUNS */}
      {activeTab === 'pipelines' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-850/80 text-slate-400 border-b border-slate-800 uppercase text-[11px]">
                  <tr>
                    <th className="py-3 px-4">Pipeline</th>
                    <th className="py-3 px-4">Batch ID</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-3 text-right">Rows Read</th>
                    <th className="py-3 px-3 text-right">Inserted</th>
                    <th className="py-3 px-3 text-right">Updated</th>
                    <th className="py-3 px-3 text-right">Rejected</th>
                    <th className="py-3 px-4 text-right">Duration</th>
                    <th className="py-3 px-4 text-right">Executed At</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {pipelineRuns.map((run) => (
                    <tr key={run.id} className="hover:bg-slate-850/40">
                      <td className="py-3 px-4 font-semibold text-slate-200">{run.pipeline_name}</td>
                      <td className="py-3 px-4 text-brand-400">{run.batch_id}</td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                            run.status === 'success'
                              ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                              : 'bg-amber-950 text-amber-400 border border-amber-800'
                          }`}
                        >
                          {run.status}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right text-slate-300">{run.rows_read}</td>
                      <td className="py-3 px-3 text-right text-emerald-400">{run.rows_inserted}</td>
                      <td className="py-3 px-3 text-right text-sky-400">{run.rows_updated}</td>
                      <td className="py-3 px-3 text-right text-rose-400">{run.rows_rejected}</td>
                      <td className="py-3 px-4 text-right text-slate-400">{run.duration_ms} ms</td>
                      <td className="py-3 px-4 text-right text-slate-500 text-[11px]">
                        {new Date(run.created_at).toLocaleTimeString()}
                      </td>
                    </tr>
                  ))}
                  {pipelineRuns.length === 0 && (
                    <tr>
                      <td colSpan={9} className="py-6 text-center text-slate-500">
                        No pipeline runs recorded yet. Click "Trigger ETL Pipeline" above.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: DATA QUALITY */}
      {activeTab === 'quality' && (
        <div className="space-y-6">
          {/* Quality Scorecard Banner */}
          {qualityScorecard && (
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                <span className="text-xs text-slate-400 uppercase font-mono">Evaluations</span>
                <div className="text-2xl font-bold text-white font-mono mt-1">
                  {qualityScorecard.total_evaluations}
                </div>
              </div>
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                <span className="text-xs text-emerald-400 uppercase font-mono">Passed Rules</span>
                <div className="text-2xl font-bold text-emerald-400 font-mono mt-1">
                  {qualityScorecard.passed}
                </div>
              </div>
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                <span className="text-xs text-amber-400 uppercase font-mono">Warnings</span>
                <div className="text-2xl font-bold text-amber-400 font-mono mt-1">
                  {qualityScorecard.warnings}
                </div>
              </div>
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                <span className="text-xs text-rose-400 uppercase font-mono">Failed Violations</span>
                <div className="text-2xl font-bold text-rose-400 font-mono mt-1">
                  {qualityScorecard.failed}
                </div>
              </div>
            </div>
          )}

          {/* Quality Rules Table */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-850/80 text-slate-400 border-b border-slate-800 uppercase text-[11px]">
                  <tr>
                    <th className="py-3 px-4">Rule Name</th>
                    <th className="py-3 px-4">Category</th>
                    <th className="py-3 px-3">Status</th>
                    <th className="py-3 px-3">Severity</th>
                    <th className="py-3 px-4">Metric Value</th>
                    <th className="py-3 px-4">Threshold</th>
                    <th className="py-3 px-4">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {qualityResults.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-850/40">
                      <td className="py-3 px-4 font-semibold text-slate-200">{r.rule_name}</td>
                      <td className="py-3 px-4 text-slate-400 uppercase text-[10px]">{r.rule_category}</td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                            r.status === 'pass'
                              ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                              : r.status === 'warning'
                              ? 'bg-amber-950 text-amber-400 border border-amber-800'
                              : 'bg-rose-950 text-rose-400 border border-rose-800'
                          }`}
                        >
                          {r.status.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-400 uppercase text-[10px]">{r.severity}</td>
                      <td className="py-3 px-4 text-slate-300 font-medium">{r.metric_value || '—'}</td>
                      <td className="py-3 px-4 text-slate-500">{r.threshold || '—'}</td>
                      <td className="py-3 px-4 text-slate-400 truncate max-w-xs">{r.details}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: TRACE LINEAGE EXPLORER */}
      {activeTab === 'lineage' && (
        <div className="space-y-6">
          <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="text-xs font-mono text-slate-300">
              Select Document Anchor to Trace Multi-Hop Transformation Lineage:
            </div>
            <select
              value={selectedDocId}
              onChange={(e) => handleSelectLineageDoc(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-slate-200 font-mono focus:outline-none"
            >
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.filename} ({d.id.substring(0, 8)})
                </option>
              ))}
            </select>
          </div>

          {lineageGraph && (
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-6 shadow-sm">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3 text-xs font-mono">
                <div>
                  Anchor Document: <span className="text-brand-300 font-bold">{selectedDocId}</span>
                </div>
                <div className="text-slate-400">
                  {lineageGraph.nodes_count} Nodes • {lineageGraph.edges_count} Transformation Edges
                </div>
              </div>

              {/* Lineage Directed Pathway Visualizer */}
              <div className="space-y-3 font-mono">
                <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold">
                  Recorded Transformation Edges (Source → Rule → Target)
                </div>
                <div className="space-y-2">
                  {lineageGraph.edges.map((edge, i) => (
                    <div
                      key={edge.id || i}
                      className="flex flex-col sm:flex-row sm:items-center justify-between p-3 rounded bg-slate-950 border border-slate-850 hover:border-slate-750 transition text-xs gap-2"
                    >
                      <div className="flex items-center space-x-2">
                        <span className="text-slate-400 px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-[10px] uppercase font-semibold">
                          {edge.source_type}
                        </span>
                        <span className="text-slate-200 truncate max-w-xs">{edge.source}</span>
                      </div>

                      <div className="flex items-center space-x-2 text-brand-400 text-[11px] font-semibold">
                        <ArrowRight className="w-3.5 h-3.5" />
                        <span className="px-2 py-0.5 rounded bg-brand-950/80 border border-brand-800/80">
                          {edge.rule}
                        </span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </div>

                      <div className="flex items-center space-x-2">
                        <span className="text-slate-400 px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-[10px] uppercase font-semibold">
                          {edge.target_type}
                        </span>
                        <span className="text-emerald-400 font-bold truncate max-w-xs">{edge.target}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 4: CSV INGEST */}
      {activeTab === 'csv' && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-6 max-w-2xl">
          <div>
            <h3 className="text-sm font-semibold text-white">Ingest Tabular Master CSV Dataset</h3>
            <p className="text-xs text-slate-400 mt-1">
              Supports schema inspection, column typing, staging tables, and rejected-row drift reporting.
            </p>
          </div>

          <form onSubmit={handleCsvSubmit} className="space-y-4">
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setCsvFile(e.target.files ? e.target.files[0] : null)}
              className="block w-full text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-brand-600 file:text-white hover:file:bg-brand-500 cursor-pointer"
            />
            <button
              type="submit"
              disabled={!csvFile}
              className="px-4 py-2 rounded bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold font-mono disabled:opacity-50 transition"
            >
              Stage & Validate CSV
            </button>
          </form>

          {csvUploadResult && (
            <div className="bg-slate-950 border border-slate-800 p-4 rounded-lg text-xs font-mono space-y-2">
              <div className="text-emerald-400 font-semibold">CSV Staged Successfully:</div>
              <div>Batch ID: {csvUploadResult.batch_id}</div>
              <div>Total Rows: {csvUploadResult.total_rows}</div>
              <div>Staged Rows: {csvUploadResult.staged_rows}</div>
              <div>Rejected Rows: {csvUploadResult.rejected_rows}</div>
              <div>Columns: {csvUploadResult.columns?.join(', ')}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
