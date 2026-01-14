from .file_cost import FileCost
from app.models.object_model import ObjectS3ResponseModel
from app.services.database.object_service import DeleteError,Object

class ObjectCost(FileCost):
    
    def __inner__init__(self, request_id, issuer):
        super().__inner__init__(request_id, issuer)
        self.meta:dict[tuple,int] = {}

    def save_meta(self,meta:list[Object]):
        for m in meta:
            key = (str(m.object_name),str(m.version_id))
            self.meta[key] = m.size

    def post_refund(self, result:ObjectS3ResponseModel|dict):
        for meta in result.get('meta',[]):
            if isinstance(meta,dict):
                size = meta['size']
                name = meta.get('object_name')
                version = meta.get('version_id')
            elif isinstance(meta,Object):
                size = meta.size
                name = meta.object_name
                version = meta.version_id
            else:
                continue

            prices=self.compute_prices(self.POST_NAME,f'{name} @ {version}',size)
            for d,c,q in prices:
                self.refund(d,c,q)
                
    def post_payment(self,errors:list[DeleteError]):
        for e in errors:
            name = str(e.name)
            version = str(e.version_id)
            key = (name,version)
            if key not in self.meta:
                continue
            size = self.meta[key]
            prices=self.compute_prices(self.POST_NAME,f'{name} @ {version}',size)
            for d,c,q in prices:
                self.refund(d,c,q)