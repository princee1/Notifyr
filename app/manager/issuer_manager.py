from fastapi import Depends, Request, Response
from app.classes.auth_permission import ClientType, ClientTypeLiteral, IssuerInfo
from app.depends.funcs_dep import get_issuer
from app.utils.constant import HTTPHeaderConstant


class IssuerManager:

    def __init__(self,response:Response,request:Request,issuer:IssuerInfo=Depends(get_issuer)):
        self.issuerInfo = issuer
        self.request = request
        self.response = response
        response.headers[HTTPHeaderConstant.X_ISSUER_ID] = issuer['issuer']


    def verify_issuer(self,provided:str):
        ...

    def verify_type(self,provided:ClientTypeLiteral|ClientType):
        ...

