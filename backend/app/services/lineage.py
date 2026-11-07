from typing import Dict, Any, List, Set, Optional
from collections import deque
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.data_platform import LineageEdge
from backend.app.models.document import Document, ExtractedField
from backend.app.models.analytics import FactInvoice, DimVendor

class LineageService:
    def get_document_lineage(
        self,
        document_id: str,
        db: Session,
        direction: str = "document",
        max_depth: int = 6
    ) -> Dict[str, Any]:
        """
        Traverse the multi-hop lineage graph for a given document.
        Supported directions:
          - 'document' (default): Precise isolated document pipeline: Source File -> Document -> Fields -> Fact -> Views -> Metrics.
          - 'upstream': Provenance trace backward to raw file.
          - 'downstream': Impact trace forward to fields, facts, views, and metrics.
          - 'all': Global graph traversal including shared aggregation hubs.
        """
        if direction == "document":
            # Upstream: file -> doc
            up = self.get_lineage_graph(root_id=document_id, root_type="document", db=db, direction="upstream", max_depth=2)
            # Downstream: doc -> fields -> fact -> views -> metrics
            down = self.get_lineage_graph(root_id=document_id, root_type="document", db=db, direction="downstream", max_depth=max_depth)

            # Combine without bridging across shared views to other documents
            combined_nodes = {n["id"]: n for n in up["nodes"]}
            for n in down["nodes"]:
                combined_nodes[n["id"]] = n

            combined_edges = {f"{e['source']}->{e['rule']}->{e['target']}": e for e in up["edges"]}
            for e in down["edges"]:
                combined_edges[f"{e['source']}->{e['rule']}->{e['target']}"] = e

            type_order = {"file": 0, "document": 1, "extracted_field": 2, "fact_invoice": 3, "view": 4, "metric": 5}
            nodes_list = list(combined_nodes.values())
            nodes_list.sort(key=lambda n: (type_order.get(n["type"], 99), n["id"]))
            edges_list = list(combined_edges.values())

            return {
                "root_document_id": document_id,
                "root_node_id": document_id,
                "root_type": "document",
                "direction": "document",
                "max_depth": max_depth,
                "nodes_count": len(nodes_list),
                "edges_count": len(edges_list),
                "nodes": nodes_list,
                "edges": edges_list
            }

        return self.get_lineage_graph(
            root_id=document_id,
            root_type="document",
            db=db,
            direction=direction,
            max_depth=max_depth
        )

    def get_lineage_graph(
        self,
        root_id: str,
        root_type: str = "document",
        db: Session = None,
        direction: str = "all",
        max_depth: int = 6
    ) -> Dict[str, Any]:
        """
        Execute Breadth-First Search (BFS) over LineageEdge records starting from root_id.
        """
        if db is None:
            return {
                "root_document_id": root_id,
                "root_node_id": root_id,
                "root_type": root_type,
                "direction": direction,
                "max_depth": max_depth,
                "nodes_count": 0,
                "edges_count": 0,
                "nodes": [],
                "edges": []
            }

        visited_nodes: Set[str] = {root_id}
        node_types: Dict[str, str] = {root_id: root_type}
        collected_edges: Dict[str, Dict[str, Any]] = {}

        queue = deque([(root_id, 0)])

        while queue:
            curr_id, depth = queue.popleft()
            if depth >= max_depth:
                continue

            query_edges: List[LineageEdge] = []

            if direction in ("downstream", "all"):
                # Forward edges where source is curr_id
                forward = db.query(LineageEdge).filter(LineageEdge.source_id == curr_id).all()
                for e in forward:
                    query_edges.append(e)

            if direction in ("upstream", "all"):
                # Backward edges where target is curr_id
                backward = db.query(LineageEdge).filter(LineageEdge.target_id == curr_id).all()
                for e in backward:
                    query_edges.append(e)

            for e in query_edges:
                edge_key = f"{e.source_id}->{e.transformation_rule}->{e.target_id}"
                if edge_key not in collected_edges:
                    collected_edges[edge_key] = {
                        "id": e.id,
                        "source": e.source_id,
                        "target": e.target_id,
                        "source_type": e.source_type,
                        "target_type": e.target_type,
                        "rule": e.transformation_rule
                    }

                node_types[e.source_id] = e.source_type
                node_types[e.target_id] = e.target_type

                neighbor = e.target_id if e.source_id == curr_id else e.source_id
                if neighbor not in visited_nodes:
                    visited_nodes.add(neighbor)
                    queue.append((neighbor, depth + 1))

        # Build enriched node objects
        nodes = []
        for n_id in visited_nodes:
            n_type = node_types.get(n_id, "unknown")
            node_meta = self._resolve_node_metadata(n_id, n_type, db)
            nodes.append({
                "id": n_id,
                "label": self._node_label(n_id, n_type, node_meta),
                "type": n_type,
                "metadata": node_meta
            })

        # Sort nodes deterministically
        type_order = {"file": 0, "document": 1, "extracted_field": 2, "fact_invoice": 3, "view": 4, "metric": 5}
        nodes.sort(key=lambda n: (type_order.get(n["type"], 99), n["id"]))

        edges_list = list(collected_edges.values())

        return {
            "root_document_id": root_id,
            "root_node_id": root_id,
            "root_type": root_type,
            "direction": direction,
            "max_depth": max_depth,
            "nodes_count": len(nodes),
            "edges_count": len(edges_list),
            "nodes": nodes,
            "edges": edges_list
        }

    def get_lineage_summary(self, db: Session) -> Dict[str, Any]:
        """Aggregate summary of all lineage relationships recorded in the platform."""
        total_edges = db.query(func.count(LineageEdge.id)).scalar() or 0

        # Edges by transformation rule
        rule_rows = db.query(
            LineageEdge.transformation_rule,
            func.count(LineageEdge.id)
        ).group_by(LineageEdge.transformation_rule).all()
        edges_by_rule = {r[0]: r[1] for r in rule_rows}

        # Distinct nodes by type
        source_nodes = db.query(LineageEdge.source_type, LineageEdge.source_id).distinct().all()
        target_nodes = db.query(LineageEdge.target_type, LineageEdge.target_id).distinct().all()

        nodes_by_type: Dict[str, Set[str]] = {}
        for s_type, s_id in source_nodes:
            nodes_by_type.setdefault(s_type, set()).add(s_id)
        for t_type, t_id in target_nodes:
            nodes_by_type.setdefault(t_type, set()).add(t_id)

        node_counts = {t: len(ids) for t, ids in nodes_by_type.items()}
        total_distinct_nodes = sum(node_counts.values())

        return {
            "total_nodes": total_distinct_nodes,
            "total_edges": total_edges,
            "nodes_by_type": node_counts,
            "edges_by_rule": edges_by_rule
        }

    def _resolve_node_metadata(self, node_id: str, node_type: str, db: Session) -> Dict[str, Any]:
        """Fetch rich entity metadata for interactive lineage inspection."""
        try:
            if node_type == "file":
                doc = db.query(Document).filter(Document.storage_path == node_id).first()
                filename = doc.filename if doc else node_id.replace("\\", "/").split("/")[-1]
                return {
                    "filename": filename,
                    "storage_path": node_id,
                    "file_size": doc.file_size if doc else None,
                    "page_count": doc.page_count if doc else None
                }
            elif node_type == "document":
                doc = db.query(Document).filter(Document.id == node_id).first()
                if doc:
                    return {
                        "filename": doc.filename,
                        "status": doc.status,
                        "version": doc.version,
                        "document_type": doc.document_type,
                        "extraction_confidence": doc.extraction_confidence,
                        "created_at": doc.created_at.isoformat() if doc.created_at else None
                    }
            elif node_type == "extracted_field":
                field = db.query(ExtractedField).filter(ExtractedField.id == node_id).first()
                if field:
                    return {
                        "field_name": field.field_name,
                        "field_value": field.field_value,
                        "normalized_value": field.normalized_value,
                        "confidence": field.confidence,
                        "page_number": field.page_number,
                        "extraction_method": field.extraction_method
                    }
            elif node_type == "fact_invoice":
                try:
                    inv_key = int(node_id)
                    fact = db.query(FactInvoice).filter(FactInvoice.invoice_key == inv_key).first()
                    if fact:
                        return {
                            "invoice_number": fact.invoice_number,
                            "currency": fact.currency,
                            "total_amount": fact.total_amount,
                            "subtotal": fact.subtotal,
                            "tax_amount": fact.tax_amount,
                            "payment_status": fact.payment_status,
                            "is_overdue": fact.is_overdue
                        }
                except ValueError:
                    pass
            elif node_type == "view":
                view_descriptions = {
                    "v_invoice_spend_by_vendor": "Curated spend aggregated by vendor and currency",
                    "v_overdue_invoices": "Active overdue invoice liabilities and exposure days",
                    "v_daily_ingestion": "Daily ingestion velocity, document count, and byte volume",
                    "v_processing_performance": "Pipeline processing latency and success ratios",
                    "v_data_quality_scorecard": "Rule evaluation pass rates and warning distributions",
                    "v_pipeline_freshness": "ETL batch freshness and record throughput metrics",
                    "v_indexing_coverage": "Search index coverage vs completed documents"
                }
                return {
                    "view_name": node_id,
                    "description": view_descriptions.get(node_id, "Analytical SQL View")
                }
            elif node_type == "metric":
                metric_definitions = {
                    "total_spend_kpi": "SUM(fact_invoice.total_amount) WHERE currency = 'USD'",
                    "overdue_exposure_kpi": "SUM(fact_invoice.total_amount) WHERE is_overdue = TRUE",
                    "quality_pass_rate_kpi": "AVG(data_quality_scorecard.pass_percentage)",
                    "processing_throughput_kpi": "COUNT(documents.id) / total_processing_time"
                }
                return {
                    "metric_name": node_id,
                    "formula": metric_definitions.get(node_id, "Aggregated BI Metric")
                }
        except Exception:
            pass
        return {}

    def _node_label(self, node_id: str, node_type: str, metadata: Dict[str, Any]) -> str:
        if node_type == "file":
            fn = metadata.get("filename") or node_id.replace("\\", "/").split("/")[-1]
            return f"Raw File ({fn[:20]})"
        elif node_type == "document":
            fn = metadata.get("filename") or node_id[:8]
            return f"Document ({fn[:18]})"
        elif node_type == "extracted_field":
            fname = metadata.get("field_name")
            fval = metadata.get("normalized_value") or metadata.get("field_value")
            if fname and fval:
                return f"{fname}: {str(fval)[:12]}"
            return f"Extracted Field ({fname or node_id[:8]})"
        elif node_type == "fact_invoice":
            inv_num = metadata.get("invoice_number") or f"Key #{node_id}"
            amt = metadata.get("total_amount")
            curr = metadata.get("currency", "")
            if amt is not None:
                return f"Fact Invoice ({inv_num}: {curr} {amt})"
            return f"Fact Invoice ({inv_num})"
        elif node_type == "view":
            return f"SQL View ({node_id})"
        elif node_type == "metric":
            return f"BI Metric ({node_id})"
        return f"{node_type.capitalize()} ({node_id[:10]})"

lineage_service = LineageService()
