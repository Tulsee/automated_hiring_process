from email.message import EmailMessage
import logging

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_email(recipient: str, subject: str, body: str):
    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM
    message["To"] = recipient
    message["Subject"] = subject

    message.set_content(body)
    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USERNAME,
        password=settings.SMTP_PASSWORD,
        start_tls=True,
    )


async def send_application_received_email(
    candidate_email: str, candidate_name: str | None, job_title: str
):
    """
    Send an email to the candidate confirming that their application has been received.
    """
    name = candidate_name if candidate_name else "Candidate"
    await send_email(
        recipient=candidate_email,
        subject=f"Application Received for {job_title}",
        body=f"""Dear {name},

            Thank you for applying for the {job_title} position.

            We have successfully received your application and resume.

            Our recruitment team will review your application and contact you if your profile is shortlisted for the next stage.

            Thank you for your interest.

            Best regards,
            Recruitment Team
            """,
    )

    logger.info(
        f"Application received email sent to {candidate_email} for {job_title}."
    )


async def send_rejection_email(
    candidate_email: str, candidate_name: str | None, job_title: str
):
    name = candidate_name or "Candidate"

    await send_email(
        recipient=candidate_email,
        subject=f"Application Update - {job_title}",
        body=f"""Dear {name},

            Thank you for your interest in the {job_title} position and for taking the time to apply.

            After reviewing your application, we will not be moving forward with your application for this position at this time.

            We appreciate your interest and wish you success in your future opportunities.

            Best regards,
            Recruitment Team
            """,
    )

    logger.info(f"Rejection email sent to {candidate_email} for {job_title}.")


async def send_interview_invitation_email(
    candidate_email: str, candidate_name: str | None, job_title: str
):
    name = candidate_name or "Candidate"

    await send_email(
        recipient=candidate_email,
        subject=f"Interview Invitation - {job_title}",
        body=f"""Dear {name},

            Thank you for applying for the {job_title} position.

            We are pleased to inform you that your application has passed our initial screening, and we would like to invite you to the next stage of the recruitment process.

            Our recruitment team will contact you with the interview details and schedule.

            We look forward to speaking with you.

            Best regards,
            Recruitment Team
            """,
    )

    logger.info(
        f"Interview invitation email sent to {candidate_email} for {job_title}."
    )
