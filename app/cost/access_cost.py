from app.definition._cost import DataCost


class AccessCost(DataCost):

    def post_refund(self,result:list[str]):
        for r in result:
            self.refund(f'Deleting the {r} access',self.default_price,1)