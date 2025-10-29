from typing import Any
from fastapi import Request, Response
from app.definition._utils_decorator import Interceptor
from app.depends.class_dep import KeepAliveQuery


class KeepAliveResponseInterceptor(Interceptor):
    
    def _before(self):
        ...

    def _after(self,result:Any|Response, keepAliveConn:KeepAliveQuery,request:Request):
        keepAliveConn.dispose()
        