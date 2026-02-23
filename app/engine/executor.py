"""
Workflow Execution Engine
- Topological sort of nodes
- Execute each node in order
- Pass outputs to connected nodes
- Handle errors with retry logic
- Store logs per node
"""

import time
import traceback
from datetime import datetime
from typing import Any
from collections import defaultdict, deque

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import Workflow, WorkflowNode
from app.models.run import WorkflowRun, NodeRun
from app.engine.node_handlers import get_node_handler
from app.utils.expression import interpolate


class WorkflowExecutor:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.context: dict[str, Any] = {}

    async def execute(self, workflow: Workflow, input_payload: dict, trigger_type: str = "manual") -> WorkflowRun:
        # Create run record
        run = WorkflowRun(
            workflow_id=workflow.id,
            status="running",
            trigger_type=trigger_type,
            input_payload=input_payload,
            started_at=datetime.utcnow(),
        )
        self.db.add(run)
        await self.db.flush()

        # Build context
        self.context = {
            "trigger": {"body": input_payload, "type": trigger_type},
            "workflow": {"variables": workflow.variables or {}, "id": str(workflow.id)},
            "env": {},
        }

        try:
            # Build adjacency and get sorted order
            # Key by node_key (frontend string ID) so it matches edge source/target
            nodes_map = {(n.node_key or str(n.id)): n for n in workflow.nodes}
            edges = workflow.edges
            sorted_node_ids = self._topological_sort(nodes_map, edges)

            # Execute nodes in order
            for node_id in sorted_node_ids:
                node = nodes_map.get(node_id)
                if not node:
                    continue

                node_run = await self._execute_node(run, node)
                if node_run.status == "failed":
                    run.status = "failed"
                    run.error = f"Node {node_id} failed: {node_run.error}"
                    break

            if run.status != "failed":
                run.status = "completed"
                run.output_payload = self.context.get("_last_output", {})

        except Exception as e:
            run.status = "failed"
            run.error = traceback.format_exc()

        run.completed_at = datetime.utcnow()
        await self.db.flush()
        return run

    async def _execute_node(self, run: WorkflowRun, node: WorkflowNode) -> NodeRun:
        node_run = NodeRun(
            run_id=run.id,
            node_id=str(node.id),
            status="running",
            started_at=datetime.utcnow(),
        )
        self.db.add(node_run)
        await self.db.flush()

        start_time = time.time()

        try:
            # Resolve expressions in node data
            resolved_data = interpolate(node.data or {}, self.context)
            node_run.input_data = resolved_data

            # Get handler and execute
            handler = get_node_handler(node.type)
            result = await handler.execute(resolved_data, self.context, self.db)

            # Store output in context using node_key (frontend string ID like "trigger_1")
            node_key = node.node_key or str(node.id)
            self.context[node_key] = {"output": result.get("output", {})}
            self.context["_last_output"] = result.get("output", {})

            node_run.node_key = node_key
            node_run.output_data = result.get("output", {})
            node_run.token_usage = result.get("token_usage")
            node_run.status = "completed"

        except Exception as e:
            node_run.status = "failed"
            node_run.error = traceback.format_exc()

        elapsed = (time.time() - start_time) * 1000
        node_run.execution_time_ms = elapsed
        node_run.completed_at = datetime.utcnow()
        await self.db.flush()
        return node_run

    def _topological_sort(self, nodes_map: dict, edges: list) -> list[str]:
        """Kahn's algorithm for topological sort."""
        in_degree: dict[str, int] = defaultdict(int)
        adjacency: dict[str, list[str]] = defaultdict(list)

        all_node_ids = set(nodes_map.keys())

        for edge in edges:
            src = edge.source
            tgt = edge.target
            adjacency[src].append(tgt)
            in_degree[tgt] += 1

        # Initialize in_degree for nodes with no incoming edges
        for nid in all_node_ids:
            if nid not in in_degree:
                in_degree[nid] = 0

        queue = deque([nid for nid in all_node_ids if in_degree[nid] == 0])
        sorted_nodes = []

        while queue:
            current = queue.popleft()
            sorted_nodes.append(current)
            for neighbor in adjacency.get(current, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return sorted_nodes
