from services.logger import LoggerService
from services.database import SQLiteService
from services.assets import AssetService
from services.config import ConfigService
from services.email import EmailReader, EmailSender
from services.support import SupportService, ChatService
from services.twilio_communication import VoiceService, SMSService,TwilioService
from services.training import TrainingService
from services.notification import AYCDNotificationService, EmailNotificationService, GoogleNotificationService, SystemNotificationService, DiscordService
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
                            VoiceService,
                            TrainingService,
                            SMSService,
                            SystemNotificationService,
                            DiscordService,
                            SecurityService,
                            PriorityQueueService,
                            RateLimiterService,
                            FTPService,
                            SQLiteService,
                            LoggerService,
                            EmailNotificationService,
                            AYCDNotificationService,
                            GoogleNotificationService,
                            ]
