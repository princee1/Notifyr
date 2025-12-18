from app.definition._ressource import BaseHTTPRessource, HTTPRessource

@HTTPRessource('kg')
class KGGraphDBRessource(BaseHTTPRessource):
    ...