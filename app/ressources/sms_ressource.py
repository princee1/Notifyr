from definition._ressource import Permission, Ressource, Handler
from container import InjectInMethod, InjectInFunction
from services.twilio_service import SMSService


SMS_ONGOING_PREFIX = 'sms-ongoing'


class OnGoingSMSRessource(Ressource):
    @InjectInMethod
    def __init__(self, smsService: SMSService) -> None:
        super().__init__("sms-ongoing")
        self.smsService: SMSService = smsService

    @Ressource.AddRoute('/otp/')
    def sms_relay_otp(self,):
        pass

    @Ressource.AddRoute('/simple/')
    def sms_simple_message(self,):
        pass

    @Ressource.AddRoute('/chat/')
    def sms_chat(self,):
        pass

    @Ressource.AddRoute('/template/')
    def sms_template(self,):
        ...

    def _add_handcrafted_routes(self):
        # self.router.add_api_route(
        #     path='/otp/', endpoint=self.sms_relay_otp, methods=['POST'], description=self.sms_relay_otp.__doc__)
        # self.router.add_api_route(
        #     path='/simple/', endpoint=self.sms_simple_message, methods=['POST'], description=self.sms_simple_message.__doc__)
        # self.router.add_api_route(
        #     path='/chat/', endpoint=self.sms_chat, methods=['POST'], description=self.sms_chat.__doc__)
        # self.router.add_api_route(
        #     path='/template/{template}', endpoint=self.sms_template, methods=['POST'], description=self.sms_template.__doc__)
        ...

SMS_INCOMING_PREFIX = "sms-incoming"


class IncomingSMSRessource(Ressource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__("sms-incoming")
