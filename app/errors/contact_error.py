from app.definition._error import BaseError

class ContactNotExistsError(BaseError):
    def __init__(self,id, *args):
        super().__init__(*args)
        self.id = id


class ContactAlreadyExistsError(BaseError):
    
    def __init__(self,email,phone ,*args):
        self.email=email
        self.phone=phone
        super().__init__(*args)
    
    @property
    def message(self):
        if self.email and self.phone:
            return "Both the email and the phone field is already used"

        if self.email:
            return "The email field is already used"
        
        return "The phone field is already used"

class ContactOptInCodeNotMatchError(BaseError):
    ...

class ContactDoubleOptInAlreadySetError(BaseError):
    ...

class ContactMissingInfoKeyError(BaseError):
    def __init__(self,info_key, *args):
        super().__init__(*args)
        self.info_key = info_key