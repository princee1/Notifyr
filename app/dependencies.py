from app.services.assets import AssetService
from app.services.config import ConfigService
from app.services.email import EmailReader, EmailSender
from app.services.twillo import TwilioService
from app.services.support import SupportService, ChatService
from app.services.communication import PhoneService, SMSService
from app.services.training import TrainingService
from services.notification import SystemService,DiscordService
from app.services.security import SecurityService
from app.services.throttling import QueueService,RateLimiterService


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

