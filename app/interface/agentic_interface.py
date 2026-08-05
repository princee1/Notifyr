from app.definition._interface import Interface, IsInterface
from app.definition._service import ServiceStatus
from app.errors.agent_error import AgentNotAvailableError, AgentOnlyAsSubAgentError

acceptable_service = {ServiceStatus.AVAILABLE,ServiceStatus.WORKS_ALMOST_ATT,ServiceStatus.PARTIALLY_AVAILABLE}

@IsInterface()
class AgenticInterface(Interface):
    
    def _verify_status(self,_raise=False):
        if self.service_status not in acceptable_service:
            raise AgentNotAvailableError(self.service_status,self.reason,self.miniService_id)
        if self.service_status != ServiceStatus.AVAILABLE:
            if _raise :
                raise AgentNotAvailableError(self.service_status,self.reason,self.miniService_id)
            return self.reason
        if not self.is_main_agent:
            raise AgentOnlyAsSubAgentError(self.miniService_id)
        
        return None

    #########################################################################################################
    ############################                                          ###################################
    #########################################################################################################
    @property
    def is_main_agent(self):
        return self.agent_model.type == 'main-agent'

    @property
    def agent_name(self)->str:
        return f"agent:{self.agent_model.alias}#{self.agent_model.id}"