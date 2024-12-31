from definition._ressource import Ressource, Handler
from container import InjectInMethod, InjectInFunction
from services.twilio_service import SMSService


SMS_ONGOING_PREFIX = 'sms-ongoing'
class OnGoingSMSRessource(Ressource):
    @InjectInMethod
    def __init__(self, smsService: SMSService) -> None:
        super().__init__("sms-ongoing")
        self.smsService = smsService

    def relay_otp(self,):
        pass

    def simple_message(self,):
        pass

    def sms_chat(self,):
        pass

    def sms_template(self,):
        ...

    def _add_routes(self):
        self.router.add_api_route('/otp/', self.relay_otp, methods=['POST'])
        self.router.add_api_route('/simple/', self.simple_message, methods=['POST'])
        self.router.add_api_route('/chat/', self.sms_chat, methods=['POST'])
        self.router.add_api_route('/template/', self.sms_template, methods=['POST'])
        

SMS_INCOMING_PREFIX = "sms-incoming"
class IncomingSMSRessource(Ressource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__("sms-incoming")
