from email.mime.multipart import MIMEMultipart
from email import encoders
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.utils import make_msgid
from email.utils import formatdate
from typing import List, Optional, Literal
from app.utils.fileIO import getFilenameOnly


class EmailMetadata:
    def __init__(
        self,
        Subject: str,
        From: str,
        To: str | List[str],
        CC: Optional[str] = None,
        Bcc: Optional[str] = None,
        replyTo: Optional[str] = None,
        Return_Path: Optional[str] = None,
        Priority: Literal['1', '3', '5'] = '1'
    ):
        self.Subject = Subject
        self.From = From
        self.To:list[str] | str = To if isinstance(To, list) else [To]
        self.CC:list[str] | str = CC
        self.Bcc = Bcc
        self.replyTo = replyTo
        self.Return_Path = Return_Path
        self.Priority = Priority

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
        self.id = make_msgid()
        self.message['Message-ID'] = self.id
        self.message['Date'] = formatdate(localtime=True)
        self.message['Reply-To'] = emailMetaData.replyTo
        self.message['Return-Path'] = emailMetaData.Return_Path
        self.message['X-Priority'] = emailMetaData.Priority
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
