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
    temperature: Optional[float] = None
    tool: Optional[str] = None

    @classmethod
    def from_proto(cls, proto: agent_pb2.PromptRequest) -> "PromptRequest":
        pr = cls(
            agent=proto.agent if proto.agent != "" else None,
            prompt=proto.prompt if proto.prompt != "" else None,
            temperature=proto.temperature if proto.temperature != 0.0 else None,
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
        if self.temperature is not None:
            # protobuf default for float is 0.0; set only when provided
            req.temperature = float(self.temperature)
        if self.tool is not None:
            req.tool = self.tool
        return req

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptRequest":
        return cls(
            agent=data.get("agent"),
            prompt=data.get("prompt"),
            temperature=data.get("temperature"),
            tool=data.get("tool"),
        )

    def missing_fields(self) -> List[str]:
        missing: List[str] = []
        if _is_missing_str(self.agent):
            missing.append("agent")
        if _is_missing_str(self.prompt):
            missing.append("prompt")
        if self.temperature is None:
            missing.append("temperature")
        if _is_missing_str(self.tool):
            missing.append("tool")
        return missing

    def is_complete(self) -> bool:
        return len(self.missing_fields()) == 0


@dataclass
class PromptAnswer:
    input_token: Optional[int] = None
    output_token: Optional[int] = None
    answer: Optional[str] = None

    @classmethod
    def from_proto(cls, proto: agent_pb2.PromptAnswer) -> "PromptAnswer":
        pr =  cls(
            input_token=proto.input_token if proto.input_token != 0 else None,
            output_token=proto.output_token if proto.output_token != 0 else None,
            answer=proto.answer if proto.answer != "" else None,
        )
        del proto
        return pr
    

    def to_proto(self) -> agent_pb2.PromptAnswer:
        resp = agent_pb2.PromptAnswer()
        if self.input_token is not None:
            resp.input_token = int(self.input_token)
        if self.output_token is not None:
            resp.output_token = int(self.output_token)
        if self.answer is not None:
            resp.answer = self.answer
        return resp

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptAnswer":
        return cls(
            input_token=data.get("input_token"),
            output_token=data.get("output_token"),
            answer=data.get("answer"),
        )

    def missing_fields(self) -> List[str]:
        missing: List[str] = []
        if self.input_token is None:
            missing.append("input_token")
        if self.output_token is None:
            missing.append("output_token")
        if _is_missing_str(self.answer):
            missing.append("answer")
        return missing

    def is_complete(self) -> bool:
        return len(self.missing_fields()) == 0


__all__ = ["PromptRequest", "PromptAnswer"]
