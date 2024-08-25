from container import InjectInConstructor
from definition._ressource import Ressource
from services.email import EmailSenderService

class EmailRessource(Ressource):
    @InjectInConstructor
    def __init__(self, emailSender:EmailSenderService) -> None:
        super().__init__()
        #self.emailService:EmailSender = self.get(EmailSender)
        self.emailService: EmailSenderService = emailSender

