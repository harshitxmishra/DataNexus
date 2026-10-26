from typing import Dict, Any, List, Set
from sqlalchemy.orm import Session
from backend.app.models.data_platform import LineageEdge

class LineageService:
    def get_document_lineage(self, document_id: str, db: Session) -> Dict[str, Any]:
        """
        Traverse the lineage graph bidirectionally for a given document.
        Returns nodes and edges formatted for visualization.
        """
        visited_ids: Set[str] = set()
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []

        # Find all edges where document_id is source or target, or related to its fields/facts
        raw_edges = db.query(LineageEdge).filter(
            (LineageEdge.source_id == document_id) | 
            (LineageEdge.target_id == document_id)
        ).all()

        # Broaden traversal by one hop
        expanded_ids = {e.source_id for e in raw_edges}.union({e.target_id for e in raw_edges})
        expanded_ids.add(document_id)

        all_related_edges = db.query(LineageEdge).filter(
            (LineageEdge.source_id.in_(expanded_ids)) |
            (LineageEdge.target_id.in_(expanded_ids))
        ).all()

        for e in all_related_edges:
            edges.append({
                "id": e.id,
                "source": e.source_id,
                "target": e.target_id,
                "source_type": e.source_type,
                "target_type": e.target_type,
                "rule": e.transformation_rule
            })
            
            # Register nodes
            if e.source_id not in visited_ids:
                visited_ids.add(e.source_id)
                nodes.append({
                    "id": e.source_id,
                    "label": self._node_label(e.source_id, e.source_type),
                    "type": e.source_type
                })
            if e.target_id not in visited_ids:
                visited_ids.add(e.target_id)
                nodes.append({
                    "id": e.target_id,
                    "label": self._node_label(e.target_id, e.target_type),
                    "type": e.target_type
                })

        return {
            "root_document_id": document_id,
            "nodes_count": len(nodes),
            "edges_count": len(edges),
            "nodes": nodes,
            "edges": edges
        }

    def _node_label(self, node_id: str, node_type: str) -> str:
        if node_type == "file":
            return f"Raw File ({node_id.split('/')[-1].split(chr(92))[-1][:20]})"
        elif node_type == "document":
            return f"Document ({node_id[:8]})"
        elif node_type == "extracted_field":
            return f"Extracted Field ({node_id[:8]})"
        elif node_type == "fact_invoice":
            return f"Fact Invoice (Key #{node_id})"
        elif node_type == "view":
            return f"SQL View ({node_id})"
        elif node_type == "metric":
            return f"BI Metric ({node_id})"
        return f"{node_type.capitalize()} ({node_id[:10]})"

lineage_service = LineageService()
