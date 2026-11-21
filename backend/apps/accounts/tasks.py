"""Outgoing account e-mails (Celery)."""

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


@shared_task(name="accounts.send_invitation", autoretry_for=(OSError,), max_retries=3)
def send_invitation(
    email: str, first_name: str, company: str, username: str, link: str, expires: str
) -> None:
    """EF-09: the agent opens the link on their phone and chooses a password."""
    send_mail(
        f"{company} — activez votre accès PointQR",
        (
            f"Bonjour {first_name},\n\n"
            f"{company} utilise PointQR pour le pointage. Pour activer votre accès, ouvrez ce "
            f"lien sur votre téléphone et choisissez votre mot de passe :\n\n{link}\n\n"
            f"Votre identifiant : {username}\n"
            f"Ce lien est personnel et valable jusqu'au {expires}.\n\n"
            "Au premier pointage, votre téléphone sera lié à votre compte.\n\n— PointQR"
        ),
        settings.DEFAULT_FROM_EMAIL,
        [email],
    )
