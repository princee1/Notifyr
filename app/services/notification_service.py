from .email_service import EmailSenderService
from .security_service import SecurityService
from classes.report import DiscordReport, Report, SystemReport,EmailReport,GoogleReport
from .config_service import ConfigService
from definition import _service
from time import sleep
from discord_webhook import DiscordWebhook, AsyncDiscordWebhook
# WARNING extends the ABC last
from interface.threads import InfiniteThreadInterface


@_service.AbstractServiceClass
class NotificationService(_service.Service):
    def __init__(self, configService: ConfigService) -> None:
        super().__init__()
        self.configService = ConfigService

    def notify(self, report: Report):
        self._treatArgument()
        self._notify()
        pass

    def _treatArgument(self, *args):
        pass

    def _notify(self, report: Report):
        pass
    pass  # BUG we can specify a kid class if we decide to inject a Notification

@_service.ServiceClass
class SystemNotificationService(NotificationService,InfiniteThreadInterface):
    MAX_TO_BE_SHOWED = 8
    DURATION = 10

    def __init__(self, configService: ConfigService, securityService: SecurityService) -> None:
        super().__init__(configService)
        self.securityService = securityService
        self.listNotification = []

    def _notify(self, report: SystemReport):
        """
        It sets the title and message of the notification, and then sets the event

        :param title: The title of the notification
        :param message: The message to be displayed
        """
        raise NotImplementedError
        self._addNotify(title, message)

    def _treatArgument(self, *args):
        return super()._treatArgument(*args)

    def _notificationDataToBeShowed(self):
        """
        It takes the last MAX_TO_BE_SHOWED elements from the list and returns them
        :return: A list of tuples.
        """
        tempList = []
        n = len(self.listNotification)
        if n == 0:
            return tempList
        if SystemNotificationService.MAX_TO_BE_SHOWED < n:
            iteration = n-SystemNotificationService.MAX_TO_BE_SHOWED-1
        else:
            iteration = -1

        try:
            for i in range(n-1, iteration, -1):
                tempList.append((self.listNotification.pop(i)))
        except:
            pass
        finally:
            return tempList

    def _addNotify(self, title, message):
        """
        The function `addNotify` adds a notification with a title and message to a list of
        notifications.

        :param title: The title parameter is a string that represents the title of the notification
        :param message: The `message` parameter is a string that represents the content of the
        notification message
        """
        raise not NotImplementedError
        self.semaphore.acquire()
        self.listNotification.append((title, message))
        if not self.event.isSet():
            self.event.set()
        self.semaphore.release()

    def _showNotification(self, tempList):
        """
        It takes a list of tuples, and for each tuple, it creates a ToastNotifier object, shows the toast,
        deletes the object, and waits for the duration of the toast plus 2 seconds.

        :param tempList: A list of tuples containing the title and message of the notification
        """
        raise NotImplementedError
        for title, message in tempList:
            try:
                test = ToastNotifier()
                test.show_toast(title=title, msg=message,
                                threaded=True, duration=DURATION)
                del test
            except:
                pass
            sleep(WAITING)

@_service.ServiceClass
class DiscordService(NotificationService):
    def __init__(self, configService: ConfigService) -> None:
        super().__init__(configService)

    def _notify(self, report: DiscordReport):
        # TODO send a discord webhook
        pass

    def send_webhook(self, report: DiscordReport):
        webhook = DiscordWebhook()
        pass

@_service.ServiceClass
class EmailNotificationService(NotificationService):
    def __init__(self, configService: ConfigService, emailService: EmailSenderService) -> None:
        super().__init__(configService)
        self.emailService: EmailSenderService = emailService

@_service.ServiceClass
class GoogleNotificationService(NotificationService):
    pass

ReportClass = {
    DiscordService.__name__: DiscordReport,
    SystemNotificationService.__name__: SystemReport,
    EmailNotificationService.__name__: EmailReport,
    GoogleNotificationService.__name__: GoogleReport,

}

def ReportBuilder(classname,*args,**kwargs) -> Report: # TODO Make as a decorator
    reportType = ReportClass[classname]
    return reportType(*args, **kwargs)
