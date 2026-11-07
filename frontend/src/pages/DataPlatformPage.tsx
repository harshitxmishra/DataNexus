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
  Info,
  ChevronRight,
  Sparkles,
  Filter,
} from 'lucide-react';
import { api } from '../services/api';
import {
  PipelineRun,
  DataQualityResult,
  DetailedScorecard,
  LineageGraph,
  LineageNode,
  DocumentItem
} from '../types';

interface DataPlatformPageProps {
  initialDocumentId?: string;
}

export const DataPlatformPage: React.FC<DataPlatformPageProps> = ({ initialDocumentId }) => {
  const [activeTab, setActiveTab] = useState<'pipelines' | 'quality' | 'lineage' | 'csv'>('pipelines');
  const [pipelineRuns, setPipelineRuns] = useState<PipelineRun[]>([]);
  const [qualityResults, setQualityResults] = useState<DataQualityResult[]>([]);
  const [qualityScorecard, setQualityScorecard] = useState<DetailedScorecard | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>(initialDocumentId || '');
  const [lineageGraph, setLineageGraph] = useState<LineageGraph | null>(null);
  const [lineageDirection, setLineageDirection] = useState<'document' | 'all' | 'upstream' | 'downstream'>('document');
  const [selectedNode, setSelectedNode] = useState<LineageNode | null>(null);

  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [evaluatingQuality, setEvaluatingQuality] = useState(false);
  const [qualityStatusFilter, setQualityStatusFilter] = useState<string>('all');
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
        const lin = await api.getDocumentLineage(targetId, lineageDirection);
        setLineageGraph(lin);
        if (lin.nodes.length > 0) {
          setSelectedNode(lin.nodes[0]);
        }
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

  const handleSelectLineageDoc = async (id: string, dir: 'document' | 'all' | 'upstream' | 'downstream' = lineageDirection) => {
    setSelectedDocId(id);
    try {
      const lin = await api.getDocumentLineage(id, dir);
      setLineageGraph(lin);
      if (lin.nodes.length > 0) {
        setSelectedNode(lin.nodes[0]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleLineageDirectionChange = async (dir: 'document' | 'all' | 'upstream' | 'downstream') => {
    setLineageDirection(dir);
    if (selectedDocId) {
      await handleSelectLineageDoc(selectedDocId, dir);
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

  const handleRunQualityEvaluation = async () => {
    try {
      setEvaluatingQuality(true);
      const res = await api.evaluateQuality();
      setQualityScorecard(res.scorecard);
      const qRes = await api.listQualityResults();
      setQualityResults(qRes);
    } catch (e: any) {
      alert(`Quality evaluation failed: ${e.message}`);
    } finally {
      setEvaluatingQuality(false);
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

  const filteredQualityResults = qualityResults.filter((r) => {
    if (qualityStatusFilter === 'all') return true;
    return r.status === qualityStatusFilter;
  });

  const getNodeTypeBadge = (type: string) => {
    switch (type) {
      case 'file':
        return 'bg-blue-950 text-blue-400 border-blue-800';
      case 'document':
        return 'bg-cyan-950 text-cyan-400 border-cyan-800';
      case 'extracted_field':
        return 'bg-amber-950 text-amber-400 border-amber-800';
      case 'fact_invoice':
        return 'bg-emerald-950 text-emerald-400 border-emerald-800';
      case 'view':
        return 'bg-purple-950 text-purple-400 border-purple-800';
      case 'metric':
        return 'bg-rose-950 text-rose-400 border-rose-800';
      default:
        return 'bg-slate-900 text-slate-400 border-slate-800';
    }
  };

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
            <span>Data Platform Engineering & Governance</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Deterministic Kimball dimensional pipelines, 11-rule automated data quality auditing, and interactive multi-hop lineage graph.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={handleTriggerPipeline}
            disabled={triggering}
            className="flex items-center space-x-2 px-3.5 py-2 rounded bg-brand-600 hover:bg-brand-500 text-white text-xs font-mono font-medium disabled:opacity-50 transition"
          >
            {triggering ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            <span>{triggering ? 'Running Pipeline...' : 'Run Dimensional ETL'}</span>
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center space-x-2 border-b border-slate-800 pb-2 text-xs font-mono">
        <button
          onClick={() => setActiveTab('pipelines')}
          className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-md transition ${
            activeTab === 'pipelines'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          <span>Pipelines & Batches ({pipelineRuns.length})</span>
        </button>
        <button
          onClick={() => setActiveTab('quality')}
          className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-md transition ${
            activeTab === 'quality'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Data Quality Scorecard ({qualityScorecard?.pass_rate_percentage || 100}%)</span>
        </button>
        <button
          onClick={() => setActiveTab('lineage')}
          className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-md transition ${
            activeTab === 'lineage'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <GitBranch className="w-3.5 h-3.5" />
          <span>Multi-Hop Lineage Graph</span>
        </button>
        <button
          onClick={() => setActiveTab('csv')}
          className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-md transition ${
            activeTab === 'csv'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileSpreadsheet className="w-3.5 h-3.5" />
          <span>Tabular Master CSV Ingest</span>
        </button>
      </div>

      {/* TAB 1: PIPELINES */}
      {activeTab === 'pipelines' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <h3 className="text-xs font-mono uppercase text-slate-300 font-semibold">
                Historical ETL Executions & Throughput
              </h3>
              <span className="text-xs font-mono text-slate-400">{pipelineRuns.length} runs recorded</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-850/80 text-slate-400 border-b border-slate-800 uppercase text-[11px]">
                  <tr>
                    <th className="py-3 px-4">Pipeline</th>
                    <th className="py-3 px-4">Batch ID</th>
                    <th className="py-3 px-3">Status</th>
                    <th className="py-3 px-3 text-right">Read</th>
                    <th className="py-3 px-3 text-right">Inserted</th>
                    <th className="py-3 px-3 text-right">Updated</th>
                    <th className="py-3 px-3 text-right">Rejected</th>
                    <th className="py-3 px-3 text-right">Duration</th>
                    <th className="py-3 px-4">Executed At</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {pipelineRuns.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-850/40">
                      <td className="py-3 px-4 font-semibold text-slate-200">{r.pipeline_name}</td>
                      <td className="py-3 px-4 text-slate-400">{r.batch_id}</td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                            r.status === 'success'
                              ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                              : 'bg-amber-950 text-amber-400 border border-amber-800'
                          }`}
                        >
                          {r.status.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right text-slate-300">{r.rows_read}</td>
                      <td className="py-3 px-3 text-right text-emerald-400 font-semibold">{r.rows_inserted}</td>
                      <td className="py-3 px-3 text-right text-brand-400 font-semibold">{r.rows_updated}</td>
                      <td className="py-3 px-3 text-right text-rose-400 font-semibold">{r.rows_rejected}</td>
                      <td className="py-3 px-3 text-right text-slate-400">{r.duration_ms}ms</td>
                      <td className="py-3 px-4 text-slate-500">{new Date(r.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                  {pipelineRuns.length === 0 && (
                    <tr>
                      <td colSpan={9} className="py-8 text-center text-slate-500">
                        No pipeline runs recorded yet. Click 'Run Dimensional ETL' to initiate execution.
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
            <div className="grid grid-cols-1 sm:grid-cols-5 gap-4">
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                <span className="text-xs text-slate-400 uppercase font-mono">Total Evaluations</span>
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
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-brand-300 uppercase font-mono">Pass Rate</span>
                  <button
                    onClick={handleRunQualityEvaluation}
                    disabled={evaluatingQuality}
                    className="text-[10px] bg-brand-950 text-brand-300 border border-brand-800 px-2 py-0.5 rounded font-mono hover:bg-brand-900 disabled:opacity-50"
                  >
                    {evaluatingQuality ? 'Evaluating...' : 'Re-run'}
                  </button>
                </div>
                <div className="text-2xl font-bold text-brand-400 font-mono mt-1">
                  {qualityScorecard.pass_rate_percentage}%
                </div>
              </div>
            </div>
          )}

          {/* Category Breakdown Cards */}
          {qualityScorecard?.by_category && qualityScorecard.by_category.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
              {qualityScorecard.by_category.map((cat) => (
                <div key={cat.rule_category} className="bg-slate-950 border border-slate-850 p-3 rounded-lg font-mono text-xs">
                  <div className="text-slate-400 uppercase text-[10px] font-semibold">{cat.rule_category}</div>
                  <div className="flex items-baseline justify-between mt-1">
                    <span className="text-white font-bold">{cat.pass_percentage}%</span>
                    <span className="text-slate-500 text-[11px]">{cat.passed}/{cat.total_evaluations} pass</span>
                  </div>
                  <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        cat.pass_percentage >= 95 ? 'bg-emerald-500' : cat.pass_percentage >= 80 ? 'bg-amber-500' : 'bg-rose-500'
                      }`}
                      style={{ width: `${cat.pass_percentage}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Rule Compliance Breakdown Table */}
          {qualityScorecard?.by_rule && qualityScorecard.by_rule.length > 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
              <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                <h3 className="text-xs font-mono uppercase text-slate-300 font-semibold">
                  Rule-by-Rule Compliance & Governance Summary
                </h3>
                <span className="text-xs font-mono text-slate-400">11 Active Deterministic Rules</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-slate-850/80 text-slate-400 border-b border-slate-800 uppercase text-[11px]">
                    <tr>
                      <th className="py-2.5 px-4">Rule Name</th>
                      <th className="py-2.5 px-3">Category</th>
                      <th className="py-2.5 px-3">Severity</th>
                      <th className="py-2.5 px-3 text-right">Evaluations</th>
                      <th className="py-2.5 px-3 text-right">Pass</th>
                      <th className="py-2.5 px-3 text-right">Warn</th>
                      <th className="py-2.5 px-3 text-right">Fail</th>
                      <th className="py-2.5 px-4 text-right">Pass Rate</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {qualityScorecard.by_rule.map((r) => (
                      <tr key={r.rule_name} className="hover:bg-slate-850/40">
                        <td className="py-2 px-4 font-semibold text-slate-200">{r.rule_name}</td>
                        <td className="py-2 px-3 text-slate-400 uppercase text-[10px]">{r.rule_category}</td>
                        <td className="py-2 px-3">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-semibold ${
                              r.severity === 'critical'
                                ? 'bg-rose-950 text-rose-400 border border-rose-800'
                                : r.severity === 'high'
                                ? 'bg-amber-950 text-amber-400 border border-amber-800'
                                : 'bg-slate-850 text-slate-400 border border-slate-700'
                            }`}
                          >
                            {r.severity}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right text-slate-400">{r.total_evaluations}</td>
                        <td className="py-2 px-3 text-right text-emerald-400 font-semibold">{r.passed}</td>
                        <td className="py-2 px-3 text-right text-amber-400">{r.warnings}</td>
                        <td className="py-2 px-3 text-right text-rose-400 font-semibold">{r.failed}</td>
                        <td className="py-2 px-4 text-right font-bold text-slate-200">{r.pass_percentage}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Filter Bar & Detailed Evaluations Log */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
            <div className="p-4 border-b border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div className="flex items-center space-x-2">
                <Filter className="w-3.5 h-3.5 text-slate-400" />
                <span className="text-xs font-mono uppercase text-slate-300 font-semibold">
                  Detailed Rule Evaluations Log
                </span>
              </div>
              <div className="flex items-center space-x-2 text-xs font-mono">
                <span className="text-slate-400">Filter Status:</span>
                {(['all', 'pass', 'warning', 'fail'] as const).map((st) => (
                  <button
                    key={st}
                    onClick={() => setQualityStatusFilter(st)}
                    className={`px-2 py-1 rounded text-[11px] uppercase font-semibold transition ${
                      qualityStatusFilter === st
                        ? 'bg-brand-600 text-white'
                        : 'bg-slate-850 text-slate-400 hover:text-white border border-slate-800'
                    }`}
                  >
                    {st}
                  </button>
                ))}
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-850/80 text-slate-400 border-b border-slate-800 uppercase text-[11px]">
                  <tr>
                    <th className="py-3 px-4">Rule Name</th>
                    <th className="py-3 px-3">Category</th>
                    <th className="py-3 px-3">Status</th>
                    <th className="py-3 px-3">Severity</th>
                    <th className="py-3 px-4">Metric Value</th>
                    <th className="py-3 px-4">Threshold</th>
                    <th className="py-3 px-4">Audit Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {filteredQualityResults.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-850/40">
                      <td className="py-2.5 px-4 font-semibold text-slate-200">{r.rule_name}</td>
                      <td className="py-2.5 px-3 text-slate-400 uppercase text-[10px]">{r.rule_category}</td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                            r.status === 'pass'
                              ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                              : r.status === 'warning'
                              ? 'bg-amber-950 text-amber-400 border border-amber-800'
                              : 'bg-rose-950 text-rose-400 border border-rose-800'
                          }`}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-400 uppercase text-[10px]">{r.severity}</td>
                      <td className="py-2.5 px-4 text-slate-300 font-medium">{r.metric_value || '—'}</td>
                      <td className="py-2.5 px-4 text-slate-500">{r.threshold || '—'}</td>
                      <td className="py-2.5 px-4 text-slate-400 truncate max-w-sm">{r.details}</td>
                    </tr>
                  ))}
                  {filteredQualityResults.length === 0 && (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-500">
                        No quality evaluations matching the selected filter.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: TRACE LINEAGE EXPLORER */}
      {activeTab === 'lineage' && (
        <div className="space-y-6">
          {/* Controls Bar */}
          <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg flex flex-col sm:flex-row items-center justify-between gap-4 font-mono text-xs">
            <div className="flex items-center space-x-3 w-full sm:w-auto">
              <span className="text-slate-400 whitespace-nowrap">Anchor Document:</span>
              <select
                value={selectedDocId}
                onChange={(e) => handleSelectLineageDoc(e.target.value)}
                className="bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-slate-200 font-mono focus:outline-none w-full sm:w-80"
              >
                {documents.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.filename} ({d.id.substring(0, 8)})
                  </option>
                ))}
              </select>
            </div>

            {/* Direction Selector */}
            <div className="flex items-center space-x-1.5">
              <span className="text-slate-400 text-[11px] mr-1">Traversal Scope:</span>
              {(['document', 'upstream', 'downstream', 'all'] as const).map((dir) => (
                <button
                  key={dir}
                  onClick={() => handleLineageDirectionChange(dir)}
                  className={`px-2.5 py-1 rounded text-[11px] font-semibold transition capitalize ${
                    lineageDirection === dir
                      ? 'bg-brand-600 text-white'
                      : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
                  }`}
                >
                  {dir === 'document' ? 'Document Pipeline' : dir}
                </button>
              ))}
            </div>
          </div>

          {/* Pipeline Stage Architecture Flow Pills */}
          <div className="flex items-center justify-center space-x-2 py-2 overflow-x-auto text-xs font-mono">
            <span className="px-3 py-1 rounded-full bg-blue-950 border border-blue-800 text-blue-400 font-semibold">1. Raw Binary File</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-600 shrink-0" />
            <span className="px-3 py-1 rounded-full bg-cyan-950 border border-cyan-800 text-cyan-400 font-semibold">2. Parsed Document</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-600 shrink-0" />
            <span className="px-3 py-1 rounded-full bg-amber-950 border border-amber-800 text-amber-400 font-semibold">3. Extracted Fields</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-600 shrink-0" />
            <span className="px-3 py-1 rounded-full bg-emerald-950 border border-emerald-800 text-emerald-400 font-semibold">4. Fact Invoice</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-600 shrink-0" />
            <span className="px-3 py-1 rounded-full bg-purple-950 border border-purple-800 text-purple-400 font-semibold">5. SQL View</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-600 shrink-0" />
            <span className="px-3 py-1 rounded-full bg-rose-950 border border-rose-800 text-rose-400 font-semibold">6. BI Metric</span>
          </div>

          {/* Graph View & Node Inspector */}
          {lineageGraph && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Edges List Visualizer */}
              <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-4 shadow-sm">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3 text-xs font-mono">
                  <div>
                    Trace Anchor: <span className="text-brand-300 font-bold">{selectedDocId.substring(0, 12)}...</span>
                  </div>
                  <div className="text-slate-400">
                    {lineageGraph.nodes_count} Nodes • {lineageGraph.edges_count} Transformation Edges
                  </div>
                </div>

                <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1 font-mono">
                  {lineageGraph.edges.map((edge, i) => (
                    <div
                      key={edge.id || i}
                      className="flex flex-col sm:flex-row sm:items-center justify-between p-3 rounded bg-slate-950 border border-slate-850 hover:border-slate-700 transition text-xs gap-2"
                    >
                      <button
                        onClick={() => {
                          const n = lineageGraph.nodes.find((x) => x.id === edge.source);
                          if (n) setSelectedNode(n);
                        }}
                        className="flex items-center space-x-2 text-left"
                      >
                        <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-semibold border ${getNodeTypeBadge(edge.source_type)}`}>
                          {edge.source_type}
                        </span>
                        <span className="text-slate-200 truncate max-w-[140px] hover:text-brand-300 transition">
                          {edge.source}
                        </span>
                      </button>

                      <div className="flex items-center space-x-1.5 text-brand-400 text-[11px] font-semibold shrink-0">
                        <ArrowRight className="w-3 h-3 text-slate-500" />
                        <span className="px-2 py-0.5 rounded bg-brand-950/80 border border-brand-800/80 text-[10px]">
                          {edge.rule}
                        </span>
                        <ArrowRight className="w-3 h-3 text-slate-500" />
                      </div>

                      <button
                        onClick={() => {
                          const n = lineageGraph.nodes.find((x) => x.id === edge.target);
                          if (n) setSelectedNode(n);
                        }}
                        className="flex items-center space-x-2 text-left"
                      >
                        <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-semibold border ${getNodeTypeBadge(edge.target_type)}`}>
                          {edge.target_type}
                        </span>
                        <span className="text-emerald-400 font-bold truncate max-w-[140px] hover:text-brand-300 transition">
                          {edge.target}
                        </span>
                      </button>
                    </div>
                  ))}
                  {lineageGraph.edges.length === 0 && (
                    <div className="py-8 text-center text-slate-500 text-xs">
                      No lineage transformation edges found for the selected direction.
                    </div>
                  )}
                </div>
              </div>

              {/* Node Inspector Panel */}
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-4 font-mono text-xs">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <span className="uppercase text-slate-400 font-semibold text-[11px]">Node Provenance Inspector</span>
                  {selectedNode && (
                    <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-semibold border ${getNodeTypeBadge(selectedNode.type)}`}>
                      {selectedNode.type}
                    </span>
                  )}
                </div>

                {selectedNode ? (
                  <div className="space-y-3">
                    <div>
                      <span className="text-slate-500 text-[10px] uppercase">Node Identifier:</span>
                      <div className="text-white font-semibold break-all mt-0.5">{selectedNode.id}</div>
                    </div>
                    <div>
                      <span className="text-slate-500 text-[10px] uppercase">Display Label:</span>
                      <div className="text-brand-300 mt-0.5">{selectedNode.label}</div>
                    </div>

                    {selectedNode.metadata && Object.keys(selectedNode.metadata).length > 0 && (
                      <div className="space-y-2 pt-2 border-t border-slate-800">
                        <span className="text-slate-500 text-[10px] uppercase font-semibold">Entity Attributes:</span>
                        <div className="bg-slate-950 p-3 rounded border border-slate-850 space-y-1.5 text-[11px]">
                          {Object.entries(selectedNode.metadata).map(([k, v]) => (
                            <div key={k} className="flex justify-between items-start gap-2">
                              <span className="text-slate-400 capitalize">{k.replace(/_/g, ' ')}:</span>
                              <span className="text-slate-200 font-medium text-right break-all">{String(v ?? '—')}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="py-8 text-center text-slate-500">
                    Click any node or edge to inspect its full provenance metadata.
                  </div>
                )}
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
