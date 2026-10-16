from typing import Literal

from fastapi import Depends, Request, Response
from app.classes.auth_permission import ClientType, ClientTypeLiteral, IssuerInfo, IssuerInfoModel
from app.depends.funcs_dep import get_issuer
from app.utils.constant import HTTPHeaderConstant
from app.utils.helper import slice_dict


__bypass_type__:set[ClientType|ClientTypeLiteral] = {'Admin','System',ClientType.Admin,ClientType.System}
class IssuerManager:

    def __init__(self,response:Response,request:Request,issuer:IssuerInfo|None=Depends(get_issuer)):
        self.issuerInfo = issuer
        self.request = request
        self.response = response
        response.headers[HTTPHeaderConstant.X_ISSUER_ID] = issuer['issuer']

    def export(self,mode:Literal['model','dict']='dict'):
        if self.issuerInfo == None:
            return None
        val = slice_dict(self.issuerInfo,{'type',},mode='exclude',copy=True)
        if mode == 'dict':
            return val
        return IssuerInfoModel(**val)

    def verify_ownership(self,provided:IssuerInfo|IssuerInfoModel|None,access_mode:Literal['read','write']='write',__raise__=True):
        if provided == None:
            return True
        
        if self.issuerInfo == None and __raise__:
            raise 

        if self.issuerInfo == None and not __raise__:
            return False

        if self.issuerInfo['type'] in __bypass_type__:
            return True

        if isinstance(provided,IssuerInfoModel):
            provided = provided.model_dump()

        ownership = provided['ownership']
        while True:
            match ownership:
                case 'exclusive':
                    if self.issuerInfo['issuer'] != provided['issuer']:
                        if __raise__:
                            ...
                        else:
                            ...
                    else:
                        return True
                case 'private':
                    if access_mode == 'read':
                        return True
                    ownership = 'exclusive'
                case 'public':
                    return True
                case 'protected':
                    if access_mode == 'read':
                        return True
                    if self.issuerInfo.get('group',None) != provided['group']:
                        if __raise__:
                            ...
                        else:
                            ...
                    else:
                        return True
