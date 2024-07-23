from services.assetsService import AssetService
from services.configService import ConfigService
from services.emailService import EmailReader,EmailSender
from services.twilloService import TwilioService

__DEPENDENCY: list[type] = [AssetService, ConfigService, EmailReader, EmailSender, TwilioService]
