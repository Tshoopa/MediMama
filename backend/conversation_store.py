"""Bounded, in-memory conversation storage for single-process demos.

Sessions are intentionally ephemeral. They are lost on process restart and are
not shared by multiple workers or replicas. Use a persistent/distributed store
before deploying a multi-worker production service.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class ConversationState:
    conversation_id: str
    child_age_months: int
    language: str
    original_concern: str
    additional_context: str = ""
    turns: list[dict[str, str | bool]] = field(default_factory=list)
    asked_question_ids: list[str] = field(default_factory=list)
    uncertain_answers: list[str] = field(default_factory=list)
    current_question_id: str | None = None
    status: str = "active"
    triage_level: int | None = None
    created_at: float = field(default_factory=time.monotonic)
    updated_at: float = field(default_factory=time.monotonic)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    def clinical_text(self) -> str:
        """Rebuild a single case narrative without inserting assistant prompts."""
        parts = [self.original_concern.strip()]
        if self.additional_context.strip():
            parts.append(self.additional_context.strip())
        for turn in self.turns:
            answer = str(turn.get("answer", "")).strip()
            if answer:
                parts.append(answer)
        return "\n".join(part for part in parts if part)

    def clinical_segments(self) -> list[str]:
        segments = [self.original_concern]
        if self.additional_context.strip():
            segments.append(self.additional_context)
        segments.extend(
            str(turn.get("answer", ""))
            for turn in self.turns
            if str(turn.get("answer", "")).strip()
        )
        return segments


class ConversationStore:
    """Thread-safe bounded store with TTL and per-session turn locks."""

    def __init__(self, ttl_seconds: int = 1800, max_sessions: int = 500):
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be at least 1")
        if max_sessions < 1:
            raise ValueError("max_sessions must be at least 1")
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self._sessions: OrderedDict[str, ConversationState] = OrderedDict()
        self._lock = threading.RLock()

    def _remove_expired_locked(self, now: float) -> None:
        for conversation_id, state in list(self._sessions.items()):
            if now - state.updated_at <= self.ttl_seconds:
                continue
            if state.lock.acquire(blocking=False):
                try:
                    if self._sessions.get(conversation_id) is state:
                        self._sessions.pop(conversation_id, None)
                finally:
                    state.lock.release()

    def create(
        self,
        child_age_months: int,
        language: str,
        original_concern: str,
        additional_context: str = "",
    ) -> ConversationState:
        now = time.monotonic()
        with self._lock:
            self._remove_expired_locked(now)

            while len(self._sessions) >= self.max_sessions:
                removed = False
                for conversation_id, candidate in list(self._sessions.items()):
                    if candidate.lock.acquire(blocking=False):
                        try:
                            if self._sessions.get(conversation_id) is candidate:
                                self._sessions.pop(conversation_id, None)
                                removed = True
                                break
                        finally:
                            candidate.lock.release()
                if not removed:
                    raise RuntimeError("Conversation capacity reached; retry shortly.")

            state = ConversationState(
                conversation_id=str(uuid.uuid4()),
                child_age_months=child_age_months,
                language=language,
                original_concern=original_concern,
                additional_context=additional_context or "",
                created_at=now,
                updated_at=now,
            )
            self._sessions[state.conversation_id] = state
            return state

    @contextmanager
    def access(self, conversation_id: str) -> Iterator[ConversationState | None]:
        """Lock one conversation for a complete turn; other sessions can proceed."""
        with self._lock:
            original_state = self._sessions.get(conversation_id)
        if original_state is None:
            yield None
            return

        original_state.lock.acquire()
        active_state: ConversationState | None = original_state
        try:
            with self._lock:
                current = self._sessions.get(conversation_id)
                if current is not original_state:
                    active_state = None
                elif time.monotonic() - current.updated_at > self.ttl_seconds:
                    self._sessions.pop(conversation_id, None)
                    active_state = None
                else:
                    self._sessions.move_to_end(conversation_id)
            yield active_state
            if active_state is not None:
                with self._lock:
                    if self._sessions.get(conversation_id) is active_state:
                        active_state.updated_at = time.monotonic()
        finally:
            original_state.lock.release()

    def delete(self, conversation_id: str) -> bool:
        with self._lock:
            state = self._sessions.get(conversation_id)
        if state is None:
            return False
        state.lock.acquire()
        try:
            with self._lock:
                if self._sessions.get(conversation_id) is state:
                    self._sessions.pop(conversation_id, None)
                    return True
                return False
        finally:
            state.lock.release()

    def __len__(self) -> int:
        with self._lock:
            self._remove_expired_locked(time.monotonic())
            return len(self._sessions)
