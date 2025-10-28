from typing import Any
from fastapi import Request, Response
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, UseGuard, UsePipe

async def pipe_after(result:Any,response:Response):
    response.status_code = 201
    return {
        **result,
        'after':"caca"
    }

async def pipe_before(request:Request,):
    request.state.test = 'pipi'
    return {}

async def guard():
    return True,''


@HTTPRessource('test')
class TestRessource(BaseHTTPRessource):

    @UseGuard(guard)
    @UsePipe(pipe_before)
    @UsePipe(pipe_before)
    @UsePipe(pipe_after,before=False)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST])
    def test(self,request:Request,response:Response):
        return {
            'before':request.state.test
        }
