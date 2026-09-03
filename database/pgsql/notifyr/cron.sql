-- Active: 1740679093248@@127.0.0.1@5432@notifyr@cron

SELECT cron.schedule_in_database (
        'delete_expired_subscontent_every_5_min', '*/5 * * * *', 'SELECT contacts.delete_expired_subscontent();', 'notifyr'
    );

SELECT cron.schedule_in_database (
        'set_email_delivered_every_hour', '0 * * * *', 'SELECT emails.set_email_delivered();', 'notifyr'
    );

SELECT cron.schedule_in_database (
        'delete_expired_email_tracking_every_day', '0 0 * * *', 'SELECT emails.delete_expired_email_tracking();', 'notifyr'
    );

SELECT cron.schedule_in_database (
        'delete_non_mapped_email_event_every_day', '0 */3 * * *', 'SELECT emails.delete_non_mapped_email_event();', 'notifyr'
    );

SELECT cron.schedule_in_database (
        'create_daily_email_analytics_row', '0 0 * * *', 'SELECT emails.create_daily_email_analytics_row();', 'notifyr'
    );

SELECT cron.schedule_in_database (
        'delete_expired_links_every_day', '0 0 * * *', 'SELECT links.delete_expired_links();', 'notifyr'
    );

SELECT cron.schedule_in_database (
        'delete_expired_link_session_event_every_day', '0 0 * * *', 'SELECT links.delete_link_event_session();', 'notifyr'
    );

SELECT cron.schedule_in_database (
        'create_weekly_sms_analytics_row', '0 0 * * 0', 'SELECT twilio.create_weekly_sms_analytics_row();', 'notifyr'
    );

SELECT cron.schedule_in_database (
        'set_sms_delivered_every_hour', '0 * * * *', 'SELECT twilio.set_sms_delivered();', 'notifyr'
    );

SELECT cron.schedule_in_database (
        'set_call_completed_every_hour', '0 * * * *', 'SELECT twilio.set_call_completed();', 'notifyr'
    );

SELECT cron.schedule_in_database (
        'delete_expired_tracking_every_day', '0 0 * * *', 'SELECT twilio.delete_expired_tracking();', 'notifyr'
    );

SELECT cron.schedule_in_database (
        'delete_old_campaigns_every_day', '0 0 * * *', 'CALL campaigns.delete_old_campaigns();', 'notifyr'
    );
