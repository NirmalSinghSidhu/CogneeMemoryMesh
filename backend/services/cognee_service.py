"""
Cognee Memory Lifecycle Service

This service implements the four core Cognee operations:
  - Remember(): Store and merge new meeting memories into the graph
  - Recall():   Retrieve relevant memories via semantic + graph search
  - Improve():  Update/evolve existing memories when new info arrives
  - Forget():   Remove memories cleanly from the graph
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

_MEETING_HEADER_RE = re.compile(
    r"Meeting ID:\s*(?P<id>\d+)\s*\|\s*Title:\s*(?P<title>.+?)\s*\|\s*Date:\s*(?P<date>\S+)",
    re.IGNORECASE,
)

# Project-local Cognee storage (avoids Windows AppData / long-path issues).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_COGNEE_DATA_ROOT = _PROJECT_ROOT / "data" / "cognee"
_COGNEE_SYSTEM_ROOT = _COGNEE_DATA_ROOT / "system"
_COGNEE_VECTOR_PATH = _COGNEE_DATA_ROOT / "cognee.lancedb"

for _path in (_COGNEE_DATA_ROOT, _COGNEE_SYSTEM_ROOT, _COGNEE_VECTOR_PATH):
    _path.mkdir(parents=True, exist_ok=True)

# Must be set before importing cognee.
os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")
os.environ.setdefault("CACHING", "false")
os.environ.setdefault("DATA_ROOT_DIRECTORY", str(_COGNEE_DATA_ROOT / "files"))
os.environ.setdefault("SYSTEM_ROOT_DIRECTORY", str(_COGNEE_SYSTEM_ROOT))
# LanceDB on Windows often fails with "Spill has sent an error" — bypass spilling.
os.environ.setdefault("LANCE_BYPASS_SPILLING", "true")
# Subprocess Lance workers are flaky on Windows file locks.
os.environ.setdefault("VECTOR_DB_SUBPROCESS_ENABLED", "false")

_COGNEE_AVAILABLE = False
_COGNEE_IMPORT_ERROR: Optional[str] = None
cognee = None  # type: ignore

try:
    import cognee as _cognee

    cognee = _cognee
    _COGNEE_AVAILABLE = True
except Exception as exc:  # pragma: no cover - depends on local env
    _COGNEE_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
    cognee = None  # type: ignore

from backend.utils.config import settings
from backend.utils.logger import logger
from backend.models.memory import (
    MemoryResult,
    RecallResult,
    RecallItem,
    OperationResult,
    ForgetScope,
    CogneeHealth,
    GraphData,
    GraphNode,
    GraphNodeSummary,
    GraphEdge,
)

# Colors for Cognee node types (and MemoryMesh entity types).
_NODE_COLORS: Dict[str, str] = {
    "person": "#06b6d4",
    "project": "#8b5cf6",
    "decision": "#f59e0b",
    "task": "#10b981",
    "topic": "#6366f1",
    "risk": "#ef4444",
    "blocker": "#f97316",
    "document": "#84cc16",
    "documentsummary": "#84cc16",
    "documentchunk": "#64748b",
    "textsummary": "#94a3b8",
    "entity": "#06b6d4",
    "entitytype": "#8b5cf6",
    "question": "#ec4899",
    "deadline": "#14b8a6",
    "meeting": "#3b82f6",
    "unknown": "#94a3b8",
}

# Prefer entity-like nodes when the graph is large.
_ENTITY_TYPE_HINTS = (
    "entity",
    "person",
    "project",
    "decision",
    "task",
    "topic",
    "risk",
    "blocker",
    "document",
    "question",
    "deadline",
    "organization",
    "location",
    "event",
    "concept",
)


class CogneeService:
    """
    Wraps Cognee's memory lifecycle API.
    Translates MemoryMesh domain concepts into Cognee operations.
    """

    def __init__(self):
        self._initialized = False
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def import_error(self) -> Optional[str]:
        return _COGNEE_IMPORT_ERROR

    async def health(self) -> CogneeHealth:
        """Report Cognee availability and optional dataset count."""
        if not self._active or cognee is None:
            return CogneeHealth(
                active=False,
                message=_COGNEE_IMPORT_ERROR or "Cognee not available",
                dataset_count=None,
                required=settings.cognee_required,
            )
        dataset_count: Optional[int] = None
        try:
            datasets = await cognee.datasets.list_datasets()
            dataset_count = len(datasets) if datasets is not None else 0
        except Exception as exc:
            logger.warning("Cognee health dataset list failed: {}", str(exc))
        return CogneeHealth(
            active=True,
            message="Cognee is active",
            dataset_count=dataset_count,
            required=settings.cognee_required,
        )

    def resolve_search_type(self, mode: str = "hybrid"):
        """Map Search UI modes to Cognee SearchType values."""
        if not self._active or cognee is None:
            return None
        search_types = getattr(cognee, "SearchType", None)
        if search_types is None:
            return None

        mode = (mode or "hybrid").lower()
        if mode == "semantic":
            for name in ("CHUNKS", "RAG_COMPLETION", "SUMMARIES"):
                value = getattr(search_types, name, None)
                if value is not None:
                    return value
        if mode == "graph":
            for name in ("GRAPH_COMPLETION", "GRAPH_COMPLETION_CONTEXT_EXTENSION"):
                value = getattr(search_types, name, None)
                if value is not None:
                    return value
        # hybrid and fallback
        return getattr(search_types, "GRAPH_COMPLETION", None)

    @staticmethod
    def format_remember_text(
        text: str,
        meeting_id: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Prefix transcript with meeting metadata for Recall source citation."""
        meta = metadata or {}
        title = meta.get("title") or "Untitled"
        date = meta.get("date") or "unknown"
        header = f"Meeting ID: {meeting_id} | Title: {title} | Date: {date}"
        body = text or ""
        if body.startswith("Meeting ID:"):
            return body
        return f"{header}\n\n{body}"

    async def initialize(self) -> None:
        """Configure Cognee with local LLM and vector store."""
        if self._initialized:
            return

        if not _COGNEE_AVAILABLE or cognee is None:
            logger.warning(
                "Cognee not available — running in SQL-only degraded mode ({})",
                _COGNEE_IMPORT_ERROR or "import failed",
            )
            self._initialized = True
            self._active = False
            return

        try:
            # Prefer cloud providers (Gemini). Ollama is optional and not required.
            llm_config: Dict[str, Any] = {
                "llm_provider": settings.llm_provider,
                "llm_model": settings.llm_model,
            }
            if settings.llm_api_key:
                llm_config["llm_api_key"] = settings.llm_api_key
            if settings.llm_base_url:
                llm_config["llm_endpoint"] = settings.llm_base_url
            cognee.config.set_llm_config(llm_config)

            # Also set env vars Cognee/LiteLLM read on some code paths.
            if settings.llm_api_key:
                os.environ["LLM_API_KEY"] = settings.llm_api_key
                os.environ["LLM_PROVIDER"] = settings.llm_provider
                os.environ["LLM_MODEL"] = settings.llm_model
                os.environ["EMBEDDING_API_KEY"] = settings.embedding_api_key or settings.llm_api_key
                os.environ["EMBEDDING_PROVIDER"] = settings.embedding_provider
                os.environ["EMBEDDING_MODEL"] = settings.embedding_model
                os.environ["EMBEDDING_DIMENSIONS"] = str(settings.embedding_dimensions)

            embedding_config: Dict[str, Any] = {
                "embedding_provider": settings.embedding_provider,
                "embedding_model": settings.embedding_model,
                "embedding_dimensions": settings.embedding_dimensions,
            }
            if settings.embedding_api_key:
                embedding_config["embedding_api_key"] = settings.embedding_api_key
            cognee.config.set_embedding_config(embedding_config)

            vector_url = str(Path(settings.vector_db_path).resolve())
            if settings.vector_db_path in ("./data/lancedb", "data/lancedb", ""):
                vector_url = str(_COGNEE_VECTOR_PATH.resolve())

            vector_config: Dict[str, Any] = {
                "vector_db_provider": settings.vector_db_provider or "lancedb",
                "vector_db_url": vector_url,
                "vector_db_subprocess_enabled": False,
            }
            cognee.config.set_vector_db_config(vector_config)
            os.environ["VECTOR_DB_URL"] = vector_url
            os.environ["VECTOR_DB_PROVIDER"] = vector_config["vector_db_provider"]

            self._initialized = True
            self._active = True
            logger.info(
                "Cognee initialized successfully with {}/{} (vectors at {})",
                settings.llm_provider,
                settings.llm_model,
                vector_url,
            )

        except Exception as e:
            logger.warning(
                "Cognee initialization failed: {} — running in degraded mode",
                str(e),
            )
            self._initialized = True
            self._active = False

    async def remember(
        self,
        text: str,
        dataset_name: str,
        meeting_id: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryResult:
        """Cognee Remember(): Add text to the knowledge graph (add + cognify)."""
        if not self._active or cognee is None:
            return MemoryResult(success=False, message="Cognee not available")

        try:
            enriched = self.format_remember_text(text, meeting_id, metadata)
            await cognee.remember(enriched, dataset_name=dataset_name)

            logger.info(
                "Remember(): Stored meeting {} in dataset '{}'",
                meeting_id,
                dataset_name,
            )
            return MemoryResult(
                success=True,
                entities_processed=self._estimate_entities(enriched),
                relationships_created=self._estimate_relationships(enriched),
                merged_entities=0,
                message=f"Meeting {meeting_id} stored and indexed in memory graph",
            )

        except Exception as e:
            logger.error("Remember() failed for meeting {}: {}", meeting_id, str(e))
            return MemoryResult(
                success=False,
                message=f"Memory storage failed: {str(e)}",
            )

    async def recall(
        self,
        query: str,
        search_type: Union[str, Any, None] = None,
        limit: int = 10,
        mode: Optional[str] = None,
    ) -> RecallResult:
        """Cognee Recall(): Retrieve relevant memories via the knowledge graph.

        `search_type` may be a Cognee SearchType enum, a mode string
        (hybrid/semantic/graph), or None. `mode` is an alias for string modes.
        """
        if not self._active or cognee is None:
            return RecallResult(query=query, results=[], sources=[], total=0)

        try:
            query_type = search_type
            if isinstance(search_type, str) or (search_type is None and mode):
                query_type = self.resolve_search_type(mode or str(search_type or "hybrid"))
            if query_type is None:
                query_type = getattr(
                    getattr(cognee, "SearchType", None), "GRAPH_COMPLETION", None
                )

            recall_kwargs: Dict[str, Any] = {
                "query_text": query,
                "top_k": limit,
                "auto_route": False,
            }
            if query_type is not None:
                recall_kwargs["query_type"] = query_type

            results = await cognee.recall(**recall_kwargs)
            recall_items = self._normalize_recall_results(results, limit)

            logger.info(
                "Recall(): Query '{}' returned {} results",
                query,
                len(recall_items),
            )
            return RecallResult(
                query=query,
                results=recall_items,
                sources=[],
                total=len(recall_items),
            )

        except Exception as e:
            logger.error("Recall() failed: {}", str(e))
            return RecallResult(query=query, results=[], sources=[], total=0)

    async def improve(
        self,
        new_text: str,
        dataset_name: str,
        old_entity_name: str,
        relationship_type: str,
        meeting_id: int,
    ) -> MemoryResult:
        """Cognee Improve(): Update existing memories with new information."""
        if not self._active or cognee is None:
            return MemoryResult(success=False, message="Cognee not available")

        try:
            enriched_text = (
                f"[IMPROVEMENT: {relationship_type}]\n"
                f"This information {relationship_type} the previous understanding of: "
                f"{old_entity_name}\n\n"
                f"{new_text}"
            )

            await cognee.remember(enriched_text, dataset_name=dataset_name)

            logger.info(
                "Improve(): Updated entity '{}' with relationship '{}' from meeting {}",
                old_entity_name,
                relationship_type,
                meeting_id,
            )
            return MemoryResult(
                success=True,
                entities_processed=self._estimate_entities(new_text),
                relationships_created=1,
                merged_entities=1,
                message=(
                    f"Memory improved: '{old_entity_name}' {relationship_type} "
                    f"by new information"
                ),
            )

        except Exception as e:
            logger.error("Improve() failed: {}", str(e))
            return MemoryResult(
                success=False,
                message=f"Memory improvement failed: {str(e)}",
            )

    async def forget(
        self,
        scope: ForgetScope,
        dataset_name: Optional[str] = None,
        entity_id: Optional[int] = None,
    ) -> OperationResult:
        """Cognee Forget(): Remove memories from the knowledge graph."""
        if not self._active or cognee is None:
            return OperationResult(
                success=False,
                message="Cognee not available",
                affected_count=0,
            )

        try:
            if scope == ForgetScope.WORKSPACE:
                await cognee.forget(everything=True)
                logger.info("Forget(): Pruned entire workspace")
                return OperationResult(
                    success=True,
                    message="Entire workspace memory has been cleared",
                    affected_count=-1,
                )

            if scope == ForgetScope.MEETING and dataset_name:
                await cognee.forget(dataset=dataset_name)
                logger.info("Forget(): Pruned dataset '{}'", dataset_name)
                return OperationResult(
                    success=True,
                    message=f"Meeting memory removed from dataset '{dataset_name}'",
                    affected_count=1,
                )

            if scope == ForgetScope.PROJECT and dataset_name:
                datasets = await cognee.datasets.list_datasets()
                matched = [
                    d
                    for d in datasets
                    if dataset_name.lower() in getattr(d, "name", "").lower()
                ]
                for dataset in matched:
                    await cognee.forget(dataset=dataset.name)
                logger.info("Forget(): Pruned {} project datasets", len(matched))
                return OperationResult(
                    success=True,
                    message=f"Project memory removed ({len(matched)} datasets)",
                    affected_count=len(matched),
                )

            return OperationResult(
                success=False,
                message="Invalid forget scope or missing target",
                affected_count=0,
            )

        except Exception as e:
            logger.error("Forget() failed: {}", str(e))
            return OperationResult(
                success=False,
                message=f"Memory removal failed: {str(e)}",
                affected_count=0,
            )

    async def get_graph(
        self,
        entity_type: Optional[str] = None,
        max_nodes: int = 250,
        max_edges: int = 500,
    ) -> Optional[GraphData]:
        """Load nodes/edges from Cognee's graph engine for visualization."""
        if not self._active or cognee is None:
            return None

        try:
            from cognee.infrastructure.databases.graph import get_graph_engine

            graph_engine = await get_graph_engine()
            raw_nodes, raw_edges = await graph_engine.get_graph_data()
            if not raw_nodes:
                return GraphData(nodes=[], edges=[], node_count=0, edge_count=0, source="cognee")

            nodes = self._map_cognee_nodes(raw_nodes, entity_type=entity_type, max_nodes=max_nodes)
            node_ids = {n.id for n in nodes}
            edges = self._map_cognee_edges(raw_edges, node_ids, max_edges=max_edges)

            # Degree-based weight for node sizing.
            degree: Dict[str, int] = {n.id: 0 for n in nodes}
            for edge in edges:
                if edge.source in degree:
                    degree[edge.source] += 1
                if edge.target in degree:
                    degree[edge.target] += 1
            for node in nodes:
                node.weight = float(max(1, degree.get(node.id, 1)))

            logger.info(
                "Graph(): Cognee returned {} nodes / {} edges (mapped {} / {})",
                len(raw_nodes),
                len(raw_edges or []),
                len(nodes),
                len(edges),
            )
            return GraphData(
                nodes=nodes,
                edges=edges,
                node_count=len(nodes),
                edge_count=len(edges),
                source="cognee",
            )
        except Exception as e:
            logger.error("Graph(): failed to load Cognee graph: {}", str(e))
            return None

    async def get_graph_node(self, node_id: str) -> Optional[GraphNode]:
        """Load a single Cognee node and its incident edges."""
        if not self._active or cognee is None:
            return None

        try:
            from cognee.infrastructure.databases.graph import get_graph_engine

            graph_engine = await get_graph_engine()
            raw_nodes, raw_edges = await graph_engine.get_graph_data()
            props_by_id: Dict[str, Dict[str, Any]] = {}
            for item in raw_nodes or []:
                nid, props = self._unpack_node(item)
                if nid is None:
                    continue
                props_by_id[nid] = props if isinstance(props, dict) else {}

            if node_id not in props_by_id:
                return None

            props = props_by_id[node_id]
            label, ntype, description = self._node_label_type_desc(props)
            connections: List[GraphEdge] = []
            for item in raw_edges or []:
                source, target, rel, eprops = self._unpack_edge(item)
                if source is None or target is None:
                    continue
                if source != node_id and target != node_id:
                    continue
                weight = 1.0
                if isinstance(eprops, dict):
                    try:
                        weight = float(eprops.get("weight", 1.0) or 1.0)
                    except (TypeError, ValueError):
                        weight = 1.0
                connections.append(
                    GraphEdge(
                        source=str(source),
                        target=str(target),
                        relationship=str(rel or "related_to"),
                        weight=weight,
                    )
                )
                if len(connections) >= 50:
                    break

            # Resolve connection labels for the side panel.
            labeled_connections = []
            for c in connections:
                other = c.target if c.source == node_id else c.source
                other_props = props_by_id.get(other, {})
                other_label, _, _ = self._node_label_type_desc(other_props)
                labeled_connections.append(
                    GraphEdge(
                        source=c.source,
                        target=c.target,
                        relationship=f"{c.relationship} → {other_label}" if other_label else c.relationship,
                        weight=c.weight,
                    )
                )

            return GraphNode(
                id=node_id,
                label=label,
                type=ntype,
                entity_id=None,
                description=description,
                connections=labeled_connections or connections,
                meetings=[],
                attributes={k: v for k, v in props.items() if isinstance(v, (str, int, float, bool))},
            )
        except Exception as e:
            logger.error("Graph node {} failed: {}", node_id, str(e))
            return None

    def _map_cognee_nodes(
        self,
        raw_nodes: Any,
        entity_type: Optional[str] = None,
        max_nodes: int = 250,
    ) -> List[GraphNodeSummary]:
        mapped: List[GraphNodeSummary] = []
        for item in raw_nodes or []:
            nid, props = self._unpack_node(item)
            if nid is None:
                continue
            props = props if isinstance(props, dict) else {}
            label, ntype, description = self._node_label_type_desc(props)
            if entity_type and ntype.lower() != entity_type.lower():
                continue
            # Skip empty/system-ish labels.
            if not label or label.lower() in ("node", "none", "null"):
                continue
            mapped.append(
                GraphNodeSummary(
                    id=str(nid),
                    label=label[:120],
                    type=ntype,
                    weight=1.0,
                    entity_id=None,
                    color=_NODE_COLORS.get(ntype.lower(), _NODE_COLORS["unknown"]),
                    description=description,
                )
            )

        # Prefer entity-like nodes when over limit.
        if len(mapped) > max_nodes:
            preferred = [n for n in mapped if n.type.lower() in _ENTITY_TYPE_HINTS]
            other = [n for n in mapped if n.type.lower() not in _ENTITY_TYPE_HINTS]
            mapped = (preferred + other)[:max_nodes]
        return mapped

    def _map_cognee_edges(
        self,
        raw_edges: Any,
        node_ids: set,
        max_edges: int = 500,
    ) -> List[GraphEdge]:
        edges: List[GraphEdge] = []
        for item in raw_edges or []:
            source, target, rel, eprops = self._unpack_edge(item)
            if source is None or target is None:
                continue
            source_s, target_s = str(source), str(target)
            if source_s not in node_ids or target_s not in node_ids:
                continue
            weight = 1.0
            if isinstance(eprops, dict):
                try:
                    weight = float(eprops.get("weight", 1.0) or 1.0)
                except (TypeError, ValueError):
                    weight = 1.0
            edges.append(
                GraphEdge(
                    source=source_s,
                    target=target_s,
                    relationship=str(rel or "related_to"),
                    weight=weight,
                )
            )
            if len(edges) >= max_edges:
                break
        return edges

    @staticmethod
    def _unpack_node(item: Any) -> tuple:
        if item is None:
            return None, {}
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            return item[0], item[1] if isinstance(item[1], dict) else {}
        if isinstance(item, dict):
            nid = item.get("id") or item.get("node_id")
            props = item.get("properties") or item.get("props") or item
            return nid, props if isinstance(props, dict) else {}
        return None, {}

    @staticmethod
    def _unpack_edge(item: Any) -> tuple:
        if item is None:
            return None, None, None, {}
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            eprops = item[3] if len(item) > 3 and isinstance(item[3], dict) else {}
            return item[0], item[1], item[2], eprops
        if isinstance(item, dict):
            return (
                item.get("source") or item.get("source_id"),
                item.get("target") or item.get("target_id"),
                item.get("relationship") or item.get("type") or item.get("label"),
                item.get("properties") or {},
            )
        return None, None, None, {}

    @staticmethod
    def _node_label_type_desc(props: Dict[str, Any]) -> tuple:
        label = (
            props.get("name")
            or props.get("label")
            or props.get("title")
            or props.get("text")
            or props.get("id")
            or "Node"
        )
        if not isinstance(label, str):
            label = str(label)
        # Truncate long chunk text used as labels.
        if len(label) > 80:
            label = label[:77] + "..."

        ntype = props.get("type") or props.get("entity_type") or props.get("label") or "entity"
        if isinstance(ntype, (list, tuple)) and ntype:
            ntype = ntype[0]
        ntype = str(ntype).split(".")[-1].strip() or "entity"

        description = props.get("description") or props.get("text") or props.get("summary")
        if description is not None and not isinstance(description, str):
            description = str(description)
        if isinstance(description, str) and len(description) > 400:
            description = description[:397] + "..."

        return label, ntype, description

    def _normalize_recall_results(self, results: Any, limit: int) -> List[RecallItem]:
        """Map Cognee recall/search payloads into MemoryMesh RecallItem list."""
        if results is None:
            return []

        if not isinstance(results, list):
            results = [results]

        items: List[RecallItem] = []
        for item in results[:limit]:
            content = self._extract_content(item)
            if not content:
                continue

            meeting_id = self._extract_field(item, "meeting_id")
            meeting_title = self._extract_field(item, "meeting_title")
            date = self._extract_field(item, "date")
            entity_name = str(self._extract_field(item, "name", "") or "")
            entity_type = str(self._extract_field(item, "type", "unknown") or "unknown")

            # Parse Meeting ID / Title / Date headers embedded by Remember().
            header = _MEETING_HEADER_RE.search(content)
            if header:
                if meeting_id is None:
                    try:
                        meeting_id = int(header.group("id"))
                    except (TypeError, ValueError):
                        pass
                if not meeting_title:
                    meeting_title = header.group("title").strip()
                if date is None:
                    date_str = header.group("date").strip()
                    try:
                        from datetime import datetime as _dt

                        date = _dt.fromisoformat(date_str.replace("Z", "+00:00"))
                    except ValueError:
                        date = None
                if not entity_name:
                    entity_name = meeting_title or "Memory"

            items.append(
                RecallItem(
                    content=content,
                    relevance_score=float(self._extract_field(item, "score", 0.8) or 0.8),
                    entity_type=entity_type,
                    entity_name=entity_name or (meeting_title or "Memory"),
                    meeting_id=meeting_id,
                    meeting_title=meeting_title,
                    date=date,
                )
            )
        return items

    @staticmethod
    def _extract_field(item: Any, key: str, default: Any = None) -> Any:
        if item is None:
            return default
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    @classmethod
    def _extract_content(cls, item: Any) -> str:
        if item is None:
            return ""
        if isinstance(item, str):
            return item

        for key in ("text", "content", "search_result", "answer"):
            value = cls._extract_field(item, key)
            if value is None:
                continue
            if isinstance(value, str) and value.strip():
                return value
            if isinstance(value, list):
                parts = [cls._extract_content(v) for v in value]
                joined = "\n".join(p for p in parts if p)
                if joined:
                    return joined
            if hasattr(value, "text"):
                text = getattr(value, "text", None)
                if text:
                    return str(text)
            if value is not None and not isinstance(value, (dict, list)):
                return str(value)

        return str(item)

    def _estimate_entities(self, text: str) -> int:
        """Rough entity count estimate based on text length."""
        words = len(text.split())
        return max(1, words // 50)

    def _estimate_relationships(self, text: str) -> int:
        """Rough relationship count estimate."""
        return max(1, self._estimate_entities(text) * 2)


cognee_service = CogneeService()
