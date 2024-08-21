from interface.base import BaseRessource
from services.email import EmailSender
class EmailRessource(BaseRessource):

    def __init__(self) -> None:
        super().__init__()
        self.emailService:EmailSender = self.container.get(EmailSender)
    pass