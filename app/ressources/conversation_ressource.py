from app.definition._ressource import BaseHTTPRessource, HTTPRessource

CONVERSATION_ONGOING_PREFIX = "conversation-ongoing"

@HTTPRessource(CONVERSATION_ONGOING_PREFIX)
class ConversationOnGoingRessource(BaseHTTPRessource):
    ...


CONVERSATION_INCOMING_PREFIX="conversation-incoming"
@HTTPRessource(CONVERSATION_INCOMING_PREFIX)
class ConversationIncomingRessource(BaseHTTPRessource):
    ...