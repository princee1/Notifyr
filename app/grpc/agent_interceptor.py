import grpc
from enum import Enum

class HandlerType(Enum):
    ONE_ONE ='one_one'
    ONE_MANY ='one_many'
    MANY_ONE = 'many_one'
    MANY_MANY = 'many_many'




class AgentServerInterceptor(grpc.aio.ServerInterceptor):
    def __init__(self, expected_token,handler_map:dict[str,str]):
        self.expected_token = expected_token
        self.handler_map = handler_map

    async def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata)
        auth_header = metadata.get('authorization')
        
        if not auth_header or not auth_header.startswith("Bearer "):
            return self._abort(grpc.StatusCode.UNAUTHENTICATED, "Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        if token != self.expected_token:
            return self._abort(grpc.StatusCode.PERMISSION_DENIED, "Invalid token")
        
        return await continuation(handler_call_details)

    def _abort(self, code, details, method):
        handler_type = self.handler_map.get(method, HandlerType.ONE_ONE)
        # Helper to abort the RPC call
        def abort_handler(request, context):
            context.abort(code, details)

        match handler_type:
            case HandlerType.ONE_ONE:
                return grpc.unary_unary_rpc_method_handler(abort_handler)
            case HandlerType.ONE_MANY:
                return grpc.unary_stream_rpc_method_handler(abort_handler)
            case HandlerType.MANY_ONE:
                return grpc.stream_unary_rpc_method_handler(abort_handler)
            case HandlerType.MANY_MANY:
                return grpc.stream_stream_rpc_method_handler(abort_handler)
            case _:
                return grpc.unary_unary_rpc_method_handler(abort_handler)

class AgentClientAsyncInterceptor(grpc.aio.UnaryUnaryClientInterceptor,grpc.aio.StreamUnaryClientInterceptor,grpc.aio.UnaryStreamClientInterceptor,grpc.aio.StreamStreamClientInterceptor):

    def __init__(self, token):
        self.token = token

    async def intercept_unary_unary(self, continuation, client_call_details, request):
        new_details = inject_bearer_token(client_call_details, self.token)
        return await continuation(new_details, request)

    async def intercept_stream_unary(self, continuation, client_call_details, request_iterator):
        new_details = inject_bearer_token(client_call_details, self.token)
        return await continuation(new_details, request_iterator)

    async def intercept_unary_stream(self, continuation, client_call_details, request):
        new_details = inject_bearer_token(client_call_details, self.token)
        return await continuation(new_details, request)

    async def intercept_stream_stream(self, continuation, client_call_details, request_iterator):
        new_details = inject_bearer_token(client_call_details, self.token)
        return await continuation(new_details, request_iterator)

class AgentClientInterceptor(grpc.UnaryUnaryClientInterceptor):

    def __init__(self, token):
        self.token = token

    def intercept_unary_unary(self, continuation, client_call_details, request):
        new_details = inject_bearer_token(client_call_details, self.token)
        return continuation(new_details, request)


def inject_bearer_token(client_call_details,token):
    metadata = []
    if client_call_details.metadata is not None:
        metadata = list(client_call_details.metadata)
        
    metadata.append(('authorization', f'Bearer {token}'))
    new_details = client_call_details._replace(metadata=metadata)
    return new_details   