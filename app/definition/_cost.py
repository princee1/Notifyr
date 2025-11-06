from fastapi import Request


class Cost():

    def __init__(self,c=0):
        self.c=c

    def add_cost(self,c:int=1):
        self.c+=c
    
    def compute_cost(self,c:int):
        return c
    

def bind_cost_request(request:Request):
    cost:Cost |None = getattr(request.state,'cost',None)
    if cost == None:
        return 1
    return cost.c