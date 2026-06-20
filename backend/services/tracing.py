import json
import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TraceStep:
    step_id: int
    action: str
    state: str
    decision: str = ""
    reasoning: str = ""
    result_summary: str = ""
    duration_ms: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class ToolCallTrace:
    tool_name: str
    args: dict = field(default_factory=dict)
    result_summary: str = ""
    duration_ms: int = 0
    success: bool = True
    timestamp: float = field(default_factory=time.time)


@dataclass
class TraceRecord:
    trace_id: str
    user_key: str
    steps: list[TraceStep] = field(default_factory=list)
    reasoning_chain: list[str] = field(default_factory=list)
    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    total_duration_ms: int = 0
    quality_score: float = 0.0
    created_at: float = field(default_factory=time.time)


class AgentTracer:
    def __init__(self):
        self._active_trace: TraceRecord | None = None
        self._step_counter: int = 0

    def start_trace(self, user_key: str = "anonymous") -> str:
        trace_id = str(uuid.uuid4())[:12]
        self._active_trace = TraceRecord(trace_id=trace_id, user_key=user_key)
        self._step_counter = 0
        logger.info(f"Trace started: {trace_id}")
        return trace_id

    def add_step(self, action: str, state: str, decision: str = "",
                 reasoning: str = "", result_summary: str = "", duration_ms: int = 0):
        if not self._active_trace:
            return
        self._step_counter += 1
        step = TraceStep(
            step_id=self._step_counter,
            action=action,
            state=state,
            decision=decision,
            reasoning=reasoning,
            result_summary=result_summary[:200],
            duration_ms=duration_ms,
        )
        self._active_trace.steps.append(step)

    def add_reasoning(self, message: str):
        if not self._active_trace:
            return
        self._active_trace.reasoning_chain.append(message)

    def add_tool_call(self, tool_name: str, args: dict, result_summary: str,
                      duration_ms: int, success: bool = True):
        if not self._active_trace:
            return
        call = ToolCallTrace(
            tool_name=tool_name,
            args=args,
            result_summary=result_summary[:200],
            duration_ms=duration_ms,
            success=success,
        )
        self._active_trace.tool_calls.append(call)

    def finish(self, context, total_duration_ms: int, quality_score: float = 0.0):
        if not self._active_trace:
            return
        self._active_trace.total_duration_ms = total_duration_ms
        self._active_trace.quality_score = quality_score

        if hasattr(context, 'reasoning') and context.reasoning:
            self._active_trace.reasoning_chain = context.reasoning

        self._persist()
        logger.info(
            f"Trace finished: {self._active_trace.trace_id}, "
            f"steps={len(self._active_trace.steps)}, "
            f"duration={total_duration_ms}ms, "
            f"quality={quality_score:.1f}"
        )

    def _persist(self):
        if not self._active_trace:
            return
        try:
            from database import save_agent_trace
            trace = self._active_trace
            asyncio_loop = None
            try:
                import asyncio
                asyncio_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

            if asyncio_loop and asyncio_loop.is_running():
                import asyncio
                asyncio.ensure_future(save_agent_trace(
                    trace_id=trace.trace_id,
                    user_key=trace.user_key,
                    steps_json=json.dumps([
                        {
                            "step_id": s.step_id,
                            "action": s.action,
                            "state": s.state,
                            "decision": s.decision,
                            "reasoning": s.reasoning,
                            "result_summary": s.result_summary,
                            "duration_ms": s.duration_ms,
                        }
                        for s in trace.steps
                    ], ensure_ascii=False),
                    reasoning_chain=json.dumps(trace.reasoning_chain, ensure_ascii=False),
                    tool_calls_json=json.dumps([
                        {
                            "tool": tc.tool_name,
                            "args": tc.args,
                            "result": tc.result_summary,
                            "duration_ms": tc.duration_ms,
                            "success": tc.success,
                        }
                        for tc in trace.tool_calls
                    ], ensure_ascii=False),
                    total_duration_ms=trace.total_duration_ms,
                    quality_score=trace.quality_score,
                ))
            else:
                import asyncio
                asyncio.run(save_agent_trace(
                    trace_id=trace.trace_id,
                    user_key=trace.user_key,
                    steps_json=json.dumps([], ensure_ascii=False),
                    reasoning_chain=json.dumps([], ensure_ascii=False),
                    tool_calls_json=json.dumps([], ensure_ascii=False),
                    total_duration_ms=trace.total_duration_ms,
                    quality_score=trace.quality_score,
                ))
        except Exception as e:
            logger.error(f"Failed to persist trace: {e}")

    def get_trace(self) -> TraceRecord | None:
        return self._active_trace

    def get_trace_summary(self) -> dict:
        if not self._active_trace:
            return {}
        trace = self._active_trace
        return {
            "trace_id": trace.trace_id,
            "steps_count": len(trace.steps),
            "tool_calls_count": len(trace.tool_calls),
            "reasoning_count": len(trace.reasoning_chain),
            "total_duration_ms": trace.total_duration_ms,
            "quality_score": trace.quality_score,
            "created_at": trace.created_at,
        }
