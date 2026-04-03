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


def send_task_email(task: dict, assignment: dict | None = None):
    """
    Send the task email when a task is assigned.
    If an assignment dict is provided, appends the unique assignment URL
    (https://<site_url>/a/<assignment_id>) to the email body.
    """
    html_content = (task.get("email_text") or "").strip()
    if not html_content:
        logger.info("Task %s has no email_text; skipping task email", task.get("task_id"))
        return {"sent": False, "reason": "no_email_text"}

    if assignment:
        site_url = (task.get("site_url") or "").strip()
        assignment_id = assignment["assignment_id"]
        if site_url:
            assignment_url = f"https://{site_url}/a/{assignment_id}"
            html_content += (
                f'\n<p><a href="{assignment_url}" '
                f'style="color:#1a73e8;text-decoration:underline;">'
                f"Open task</a></p>"
            )

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
