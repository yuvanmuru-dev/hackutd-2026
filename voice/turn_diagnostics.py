"""Metadata-only breadcrumbs across recognition, turn filtering and playback.

Never retain recognized words, model replies, audio or provider frame objects.
These observations do not change turn detection or arm an approval question.
"""
from dataclasses import dataclass
from typing import Callable


@dataclass
class TurnDiagnostics:
    conversation: object
    emit: Callable
    asr_seq: int = 0
    turn_seq: int = 0
    plan_seq: int = 0
    bot_speaking: bool = False
    last_asr_final: bool = False
    last_asr_words: int = 0

    def event(self, name: str, stage: str, **fields):
        c = self.conversation
        self.emit(name, case_id=c.request["case_id"], stage=stage,
            asr_seq=self.asr_seq, turn_seq=self.turn_seq, plan_seq=self.plan_seq,
            bot_speaking=self.bot_speaking, action_id=c.awaiting,
            question_heard=c.heard_question, completed_count=len(c.completed), **fields)

    def recognized(self, text: str, *, final: bool, finalized: bool = False):
        self.asr_seq += 1
        self.last_asr_final = final
        self.last_asr_words = min(len(text.split()), 512)
        self.event("voice.asr_result", "asr", final=final, finalized=finalized,
            word_count=self.last_asr_words, char_count=min(len(text), 4096))

    def aggregation_reset(self):
        self.event("voice.turn_aggregation_reset", "turn",
            last_asr_final=self.last_asr_final, last_asr_word_count=self.last_asr_words)

    def turn_started(self):
        self.event("voice.user_turn_started", "turn")

    def turn_accepted(self):
        self.turn_seq += 1
        c = self.conversation
        reason = "no_pending_action" if not c.awaiting else (
            "question_heard" if c.heard_question else "question_not_heard")
        self.event("voice.turn_accepted", "conversation", gate_reason=reason)

    def turn_completed(self):
        self.event("voice.turn_completed", "conversation")

    def plan_queued(self, plan):
        self.plan_seq += 1
        self.event("voice.plan_queued", "tts", line_count=len(plan.lines), end=plan.end)

    def playback(self, speaking: bool):
        self.bot_speaking = speaking
        self.event("voice.playback_started" if speaking else "voice.playback_stopped", "transport")

    def question_audited(self, *, interrupted: bool):
        self.event("voice.question_audited", "transport", interrupted=interrupted)

    def interrupted(self):
        self.event("voice.playback_interrupted", "transport")
