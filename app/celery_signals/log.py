from celery.signals import setup_logging,after_setup_logger,after_setup_task_logger

class LoggingSignals:


    def on_setup_logging():
        ...

    
    def on_after_setup_loger():
        ...
    
    def on_after_setup_task_logger():
        ...