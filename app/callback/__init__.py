from app.utils.globals import APP_MODE, ApplicationMode

Callbacks_Stream = {}
Callbacks_Sub = {}

if APP_MODE == ApplicationMode.server:
    from .process_sub import Process_Sub
    from .event_stream import Events_Stream
    from .track_stream import Tracking_Stream
    from .webhook_stream import Webhook_Stream
    from .error_stream import Profile_Error_Stream

    Callbacks_Sub.update(Process_Sub)
    Callbacks_Stream.update(Events_Stream)
    Callbacks_Stream.update(Tracking_Stream)
    Callbacks_Stream.update(Profile_Error_Stream)
    Callbacks_Stream.update(Webhook_Stream)


if APP_MODE == ApplicationMode or APP_MODE == ApplicationMode.agentic:
    from .g_state_sub import G_State_Subs

    Callbacks_Sub.update(G_State_Subs)


