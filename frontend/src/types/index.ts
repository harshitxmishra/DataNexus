export interface StageEvent {
  id: string;
  stage: string;
  status: string;
  duration_ms: number | null;
  details: string | null;
  error_message: string | null;
  created_at: string;
}

export interface ExtractedField {
  id: string;
  field_name: string;
  field_value: string;
  normalized_value: string | null;
  page_number: number;
  supporting_text: string | null;
  start_char: number | null;
  end_char: number | null;
  confidence: number | null;
  extraction_method: string;
  validation_status: string;
  created_at: string;
}

export interface InvoiceLineItem {
  id: string;
  line_number: number;
  description: string;
  quantity: number;
  unit_price: number;
  amount: number;
  page_number: number;
  confidence: number | null;
}

export interface DocumentChunk {
  id: string;
  chunk_index: number;
  page_number: number;
  start_char: number;
  end_char: number;
  content: string;
  indexed_in_es: boolean;
}

export interface DocumentItem {
  id: string;
  filename: string;
  original_name: string;
  file_type: string;
  file_size: number;
  file_hash: string;
  status: string;
  document_type: string;
  page_count: number;
  chunk_count: number;
  is_duplicate: boolean;
  extraction_confidence: number | null;
  created_at: string;
  processed_at: string | null;
  error_message: string | null;
}

export interface DocumentDetail extends DocumentItem {
  storage_path: string;
  character_count: number;
  version: number;
  stage_events: StageEvent[];
  extracted_fields: ExtractedField[];
  line_items: InvoiceLineItem[];
  chunks: DocumentChunk[];
}

export interface OverviewMetrics {
  total_documents: number;
  completed_documents: number;
  processing_backlog: number;
  failed_documents: number;
  total_spend_usd: number;
  avg_processing_time_ms: number;
  data_quality_pass_rate: number;
  indexing_coverage_rate: number;
  recent_pipeline_runs_count: number;
  active_vendors_count: number;
}

export interface VendorSpendItem {
  vendor_name: string;
  vendor_category: string;
  currency: string;
  invoice_count: number;
  total_subtotal: number;
  total_tax: number;
  total_spend: number;
  avg_confidence: number;
}

export interface OverdueInvoiceItem {
  invoice_number: string;
  vendor_name: string;
  currency: string;
  total_amount: number;
  payment_status: string;
  days_overdue: number;
  invoice_date: string;
  due_date: string | null;
  document_id: string;
}

export interface SpendTrendItem {
  period: string;
  invoice_count: number;
  total_spend: number;
  currency: string;
}

export interface ProcessingPerformanceMetric {
  file_type: string;
  total_processed: number;
  success_count: number;
  failure_count: number;
  avg_duration_ms: number;
  ocr_count: number;
  indexed_count: number;
}

export interface SearchHitItem {
  chunk_id: string;
  document_id: string;
  filename: string;
  document_type: string;
  page_number: number;
  content: string;
  snippet: string;
  score: number;
  lexical_score: number;
  vector_score: number;
  retrieval_mode: string;
}

export interface SearchResponse {
  query: string;
  provider: string;
  engine: string;
  retrieval_mode: string;
  total_hits: number;
  results: SearchHitItem[];
}

export interface QACitation {
  document_id: string;
  filename: string;
  page_number: number;
  snippet: string;
  chunk_id: string;
}

export interface QAResponse {
  question: string;
  answer: string;
  evidence_status: string;
  citations: QACitation[];
  provider_used: string;
  latency_ms: number;
}

export interface PipelineRun {
  id: string;
  pipeline_name: string;
  batch_id: string;
  status: string;
  start_time: string;
  end_time: string | null;
  duration_ms: number | null;
  rows_read: number;
  rows_inserted: number;
  rows_updated: number;
  rows_rejected: number;
  source_range: string | null;
  error_details: string | null;
  created_at: string;
}

export interface DataQualityResult {
  id: string;
  rule_name: string;
  rule_category: string;
  evaluated_entity_type: string;
  evaluated_entity_id: string;
  status: string;
  severity: string;
  metric_value: string | null;
  threshold: string | null;
  details: string | null;
  evaluated_at: string;
}

export interface LineageNode {
  id: string;
  label: string;
  type: string;
  metadata?: Record<string, any>;
}

export interface LineageEdge {
  id: string;
  source: string;
  target: string;
  source_type: string;
  target_type: string;
  rule: string;
}

export interface LineageGraph {
  root_document_id: string;
  root_node_id?: string;
  root_type?: string;
  direction?: string;
  max_depth?: number;
  nodes_count: number;
  edges_count: number;
  nodes: LineageNode[];
  edges: LineageEdge[];
}

export interface RuleScorecardItem {
  rule_name: string;
  rule_category: string;
  severity: string;
  total_evaluations: number;
  passed: number;
  failed: number;
  warnings: number;
  pass_percentage: number;
}

export interface CategoryScorecardItem {
  rule_category: string;
  total_evaluations: number;
  passed: number;
  failed: number;
  warnings: number;
  pass_percentage: number;
}

export interface DetailedScorecard {
  total_evaluations: number;
  passed: number;
  failed: number;
  warnings: number;
  pass_rate_percentage: number;
  by_rule?: RuleScorecardItem[];
  by_category?: CategoryScorecardItem[];
}

export interface AnalyticalViewItem {
  view_name: string;
  description: string;
  domain: string;
  columns: string[];
  row_count: number;
}

export interface AnalyticalViewData {
  view_name: string;
  description: string;
  domain: string;
  total_rows: number;
  returned_rows: number;
  skip: number;
  limit: number;
  columns: string[];
  data: Record<string, any>[];
}

export interface PowerBiSemanticModel {
  dataset_name: string;
  architecture: string;
  recommended_connectivity_mode: string;
  tables: Array<{
    name: string;
    type: string;
    description: string;
    primary_key: string;
    columns: string[];
  }>;
  relationships: Array<{
    from_table: string;
    from_column: string;
    to_table: string;
    to_column: string;
    cardinality: string;
    cross_filter_direction: string;
    is_active: boolean;
    description: string;
  }>;
  dax_measures: Array<{
    name: string;
    display_folder: string;
    expression: string;
    format_string: string;
    description: string;
  }>;
  curated_views: string[];
  connection_parameters: {
    server: string;
    database: string;
    schema: string;
    authentication: string;
  };
}

export interface SystemReadiness {
  status: string;
  database: {
    status: string;
    dialect: string;
    latency_ms: number;
  };
  elasticsearch: {
    status: string;
    url: string;
    fallback_active: boolean;
  };
  embedding_provider: {
    status: string;
    model: string;
    dimension: number;
  };
  queue_broker: {
    type: string;
    status: string;
  };
  llm_provider: {
    provider: string;
    configured: boolean;
    model: string;
  };
}
