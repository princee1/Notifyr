from services.assetsService import AssetService
from services.configService import ConfigService
from services.emailService import EmailReader, EmailSender
from services.twilloService import TwilioService
from services.supportService import SupportService, ChatService
from services.communicationService import PhoneService, SMSService
from services.trainingService import TrainingService
from services.notification import SystemService,DiscordService
from services.securityService import SecurityService
from services.throttlingService import QueueService,RateLimiterService


__DEPENDENCY: list[type] = [AssetService, 
                            ConfigService, 
                            EmailReader, 
                            EmailSender,
                            TwilioService, 
                            SupportService, 
                            ChatService, 
                            PhoneService, 
                            TrainingService,  
                            SMSService,
                            SystemService,
                            DiscordService,
                            SecurityService,
                            QueueService,
                            RateLimiterService ]

