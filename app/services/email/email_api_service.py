
from app.classes.mail_oauth_access import GoogleFlowType,MailOAuthFactory
from app.classes.mail_provider import provider_map
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from base64 import urlsafe_b64encode, urlsafe_b64decode

from app.definition._service import BaseService, MiniService, Service
from app.interface.email import EmailSendInterface,EmailReadInterface
from app.services.config_service import ConfigService



class EmailAPIService(BaseService,EmailSendInterface,EmailReadInterface):
    
    def __init__(self,configService:ConfigService):
        super().__init__()
        EmailReadInterface.__init__(self)
        EmailSendInterface.__init__(self)
        self.configService= configService

    def build(self,build_state=-1):
        ...


@MiniService()
class GMailAPIMiniService(EmailAPIService):
    def __init__(self, flowtype: GoogleFlowType, credentials):
        """
        Initializes the GMailAPI with a specific Google OAuth2 flow type and credentials.

        Args:
            flowtype (GoogleFlowType): The type of Google OAuth flow used.
            credentials (google.oauth2.credentials.Credentials): OAuth2 credentials.
        """
        super().__init__()
        self.flowtype = flowtype
        self.credentials = credentials
        self.service = build('gmail', 'v1', credentials=self.credentials)

    def send_email(self,message:str):
        try:

            # Encode the message as base64
            #encoded_message = urlsafe_b64encode(message.as_bytes()).decode()
            encoded_message = ...
            # Send the message
            create_message = {'raw': encoded_message}
            sent_message = self.service.users().messages().send(userId='me', body=create_message).execute()
            return sent_message
        except HttpError as error:
            print(f"An error occurred: {error}")
            return None

    def list_messages(self, query='', max_results=10):
        try:
            response = self.service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
            messages = response.get('messages', [])
            return messages
        except HttpError as error:
            print(f"An error occurred: {error}")
            return []

    def get_message(self, message_id):
        try:
            message = self.service.users().messages().get(userId='me', id=message_id, format='full').execute()
            return message
        except HttpError as error:
            print(f"An error occurred: {error}")
            return None

    def list_labels(self):
        try:
            response = self.service.users().labels().list(userId='me').execute()
            labels = response.get('labels', [])
            return labels
        except HttpError as error:
            print(f"An error occurred: {error}")
            return []

@MiniService()
class MicrosoftGraphMailAPIMiniService(EmailAPIService):
    ...

