from services.assets import AssetService
from services.config import ConfigService
from services.email import EmailReader, EmailSender
from services.twillo import TwilioService
from services.support import SupportService, ChatService
from services.communication import PhoneService, SMSService
from services.training import TrainingService
from services.notification import SystemNotificationService, DiscordService
from services.security import SecurityService
from services.throttling import PriorityQueueService, RateLimiterService
from services.file import FileService,FTPService


__DEPENDENCY: list[type] = [AssetService,
                            ConfigService,
                            EmailReader,
                            FileService,
                            EmailSender,
                            TwilioService,
                            SupportService,
                            ChatService,
                            PhoneService,
                            TrainingService,
                            SMSService,
                            SystemNotificationService,
                            DiscordService,
                            SecurityService,
                            PriorityQueueService,
                            RateLimiterService,
                            FTPService
                            ]
