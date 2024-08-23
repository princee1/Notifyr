from definition._ressource import Ressource
from services.email import EmailSender
class EmailRessource(Ressource):

    def __init__(self) -> None:
        super().__init__()
        self.emailService:EmailSender = self.container.get(EmailSender)
    pass