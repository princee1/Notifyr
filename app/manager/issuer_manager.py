from app.classes.auth_permission import ClientType, ClientTypeLiteral


class IssuerManager:

    def __init__(self,issuer:str,issuer_type:ClientTypeLiteral|ClientType=None):
        self.issuer = issuer
        self.issuer_type= issuer_type

    def verify_issuer(self,provided:str):
        ...

    def verify_type(self,provided:ClientTypeLiteral|ClientType):
        ...