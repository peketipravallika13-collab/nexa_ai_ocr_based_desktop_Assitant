"""
Email Plugin for Nexa AI
------------------------
Allows drafting and sending emails, formatting communication from captured screens,
and launching the default desktop email client (Outlook, Thunderbird, Mail, or webmail).
"""

import os
import sys
import urllib.parse
import webbrowser
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger("email_plugin")

PLUGIN_SCHEMA = {
    "name": "email_manager",
    "description": "Draft or send an email, compose messages from screen content, or open the email client with pre-filled recipients, subject, and body.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'draft' (opens default email client with pre-filled fields) or 'send_smtp' (sends directly via SMTP if configured) or 'format_email' (formats an email text)."
            },
            "to_email": {
                "type": "STRING",
                "description": "Recipient email address (e.g. 'client@example.com' or 'team@company.com')."
            },
            "subject": {
                "type": "STRING",
                "description": "Email subject line."
            },
            "body": {
                "type": "STRING",
                "description": "Body content of the email."
            },
            "cc": {
                "type": "STRING",
                "description": "Optional CC email address."
            }
        },
        "required": ["action", "subject", "body"]
    }
}

def run(action: str = "draft", to_email: str = "", subject: str = "", body: str = "", cc: str = "") -> str:
    """Execute email drafting or sending."""
    action = action.lower().strip()
    
    if action in ("draft", "open", "compose"):
        # Construct mailto URI
        params = {}
        if subject:
            params["subject"] = subject
        if body:
            params["body"] = body
        if cc:
            params["cc"] = cc
            
        query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        mailto_url = f"mailto:{to_email.strip()}?{query_string}" if to_email else f"mailto:?{query_string}"
        
        try:
            webbrowser.open(mailto_url)
            return (
                f"📧 **Email Draft Created!**\n\n"
                f"- **To:** {to_email or '[Recipient to be filled]'}\n"
                f"- **Subject:** {subject}\n"
                f"- **Body Preview:**\n```text\n{body[:300]}{'...' if len(body) > 300 else ''}\n```\n\n"
                f"Opened draft in your default email client."
            )
        except Exception as e:
            return f"Error launching email client: {str(e)}"
            
    elif action == "format_email":
        return (
            f"📨 **Formatted Email Ready:**\n\n"
            f"**To:** {to_email or '[Recipient]'}\n"
            f"**Subject:** {subject}\n\n"
            f"---\n"
            f"{body}\n"
            f"---\n"
            f"*Tip: Ask Nexa to open this in your email client to send it!*"
        )
        
    elif action == "send_smtp":
        # Check environment variables for optional headless SMTP sending
        smtp_server = os.getenv("NEXA_SMTP_SERVER")
        smtp_port = int(os.getenv("NEXA_SMTP_PORT", "587"))
        smtp_user = os.getenv("NEXA_SMTP_USER")
        smtp_pass = os.getenv("NEXA_SMTP_PASS")
        
        if not (smtp_server and smtp_user and smtp_pass):
            # Fallback to drafting in desktop email app
            return run(action="draft", to_email=to_email, subject=subject, body=body, cc=cc)
            
        try:
            msg = MIMEMultipart()
            msg["From"] = smtp_user
            msg["To"] = to_email
            msg["Subject"] = subject
            if cc:
                msg["Cc"] = cc
            msg.attach(MIMEText(body, "plain"))
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                recipients = [to_email] + ([cc] if cc else [])
                server.sendmail(smtp_user, recipients, msg.as_string())
                
            return f"✅ **Email Sent Successfully** to `{to_email}` with subject: *{subject}*"
        except Exception as e:
            logger.error(f"SMTP error: {e}")
            return f"Failed to send via SMTP: {str(e)}. (Fallback to drafting instead)"
    else:
        return f"Unknown email action '{action}'. Use 'draft' or 'format_email'."
