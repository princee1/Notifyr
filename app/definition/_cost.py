from typing import Type
from fastapi import Request


class Cost():

    def __init__(self,cost_key:str,c=0):
        self.cost_key = cost_key
        self.c=c
    
    


def InjectCost(key:str,cost_type:Type[Cost],start_cost:int=0):
    return lambda :cost_type(key,start_cost)