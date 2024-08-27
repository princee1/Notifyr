from services.logger_service import LoggerService
from services.database_service import SQLiteService
from services.assets_service import AssetService
from services.config_service import ConfigService
from services.email_service import EmailReaderService, EmailSenderService
from services.support_service import SupportService, ChatService
from services.twilio_service import VoiceService, SMSService,TwilioService
from services.training_service import TrainingService
from services.notification_service import EmailNotificationService, GoogleNotificationService, SystemNotificationService, DiscordService
from services.security_service import SecurityService
from services.throttling_service import PriorityQueueService, RateLimiterService
from services.file_service import FileService,FTPService


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
