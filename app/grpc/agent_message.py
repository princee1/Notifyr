from __future__ import annotations
from typing import List, Optional, Dict, Any, Union
import json
import app.grpc.agent_pb2 as agent_pb2


class ContentBlock:
    """Wrapper for gRPC ContentBlock message."""
    
    def __init__(self, mode: str, type: str, value: str, mime: Optional[str] = None):
        self.mode = mode
        self.type = type
        self.value = value
        self.mime = mime

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ContentBlock:
        return cls(
            mode=data.get("mode", ""),
            type=data.get("type", ""),
            value=data.get("value", ""),
            mime=data.get("mime",None),
        )

    def to_proto(self) -> agent_pb2.ContentBlock:
        block = agent_pb2.ContentBlock()
        block.mode = self.mode or ""
        block.type = self.type or ""
        block.value = self.value or ""
        if self.mime:
            block.mime = self.mime
        return block


class Context:
    """Wrapper for gRPC Context message."""
    
    def __init__(
        self,
        user: Optional[str] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        channel: Optional[str] = None,
        auth: Optional[str] = None,
        save: bool = False,
        user_encoded: Optional[str] = None,
        permissions: Optional[List[str]] = None,
    ):
        self.user = user
        self.request_id = request_id
        self.session_id = session_id
        self.channel = channel
        self.auth = auth
        self.save = save
        self.user_encoded = user_encoded
        self.permissions = permissions or []

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Context':
        return cls(
            user=data.get("user"),
            request_id=data.get("request_id"),
            session_id=data.get("session_id"),
            channel=data.get("channel"),
            auth=data.get("auth"),
            save=data.get("save", False),
            user_encoded=data.get("user_encoded"),
            permissions=data.get("permissions", []),
        )

    @classmethod
    def from_proto(cls, proto: agent_pb2.Context) -> 'Context':
        return cls(
            user=proto.user or None,
            request_id=proto.request_id or None,
            session_id=proto.session_id or None,
            channel=proto.channel or None,
            auth=proto.auth or None,
            save=proto.save,
            user_encoded=proto.user_encoded or None,
            permissions=list(proto.permissions),
        )

    def to_proto(self) -> agent_pb2.Context:
        ctx = agent_pb2.Context()
        if self.user:
            ctx.user = self.user
        if self.request_id:
            ctx.request_id = self.request_id
        if self.session_id:
            ctx.session_id = self.session_id
        if self.channel:
            ctx.channel = self.channel
        if self.auth:
            ctx.auth = self.auth
        ctx.save = self.save
        if self.user_encoded:
            ctx.user_encoded = self.user_encoded
        ctx.permissions.extend(self.permissions)
        return ctx

    

class PromptRequest:
    """Wrapper for gRPC PromptRequest with ContentBlock list conversion."""
    
    def __init__(
        self,
        agent: str,
        prompt: str,
        user: str,
        thread: str,
        mess_id: Optional[str] = None,
        send_at: Optional[float] = None,
        blocks: Optional[List[Union[Dict, ContentBlock]]] = None,
        context: Optional[Union[Dict, Context]] = None,
    ):
        self.agent = agent
        self.prompt = prompt
        self.user = user
        self.thread = thread
        self.mess_id = mess_id
        self.send_at = send_at
        self.blocks = [
            block if isinstance(block, ContentBlock) else ContentBlock.from_dict(block)
            for block in (blocks or [])
        ]
        self.context = (
            context if isinstance(context, Context) else Context.from_dict(context)
            if context else None
        )

    @classmethod
    def from_proto(cls, proto: agent_pb2.PromptRequest) -> PromptRequest:
        blocks = [
            ContentBlock(mode=b.mode, type=b.type, value=b.value, mime=b.mime or None)
            for b in proto.blocks
        ]
        context = Context.from_proto(proto.context) if proto.HasField("context") else None
        return cls(
            proto.agent,
            proto.prompt,
            proto.user,
            proto.thread,
            proto.mess_id or None,
            proto.send_at or None,
            blocks,
            context,
        )

    def to_proto(self) -> agent_pb2.PromptRequest:
        req = agent_pb2.PromptRequest()
        req.agent = self.agent or ""
        req.prompt = self.prompt or ""
        req.user = self.user or ""
        req.thread = self.thread or ""
        req.blocks.extend([b.to_proto() for b in self.blocks])
        if self.mess_id:
            req.mess_id = self.mess_id
        if self.send_at:
            req.send_at = self.send_at
        if self.context:
            req.context.CopyFrom(self.context.to_proto())
        return req


class PromptAnswer:
    """Wrapper for gRPC PromptAnswer with TypedDict list conversion."""
    
    def __init__(
        self,
        text: str,
        reply_id: str,
        agent: str,
        reasoning: Optional[List[Dict]] = None,
        tool_calling: Optional[List[Dict]] = None,
        invalid_tool_calling: Optional[List[Dict]] = None,
        reason: Optional[str] = None,
    ):
        self.text = text
        self.reply_id = reply_id
        self.agent = agent
        self.reason = reason
        self.reasoning = self._build_reasoning(reasoning or [])
        self.tool_calling = self._build_tool_calling(tool_calling or [])
        self.invalid_tool_calling = self._build_invalid_tool_calling(invalid_tool_calling or [])

    @staticmethod
    def _build_reasoning(items: List[Dict]) -> List[agent_pb2.Reasoning]:
        result = []
        for item in items:
            r = agent_pb2.Reasoning()
            r.index = item.get("index", 0)
            r.thought = str(item.get("thought", ""))
            r.id = str(item.get("id", ""))
            result.append(r)
        return result

    @staticmethod
    def _build_tool_calling(items: List[Dict]) -> List[agent_pb2.ToolCalling]:
        result = []
        for item in items:
            tc = agent_pb2.ToolCalling()
            tc.id = str(item.get("id", ""))
            args = item.get("args", {})
            tc.args = json.dumps(args) if isinstance(args, dict) else str(args)
            tc.name = str(item.get("name", ""))
            result.append(tc)
        return result

    @staticmethod
    def _build_invalid_tool_calling(items: List[Dict]) -> List[agent_pb2.InvalidToolCalling]:
        result = []
        for item in items:
            itc = agent_pb2.InvalidToolCalling()
            itc.id = str(item.get("id", ""))
            args = item.get("args", {})
            itc.args = json.dumps(args) if isinstance(args, dict) else str(args)
            itc.name = str(item.get("name", ""))
            itc.error = str(item.get("error", ""))
            itc.index = str(item.get("index", ""))
            result.append(itc)
        return result

    @classmethod
    def from_proto(cls, proto: agent_pb2.PromptAnswer) -> PromptAnswer:
        reasoning = [{"index": r.index, "thought": r.thought, "id": r.id} for r in proto.reasoning]
        tool_calling = [{"id": tc.id, "args": tc.args, "name": tc.name} for tc in proto.tool_calling]
        invalid_tool_calling = [
            {"id": itc.id, "args": itc.args, "name": itc.name, "error": itc.error, "index": itc.index}
            for itc in proto.invalid_tool_calling
        ]
        return cls(
            proto.text,
            proto.reply_id,
            proto.agent,
            reasoning,
            tool_calling,
            invalid_tool_calling,
            proto.reason or None,
        )

    def to_proto(self) -> agent_pb2.PromptAnswer:
        resp = agent_pb2.PromptAnswer()
        resp.text = self.text or ""
        resp.reply_id = self.reply_id or ""
        resp.agent = self.agent or ""
        if self.reason:
            resp.reason = self.reason
        resp.reasoning.extend(self.reasoning)
        resp.tool_calling.extend(self.tool_calling)
        resp.invalid_tool_calling.extend(self.invalid_tool_calling)
        return resp

    def export(self)->dict:
        return {
            'text': self.text,
            'reply_id': self.reply_id,
            'agent': self.agent,
            'reasoning': self.reasoning,
            'tool_calling': self.tool_calling,
            'invalid_tool_calling': self.invalid_tool_calling,
        }


__all__ = ["ContentBlock", "Context", "PromptRequest", "PromptAnswer"]
