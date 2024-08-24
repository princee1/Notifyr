from container import InjectInConstructor
from definition._ressource import Ressource
from services.email import EmailSender

class EmailRessource(Ressource):
    @InjectInConstructor
    def __init__(self, emailSender:EmailSender) -> None:
        super().__init__()
        #self.emailService:EmailSender = self.get(EmailSender)
        self.emailService: EmailSender = emailSender

