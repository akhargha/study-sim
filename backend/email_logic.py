import logging
import re

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


def replace_site_href_with_assignment_url(html: str, site_url: str, assignment_url: str) -> str:
    """
    Replace href="https://site_url" or href="http://site_url" (with optional trailing slash)
    with the assignment-specific URL.
    """
    pattern = rf'href\s*=\s*["\']https?://{re.escape(site_url)}/?["\']'
    replacement = f'href="{assignment_url}"'
    return re.sub(pattern, replacement, html, flags=re.IGNORECASE)


def send_task_email(task: dict, assignment: dict | None = None):
    """
    Send the task email when a task is assigned.
    If an assignment dict is provided, replaces existing site links in the email
    with the assignment-specific URL (https://<site_url>/a/<assignment_id>).
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
            html_content = replace_site_href_with_assignment_url(
                html_content, site_url, assignment_url
            )
            logger.info(
                "Replaced href for site_url=%s with assignment_url=%s",
                site_url, assignment_url,
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
