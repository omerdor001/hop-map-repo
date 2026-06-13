import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import config_manager

log = logging.getLogger(__name__)


def send_password_reset_email(to_email: str, reset_link: str) -> bool:
    """Send a password reset email. Returns True on success, False on failure."""
    cfg = config_manager.email
    if not cfg.enabled:
        log.warning(
            "Email service disabled — reset token not sent to %s. Link: %s",
            to_email, reset_link,
        )
        return False

    from_addr = cfg.from_address or cfg.smtp_user
    expiry = cfg.reset_token_expiry_minutes

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Reset your HopeMap password"
    msg["From"] = f"{cfg.from_name} <{from_addr}>"
    msg["To"] = to_email

    text_body = (
        f"Reset your HopeMap password\n\n"
        f"Click the link below to reset your password. "
        f"The link expires in {expiry} minutes.\n\n"
        f"{reset_link}\n\n"
        f"If you didn't request a password reset, you can ignore this email."
    )
    html_body = f"""<html><body style="font-family:sans-serif;color:#3a0e1e;max-width:480px;margin:auto">
  <h2 style="color:#d4537e">Reset your HopeMap password</h2>
  <p>Click the button below to reset your password.
     The link expires in <strong>{expiry} minutes</strong>.</p>
  <p>
    <a href="{reset_link}"
       style="display:inline-block;background:#d4537e;color:white;
              padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">
      Reset Password
    </a>
  </p>
  <p>Or copy this link: <a href="{reset_link}">{reset_link}</a></p>
  <hr style="border:none;border-top:1px solid #fce8f0;margin:24px 0">
  <p style="font-size:12px;color:#993556">
    If you didn't request a password reset, you can safely ignore this email.
  </p>
</body></html>"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        password = cfg.smtp_password.get_secret_value()
        if cfg.smtp_secure:
            with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port) as smtp:
                smtp.login(cfg.smtp_user, password)
                smtp.sendmail(from_addr, to_email, msg.as_string())
        else:
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(cfg.smtp_user, password)
                smtp.sendmail(from_addr, to_email, msg.as_string())
        log.info("Password reset email sent to %s", to_email)
        return True
    except Exception:
        log.exception("Failed to send password reset email to %s", to_email)
        return False
