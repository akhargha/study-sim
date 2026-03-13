import logging

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from config import SENDGRID_API_KEY, EMAIL_TO, DEFAULT_FROM_EMAIL

logger = logging.getLogger("study_backend")


def send_email(from_email: str, to_email: str, subject: str, html_content: str):
    if not SENDGRID_API_KEY:
        raise ValueError("SENDGRID_API_KEY is not set")

    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=subject,
        html_content=html_content,
    )

    sg = SendGridAPIClient(SENDGRID_API_KEY)
    response = sg.send(message)

    logger.info(
        "SendGrid send status=%s from=%s to=%s subject=%s",
        response.status_code,
        from_email,
        to_email,
        subject,
    )

    return response.status_code


def send_task_email(task: dict):
    """
    Send the task email when a task is assigned.
    From: task.email if present, else DEFAULT_FROM_EMAIL
    To: EMAIL_TO
    Body: task.email_text
    Subject: task.task_name (or fallback)
    """
    html_content = (task.get("email_text") or "").strip()
    if not html_content:
        logger.info("Task %s has no email_text; skipping task email", task.get("task_id"))
        return {"sent": False, "reason": "no_email_text"}

    from_email = (task.get("email") or "").strip() or DEFAULT_FROM_EMAIL
    subject = (task.get("task_name") or "New study task").strip() or "New study task"

    status_code = send_email(
        from_email=from_email,
        to_email=EMAIL_TO,
        subject=subject,
        html_content=html_content,
    )

    return {
        "sent": True,
        "status_code": status_code,
        "from_email": from_email,
        "to_email": EMAIL_TO,
        "subject": subject,
    }


def send_stage_complete_email(stage: str):
    """
    Send a stage-complete message to EMAIL_TO.
    """
    subject = f"{stage} complete — contact admin"
    html_content = f"""
    <html>
      <body>
        <p>The stage <strong>{stage}</strong> has been completed.</p>
        <p>Please contact the admin before continuing to the next stage.</p>
      </body>
    </html>
    """

    status_code = send_email(
        from_email=DEFAULT_FROM_EMAIL,
        to_email=EMAIL_TO,
        subject=subject,
        html_content=html_content,
    )

    return {
        "sent": True,
        "status_code": status_code,
        "from_email": DEFAULT_FROM_EMAIL,
        "to_email": EMAIL_TO,
        "subject": subject,
    }
