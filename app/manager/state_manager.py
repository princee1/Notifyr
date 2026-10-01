from fastapi import Request, Response
from typing import Literal, Dict, Any

class StateManager:
  def __init__(self,request:Request,response:Response):
    self.request = request
    self.response = response
    self.store:Dict[str,Any] = {}

  def __getitem__(self, key):
      return 
  
  @property
  def state(self):
    return self.request.state
  
