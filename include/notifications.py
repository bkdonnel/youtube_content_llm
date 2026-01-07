#!/usr/bin/env python3
"""
Notification System
Send alerts via email, Slack, Discord, or webhook
"""

import os
import requests
from typing import Dict, Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


# Pydantic Models
class NotificationConfig(BaseModel):
    slack_webhook: Optional[str] = None
    discord_webhook: Optional[str] = None
    smtp_server: Optional[str] = None
    smtp_port: int = 587
    sender_email: Optional[str] = None
    sender_password: Optional[str] = None
    recipient_email: Optional[str] = None


class VideoInfo(BaseModel):
    creator: str
    title: str
    id: str
    url: str
    duration: float


class ErrorInfo(BaseModel):
    creator: str
    video_title: str
    video_id: str
    error: str
    occurred_at: Optional[str] = None


class SummaryInfo(BaseModel):
    new_videos: int = 0
    total_videos: int = 0
    rag_integrated: int = 0
    pending: int = 0
    errors: int = 0
    by_creator: Dict[str, int] = {}


# Configuration utilities
def load_notification_config() -> NotificationConfig:
    """Load notification configuration from environment variables."""
    return NotificationConfig(
        slack_webhook=os.getenv("SLACK_WEBHOOK_URL"),
        discord_webhook=os.getenv("DISCORD_WEBHOOK_URL"),
        smtp_server=os.getenv("SMTP_SERVER"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        sender_email=os.getenv("SENDER_EMAIL"),
        sender_password=os.getenv("SENDER_PASSWORD"),
        recipient_email=os.getenv("RECIPIENT_EMAIL")
    )


def format_creator_stats(by_creator: Dict[str, int]) -> str:
    """Format creator statistics for notification."""
    if not by_creator:
        return "  (No data)"

    lines = []
    for creator, count in by_creator.items():
        lines.append(f"  • {creator}: {count} videos")
    return "\n".join(lines)


# Notification senders
def send_slack_notification(webhook_url: str, title: str, message: str) -> bool:
    """Send Slack notification."""
    try:
        payload = {
            "text": f"*{title}*\n```{message}```"
        }
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        print(f"✅ Slack notification sent: {title}")
        return True
    except Exception as e:
        print(f"⚠️  Failed to send Slack notification: {e}")
        return False


def send_discord_notification(webhook_url: str, title: str, message: str) -> bool:
    """Send Discord notification."""
    try:
        payload = {
            "content": f"**{title}**\n```{message}```"
        }
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        print(f"✅ Discord notification sent: {title}")
        return True
    except Exception as e:
        print(f"⚠️  Failed to send Discord notification: {e}")
        return False


def send_email_notification(
    config: NotificationConfig,
    title: str,
    message: str
) -> bool:
    """Send email notification."""
    if not all([config.smtp_server, config.sender_email,
                config.sender_password, config.recipient_email]):
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = config.sender_email
        msg['To'] = config.recipient_email
        msg['Subject'] = title

        msg.attach(MIMEText(message, 'plain'))

        with smtplib.SMTP(config.smtp_server, config.smtp_port) as server:
            server.starttls()
            server.login(config.sender_email, config.sender_password)
            server.send_message(msg)

        print(f"✅ Email notification sent: {title}")
        return True
    except Exception as e:
        print(f"⚠️  Failed to send email notification: {e}")
        return False


def send_notification_to_all_channels(
    title: str,
    message: str,
    config: Optional[NotificationConfig] = None
) -> None:
    """Send notification via all configured channels."""
    if not config:
        config = load_notification_config()

    if config.slack_webhook:
        send_slack_notification(config.slack_webhook, title, message)

    if config.discord_webhook:
        send_discord_notification(config.discord_webhook, title, message)

    if all([config.smtp_server, config.sender_email,
            config.sender_password, config.recipient_email]):
        send_email_notification(config, title, message)


# Notification composers
def notify_new_video(video_info: VideoInfo) -> None:
    """Send notification about a new video being processed."""
    title = "🎬 New Music Production Tutorial Processed"
    message = f"""
New music production tutorial added to database:

Creator: {video_info.creator}
Title: {video_info.title}
Video ID: {video_info.id}
URL: {video_info.url}
Duration: {video_info.duration / 60:.1f} minutes
Processed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

You can now search for content from this video in the RAG system!
"""
    send_notification_to_all_channels(title, message)


def notify_error(error_info: ErrorInfo) -> None:
    """Send notification about a processing error."""
    title = "❌ Pipeline Error"
    occurred_at = error_info.occurred_at or datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    message = f"""
Error occurred during video processing:

Creator: {error_info.creator}
Video: {error_info.video_title}
Video ID: {error_info.video_id}
Error: {error_info.error}
Occurred: {occurred_at}

Please check the logs for more details.
"""
    send_notification_to_all_channels(title, message)


def notify_summary(summary: SummaryInfo) -> None:
    """Send daily/weekly summary notification."""
    title = "📊 Pipeline Summary Report"
    message = f"""
Pipeline Summary Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

New videos processed: {summary.new_videos}
Total in database: {summary.total_videos}
RAG integrated: {summary.rag_integrated}
Pending integration: {summary.pending}
Errors: {summary.errors}

By Creator:
{format_creator_stats(summary.by_creator)}
"""
    send_notification_to_all_channels(title, message)


# Example usage
if __name__ == "__main__":
    # Test new video notification
    notify_new_video(VideoInfo(
        creator='In The Mix',
        title='How to Sidechain in FL Studio',
        id='test123',
        url='https://youtube.com/watch?v=test123',
        duration=720
    ))
