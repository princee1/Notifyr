from fastapi import Request, Response
from typing import Literal, Dict, Any

class StateManager:
  def __init__(self,request:Request,response:Response):
    self.request = request
    self.response = response
    self._store:Dict[str,Any] = {}
    self._activated = True

  def activate(self):
    self._activated = True

  def deactivate(self):
    self._activated = False

  def store(self,name:str,value:Any):
    self._store[name] = value
    return value

  def get(self,name:str):
    return self[name]

  def __getitem__(self, key:str):
    return self._store.get(key,None)
  
  @property
  def state(self):
    return self.request.state
  
