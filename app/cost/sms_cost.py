from app.definition._cost import TaskCost


class SMSCost(TaskCost):
    
    def compute_cost(self, scheduler, taskManager, tracker):
        total_content, total_recipient = super().compute_cost(scheduler, taskManager, tracker)