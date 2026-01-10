from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import app.grpc.agent_pb2 as agent_pb2


def _is_missing_str(value: Optional[str]) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


@dataclass
class PromptRequest:
    agent: Optional[str] = None
    prompt: Optional[str] = None
    tool: Optional[str] = None

    @classmethod
    def from_proto(cls, proto: agent_pb2.PromptRequest) -> "PromptRequest":
        pr = cls(
            agent=proto.agent if proto.agent != "" else None,
            prompt=proto.prompt if proto.prompt != "" else None,
            tool=proto.tool if proto.tool != "" else None,
        )
        del proto
        return pr

    def to_proto(self) -> agent_pb2.PromptRequest:
        req = agent_pb2.PromptRequest()
        if self.agent is not None:
            req.agent = self.agent
        if self.prompt is not None:
            req.prompt = self.prompt
        if self.tool is not None:
            req.tool = self.tool
        return req

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptRequest":
        return cls(
            agent=data.get("agent"),
            prompt=data.get("prompt"),
            tool=data.get("tool"),
        )

    def missing_fields(self) -> List[str]:
        missing: List[str] = []
        if _is_missing_str(self.agent):
            missing.append("agent")
        if _is_missing_str(self.prompt):
            missing.append("prompt")
        if _is_missing_str(self.tool):
            missing.append("tool")
        return missing

    def is_complete(self) -> bool:
        return len(self.missing_fields()) == 0


@dataclass
class PromptAnswer:
    answer: Optional[str] = None

    @classmethod
    def from_proto(cls, proto: agent_pb2.PromptAnswer) -> "PromptAnswer":
        pr =  cls(
            answer=proto.answer if proto.answer != "" else None,
        )
        del proto
        return pr
    

    def to_proto(self) -> agent_pb2.PromptAnswer:
        resp = agent_pb2.PromptAnswer()
        if self.answer is not None:
            resp.answer = self.answer
        return resp

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptAnswer":
        return cls(
            answer=data.get("answer"),
        )

    def missing_fields(self) -> List[str]:
        missing: List[str] = []
        if _is_missing_str(self.answer):
            missing.append("answer")
        return missing

    def is_complete(self) -> bool:
        return len(self.missing_fields()) == 0


__all__ = ["PromptRequest", "PromptAnswer"]
