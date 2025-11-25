from celery.signals import task_failure,task_received,task_prerun,task_postrun,task_internal_error,task_retry,task_rejected,task_sent,task_success,task_revoked


class TaskSignals:
    ...