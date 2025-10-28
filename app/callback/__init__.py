from app.callback.process_sub import Process_Sub
from .event_stream import Events_Stream
from .retry_stream import Retry_Stream
from .track_stream import Tracking_Stream
from .g_state_sub import G_State_Subs
from .webhook_stream import Webhook_Stream


Callbacks_Stream = {
    **Events_Stream,
    **Retry_Stream,
    **Tracking_Stream
    **Webhook_Stream
}

Callbacks_Sub = {
    **G_State_Subs,
    **Process_Sub,  
}
