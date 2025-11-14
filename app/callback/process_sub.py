from app.classes.process import ProcessTerminateProtocol
from app.services import ConfigService, LoggerService
from app.utils.constant import SubConstant
from app.container import Get   


async def Process_Terminate(message: ProcessTerminateProtocol) -> None:
    configService = Get(ConfigService)
    loggerService = Get(LoggerService)


Process_Sub = {
    SubConstant.PROCESS_TERMINATE: Process_Terminate,
}