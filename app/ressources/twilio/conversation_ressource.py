from app.definition._ressource import BaseHTTPRessource, HTTPRessource

CONVERSATION_ONGOING_PREFIX = "conversation-ongoing"

@HTTPRessource(CONVERSATION_ONGOING_PREFIX)
class ConversationOnGoingRessource(BaseHTTPRessource):
    ...


CONVERSATION_INCOMING_PREFIX="conversation-incoming"
@HTTPRessource(CONVERSATION_INCOMING_PREFIX)
class ConversationIncomingRessource(BaseHTTPRessource):
    ...

@HTTPRessource("conversation",routers=[CONVERSATION_ONGOING_PREFIX, CONVERSATION_INCOMING_PREFIX],mount=False)
class ConversationRessource(BaseHTTPRessource):
    ...

    def __init__(self):
        super().__init__(None,None)
    
    