from email.mime.multipart import MIMEMultipart
from email import encoders
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.utils import formatdate
from typing import List, Optional, Literal
from app.definition._error import BaseError
from app.utils.constant import EmailHeadersConstant
from app.utils.fileIO import getFilenameOnly
from dataclasses import dataclass
from typing import List, Optional, Literal, Union
from email.message import Message
from email.header import decode_header
from dataclasses import dataclass, field


class NotSameDomainEmailError(BaseError):
    ...

class EmailInvalidFormatError(BaseError):
    ...

@dataclass
class EmailMetadata:
    Subject: str
    From: str
    To: Union[str, List[str]]
    CC: Optional[Union[str, List[str]]] = None
    Bcc: Optional[str] = None
    replyTo: Optional[str] = None
    Return_Path: Optional[str] = None
    Priority: Literal['1', '3', '5'] = '1'
    Disposition_Notification_To: Optional[str] = None
    Return_Receipt_To: Optional[str] = None
    X_Email_ID: Optional[str] = None
    Message_ID: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.To, str):
            self.To = [self.To]
        if isinstance(self.CC, str):
            self.CC = [self.CC]

    def __str__(self):
        return (
            f"Subject: {self.Subject}\n"
            f"From: {self.From}\n"
            f"To: {self.To}\n"
            f"CC: {self.CC}\n"
            f"Bcc: {self.Bcc}\n"
            f"Reply-To: {self.replyTo}\n"
            f"Return-Path: {self.Return_Path}\n"
            f"Priority: {self.Priority}\n"
        )


class EmailBuilder():

    def __init__(self, content: tuple[str, str], emailMetaData: EmailMetadata, images: list[tuple[str, str]], attachments: list[tuple[str, str]]=[]) -> None:
        self.emailMetadata = emailMetaData
        self.message: MIMEMultipart = MIMEMultipart()
        self.message["From"] = emailMetaData.From
        self.message["Subject"] = emailMetaData.Subject
        self.multiple_dest(emailMetaData.To, "To")
        self.multiple_dest(emailMetaData.CC, "Cc",False)
        
        self.id = emailMetaData.Message_ID
        self.message['Message-ID'] = self.id
        self.message['Date'] = formatdate(localtime=True)
        self.message['Reply-To'] = emailMetaData.replyTo
        self.message['Return-Path'] = emailMetaData.Return_Path
        self.message['X-Priority'] = emailMetaData.Priority
        if emailMetaData.X_Email_ID:
            self.message['X_Email_ID'] = emailMetaData.X_Email_ID

        if emailMetaData.Disposition_Notification_To:
            self.message['Disposition-Notification-To'] = emailMetaData.Disposition_Notification_To

        if emailMetaData.Return_Receipt_To:
            self.message['Return-Receipt-To'] = emailMetaData.Return_Receipt_To
        
        self.init_email_content(attachments, images, content)

    def __str__(self):
        return self.emailMetadata.__str__()
    
    def __repr__(self):
        return self.emailMetadata.__str__()

    def multiple_dest(self, param, key,required =True):
        if type(param) == str:
            self.message[key] = param
        elif type(param) == list:
            temp = ",".join(param)
            self.message[key] = temp
            pass
        else:
            if required:
                raise TypeError

    def add_attachements(self, attachement_name, attachment_data):
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment_data)
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {attachement_name}",
        )
        pass

    def set_content(self, content: tuple[str, str]):
        html_content, text_content = content
        part1 = MIMEText(text_content, "plain")
        part2 = MIMEText(html_content, "html")
        self.message.attach(part1)
        self.message.attach(part2)

    def attach_image(self, image_path, image_data, disposition: Literal["inline", "attachment"] = "inline"):
        img = MIMEImage(image_data)
        img.add_header("Content-ID", f"<{image_path}>")
        img.add_header("Content-Disposition", disposition,
                       filename=getFilenameOnly(image_path))
        self.message.attach(img)

    def init_email_content(self, attachments: list[tuple[str, str]], images: list[tuple[str, str]], content: tuple[str, str]):
        self.set_content(content)
        for img in images:
            path, img_data = img
            self.attach_image(path, img_data)
        for attachment in attachments:
            path, att_data = attachment
            self.add_attachements(path, att_data)

        pass

    @property
    def mail_message(self):
        return self.id, self.message.as_string()

    pass


class FutureEmailBuilder(EmailBuilder):

    def __init__(self, attachments: List[tuple[str, str]], images: List[tuple[str, str]], content: tuple[str, str], emailMetaData: EmailMetadata) -> None:
        super().__init__(attachments, images, content, emailMetaData)
    pass


#######################################################                        #################################
@dataclass
class EmailReader:
    Subject: str = None
    From: str = None
    To: str = None
    CC: str = None
    Date: str = None
    Is_Multipart: bool = False
    Plain_Body: str = None
    HTML_Body: str = None
    Attachments: list = field(default_factory=list)
    Headers: dict = field(default_factory=dict)

    def __post_init__(self):
        pass  # Prevents the dataclass from generating its own __init__

    def __init__(self,msg:Message):
        self.parse_email(msg)
        self.parse_body(msg)
        
    def parse_email(self, msg: Message):
        # Parse headers
        self.Subject = self.decode_header_field(msg.get("Subject"))
        self.From = msg.get("From")
        self.To = msg.get("To")
        self.CC = msg.get("Cc")
        self.Date = msg.get("Date")

        # Store all headers
        for header, value in msg.items():
            self.Headers[header] = value

        # Check if the email is multipart
        self.Is_Multipart = msg.is_multipart()

        self.parse_body(msg)

    def parse_body(self, msg: Message):
        if self.Is_Multipart:
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if content_type == "text/plain" and "attachment" not in content_disposition:
                    self.Plain_Body = part.get_payload(decode=True).decode(errors="ignore")
                elif content_type == "text/html" and "attachment" not in content_disposition:
                    self.HTML_Body = part.get_payload(decode=True).decode(errors="ignore")
                elif "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        attachment_data = part.get_payload(decode=True)
                        self.Attachments.append({"filename": filename, "data": attachment_data})
        else:
            # If not multipart, treat the payload as plain text
            self.Plain_Body = msg.get_payload(decode=True).decode(errors="ignore")

    @staticmethod
    def decode_header_field(field):
        if not field:
            return None
        decoded_parts = decode_header(field)
        decoded_string = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_string += part.decode(encoding or "utf-8", errors="ignore")
            else:
                decoded_string += part
        return decoded_string

    @property
    def Email_ID(self):
        """
        Email ID generated for database PK
        """
        return self.Headers.get(EmailHeadersConstant.X_EMAIL_ID,None)

    @property
    def Message_ID(self):
        """
        Message ID generated for the smtp email transactions
        """
        return self.Headers.get(EmailHeadersConstant.MESSAGE_ID,None)
    
    @property
    def References(self):
        references:str = self.Headers.get('References',None)
        if not references:
            return []
        return references.split(' ')

    @property
    def In_Reply_To(self):
        return self.Headers.get('In-Reply-To',None)
