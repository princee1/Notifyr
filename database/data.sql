DELETE FROM contacts.Reason;

INSERT INTO
    contacts.Reason (
        reason_name,
        reason_description
    )
VALUES (
        'Not Interested',
        'The user is not interested in the content.'
    ),
    (
        'Too Many Emails',
        'The user is receiving too many emails.'
    ),
    (
        'Content Not Relevant',
        'The content is not relevant to the user.'
    ),
    (
        'Other',
        'Other reasons for unsubscribing.'
    ),
    (
        'Switched to Competitor',
        'The user has switched to a competitor.'
    ),
    (
        'Privacy Concerns',
        'The user has concerns about privacy.'
    ),
    (
        'Technical Issues',
        'The user is experiencing technical issues.'
    ),
    (
        'No Longer Needed',
        'The user no longer needs the service.'
    );

DELETE FROM security.Client;

DELETE FROM security.Groupclient;

INSERT INTO
    security.Client (
        client_name,
        client_type,
        client_description,
        client_scope,
        authenticated,
        can_login

    )
VALUES (
        'Notifyr ADMIN',
        'Admin',
        'Admin client for Notifyr application',
        'Free',
        True,
        True
    );


INSERT INTO
    security.Challenge (
        client_id,
        expired_at_auth,
        expired_at_refresh
    )
VALUES (
        (
            SELECT client_id
            FROM security.Client
            WHERE
                client_type = 'Admin'
        ),
        NOW() + INTERVAL '5 minute',
        NOW() + INTERVAL '1 hour'
    );

SELECT emails.create_daily_email_analytics_row();

INSERT INTO
    twilio.SMSAnalytics (
        analytics_id,
        week_start_date,
        direction,
        sms_sent,
        sms_delivered,
        sms_failed,
        total_price
    )
VALUES (
        DEFAULT,
        DATE_TRUNC('week', NOW()),
        'O',
        0,
        0,
        0,
        0
    ),
    (
        DEFAULT,
        DATE_TRUNC('week', CURRENT_DATE),
        'I',
        0,
        0,
        0,
        0
    );
