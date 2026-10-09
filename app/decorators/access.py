from app.classes.auth_permission import AccessAPIInfo, AccessDoesNotExistsError
from app.definition._utils_decorator import Access


class AdminModificationAccess(Access):
    def __init__(self):
        super().__init__()
    
    def access(self,access:str,accessInfo:AccessAPIInfo):
        if access == 'system':
            raise AccessDoesNotExistsError(access)
        if access == 'admin' and accessInfo['type'] != 'System':
            raise AccessDoesNotExistsError(access)
        return True
        