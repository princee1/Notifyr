DELETE FROM contacts.Reason;

INSERT INTO
    emails.EmailAnalytics (
        analytics_id,
        week_start_date,
        emails_sent,
        emails_delivered,
        emails_opened,
        emails_bounced,
        emails_replied
    )
DEFAULT VALUES;
