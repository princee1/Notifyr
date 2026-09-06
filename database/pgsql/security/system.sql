SET search_path = system;

CREATE TABLE IF NOT EXISTS Notifications (
    notification_id UUID DEFAULT public.uuid_generate_v1mc (),
    PRIMARY KEY (notification_id)
);

CREATE TABLE IF NOT EXISTS Notes (
    note_id UUID DEFAULT public.uuid_generate_v1mc (),
    PRIMARY KEY (note_id)
);