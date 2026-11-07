from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict

class PipelineRunResponse(BaseModel):
    id: str
    pipeline_name: str
    batch_id: str
    status: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    rows_read: int
    rows_inserted: int
    rows_updated: int
    rows_rejected: int
    source_range: Optional[str] = None
    error_details: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DataQualityResultResponse(BaseModel):
    id: str
    rule_name: str
    rule_category: str
    evaluated_entity_type: str
    evaluated_entity_id: str
    status: str
    severity: str
    metric_value: Optional[str] = None
    threshold: Optional[str] = None
    details: Optional[str] = None
    evaluated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class RuleScorecardItem(BaseModel):
    rule_name: str
    rule_category: str
    severity: str
    total_evaluations: int
    passed: int
    failed: int
    warnings: int
    pass_percentage: float

class CategoryScorecardItem(BaseModel):
    rule_category: str
    total_evaluations: int
    passed: int
    failed: int
    warnings: int
    pass_percentage: float

class DetailedScorecardResponse(BaseModel):
    total_evaluations: int
    passed: int
    failed: int
    warnings: int
    pass_rate_percentage: float
    by_rule: List[RuleScorecardItem] = []
    by_category: List[CategoryScorecardItem] = []

class QualityEvaluationTriggerResponse(BaseModel):
    status: str
    documents_evaluated: int
    total_rules_evaluated: int
    scorecard: DetailedScorecardResponse

class RejectedRecordResponse(BaseModel):
    id: str
    batch_id: str
    source_file: str
    row_index: int
    raw_data: str
    rejection_reason: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class LineageNode(BaseModel):
    id: str
    label: str
    type: str
    metadata: Optional[Dict[str, Any]] = None

class LineageEdgeItem(BaseModel):
    id: str
    source: str
    target: str
    source_type: str
    target_type: str
    rule: str

class LineageGraphResponse(BaseModel):
    root_document_id: str
    root_node_id: Optional[str] = None
    root_type: Optional[str] = None
    direction: str = "all"
    max_depth: int = 6
    nodes_count: int
    edges_count: int
    nodes: List[LineageNode]
    edges: List[LineageEdgeItem]

class LineageSummaryResponse(BaseModel):
    total_nodes: int
    total_edges: int
    nodes_by_type: Dict[str, int]
    edges_by_rule: Dict[str, int]
