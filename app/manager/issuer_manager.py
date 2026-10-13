class IssuerManager:

    def __init__(self,issuer:str):
        self.issuer = issuer


    def verify_issuer(self,provided:str):
        ...