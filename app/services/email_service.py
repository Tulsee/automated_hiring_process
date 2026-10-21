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
    candidate_email: str,
    candidate_name: str | None,
    job_title: str,
    interview_url: str | None = None,
    invite_expires_at=None,
):
    name = candidate_name or "Candidate"

    if interview_url:
        expiry_line = (
            f"This link expires on "
            f"{invite_expires_at:%d %b %Y %H:%M} UTC."
            if invite_expires_at
            else "This link will expire shortly, so please complete it soon."
        )

        next_steps = f"""Your interview is a short set of recorded video questions you can complete in your browser. Each question has its own time limit, shown on screen.

            Start your interview here:
            {interview_url}

            {expiry_line}"""
    else:
        next_steps = (
            "Our recruitment team will contact you with the "
            "interview details and schedule."
        )

    await send_email(
        recipient=candidate_email,
        subject=f"Interview Invitation - {job_title}",
        body=f"""Dear {name},

            Thank you for applying for the {job_title} position.

            We are pleased to inform you that your application has passed our initial screening, and we would like to invite you to the next stage of the recruitment process.

            {next_steps}

            We look forward to speaking with you.

            Best regards,
            Recruitment Team
            """,
    )

    logger.info(
        f"Interview invitation email sent to {candidate_email} for {job_title}."
    )


# --------------------------------------------------------------- final decision

def build_decision_email(
    decision: str, candidate_name: str | None, job_title: str
) -> tuple[str, str]:
    """The subject and body for a final, post-interview decision.

    Three outcomes, each with its own message: an offer, moving to a further
    round, or a decline. Returned as a draft so it can be printed or sent - the
    caller decides which.
    """
    name = candidate_name or "Candidate"

    if decision == "hired":
        subject = f"Great news about your application - {job_title}"
        body = f"""Dear {name},

            Thank you for taking the time to interview for the {job_title} position.

            We were impressed by your interview and are delighted to move forward with an offer. A member of our team will be in touch shortly with the details and next steps.

            Congratulations, and welcome.

            Best regards,
            Recruitment Team
            """
    elif decision == "next_round":
        subject = f"Next steps in your application - {job_title}"
        body = f"""Dear {name},

            Thank you for completing your interview for the {job_title} position.

            We enjoyed learning more about you and would like to invite you to the next stage of the process. A member of our team will reach out shortly to arrange it.

            We look forward to speaking with you again.

            Best regards,
            Recruitment Team
            """
    else:  # rejected / declined after interview
        subject = f"Update on your application - {job_title}"
        body = f"""Dear {name},

            Thank you for taking the time to interview for the {job_title} position.

            After careful consideration, we have decided not to move forward with your application at this time. This was a difficult decision, and we are grateful for the opportunity to have spoken with you.

            We wish you every success in your search.

            Best regards,
            Recruitment Team
            """

    return subject, body


async def send_decision_email(
    decision: str, candidate_email: str, candidate_name: str | None, job_title: str
):
    """Build the right decision email, log the draft, and send it.

    The draft is always logged (Module 18 begins with drafts printed to the
    console); sending is attempted on top, so a run without SMTP configured
    still shows exactly what would go out.
    """
    subject, body = build_decision_email(decision, candidate_name, job_title)

    logger.info(
        "Decision email draft (%s) for %s:\nSubject: %s\n%s",
        decision,
        candidate_email,
        subject,
        body,
    )

    await send_email(recipient=candidate_email, subject=subject, body=body)

    logger.info(
        "Decision email (%s) sent to %s for %s.",
        decision,
        candidate_email,
        job_title,
    )
