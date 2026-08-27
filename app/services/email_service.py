from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings


async def send_application_received_email(
    candidate_email: str, candidate_name: str | None, job_title: str
):
    """
    Send an email to the candidate confirming that their application has been received.
    """
    name = candidate_name if candidate_name else "Candidate"
    message = EmailMessage()

    message["From"] = settings.EMAIL_FROM
    message["To"] = candidate_email
    message["Subject"] = f"Application Received for {job_title}"

    message.set_content(f"""

        Dear {name},

        Thank you for applying for the position of {job_title}. We have received your application and our team will review it shortly.

        Our  recruitment team will review your application and contact you if your profile is shortlisted for the next stage of the hiring process.

        If you have any questions or concerns, please don't hesitate to reach out to us.
        We appreciate your interest in joining our company and will be in touch with you regarding the next steps in the hiring process.

        Best regards,
        The Hiring Team
        """)

    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USERNAME,
        password=settings.SMTP_PASSWORD,
        start_tls=True,
    )

    print(f"Application received email sent to {candidate_email} for {job_title}.")
