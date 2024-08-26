from app.services.logger_service import LoggerService
from app.services.database_service import SQLiteService
from app.services.assets_service import AssetService
from app.services.config_service import ConfigService
from app.services.email_service import EmailReaderService, EmailSenderService
from app.services.support_service import SupportService, ChatService
from app.services.twilio_service import VoiceService, SMSService,TwilioService
from app.services.training_service import TrainingService
from app.services.notification_service import EmailNotificationService, GoogleNotificationService, SystemNotificationService, DiscordService
from app.services.security_service import SecurityService
from app.services.throttling_service import PriorityQueueService, RateLimiterService
from app.services.file_service import FileService,FTPService


__DEPENDENCY: list[type] = [AssetService,
                            ConfigService,
                            EmailReaderService,
                            FileService,
                            EmailSenderService,
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
                            GoogleNotificationService,
                            #Stats Service
                            ]
