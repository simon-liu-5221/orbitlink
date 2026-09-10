"""Outbound email with a pluggable backend (decision A1).

Default backend writes the message to the application log — no SMTP server, no
provider account, works in CI. Set ``EMAIL_BACKEND=smtp`` to talk to MailHog
locally (``docker compose up mailhog``, inbox at http://localhost:8025) or to a
real provider in production.
"""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    body: str


class EmailBackend(Protocol):
    def send(self, message: Message) -> None: ...


class LogEmailBackend:
    """Logs the message instead of sending it. The default."""

    def __init__(self, sender: str) -> None:
        self._sender = sender

    def send(self, message: Message) -> None:
        logger.info(
            "email (not actually sent) from=%s to=%s subject=%s\n%s",
            self._sender,
            message.to,
            message.subject,
            message.body,
        )


class SmtpEmailBackend:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, message: Message) -> None:
        settings = self._settings
        email = EmailMessage()
        email["From"] = settings.email_from
        email["To"] = message.to
        email["Subject"] = message.subject
        email.set_content(message.body)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(email)


def build_email_backend(settings: Settings) -> EmailBackend:
    if settings.email_backend == "smtp":
        return SmtpEmailBackend(settings)
    return LogEmailBackend(settings.email_from)


# --- the messages we actually send ------------------------------------


def verification_message(*, to: str, username: str, link: str, hours: int) -> Message:
    return Message(
        to=to,
        subject="Confirm your OrbitLink email",
        body=(
            f"Hi {username},\n\n"
            "Confirm your email address to finish setting up your OrbitLink account:\n\n"
            f"{link}\n\n"
            f"The link works for {hours} hours. If you didn't sign up, ignore this email.\n"
        ),
    )


def already_registered_message(*, to: str) -> Message:
    """Sent instead of a verification email when the address already has an
    account — so the API's response is identical either way (GU-01 AC-3)."""
    return Message(
        to=to,
        subject="You already have an OrbitLink account",
        body=(
            "Someone tried to sign up with this email address, but it already has an "
            "OrbitLink account.\n\n"
            "If that was you, sign in instead — or reset your password if you've "
            "forgotten it. If it wasn't, you can ignore this email.\n"
        ),
    )


def password_reset_message(*, to: str, username: str, link: str, hours: int) -> Message:
    return Message(
        to=to,
        subject="Reset your OrbitLink password",
        body=(
            f"Hi {username},\n\n"
            "Someone asked to reset the password on your OrbitLink account. Follow "
            "this link to choose a new one:\n\n"
            f"{link}\n\n"
            f"The link works for {hours} hour(s) and can be used once. If you didn't "
            "ask for this, ignore this email — your password stays as it is.\n"
        ),
    )
