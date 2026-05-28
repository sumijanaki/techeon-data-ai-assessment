import os
import smtplib
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from pathlib import Path
from config import (
    logger,
    SMTP_SERVER,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    ALERT_RECEIVER_EMAIL,
    ALERT_SENDER_EMAIL,
    MOCK_ALERTING,
    LOG_DIR
)

class AlerterError(Exception):
    """Base exception class for Alerter Service errors."""
    pass

class PipelineAlerter:
    """Service to deliver structured HTML exception notifications to developers if a job fails."""

    @staticmethod
    def generate_html_body(error_message: str, traceback_str: str) -> str:
        """
        Structures a highly readable, professional HTML failure alert template.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #f8f9fa;
                    color: #333333;
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    max-width: 650px;
                    background: #ffffff;
                    border: 1px solid #e1e4e8;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
                }}
                .header {{
                    background-color: #d9381e;
                    color: #ffffff;
                    padding: 20px;
                    font-size: 20px;
                    font-weight: bold;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                .content {{
                    padding: 24px;
                }}
                .meta-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                }}
                .meta-table td {{
                    padding: 8px 12px;
                    border-bottom: 1px solid #f1f2f4;
                }}
                .meta-table td.label {{
                    font-weight: 600;
                    color: #555555;
                    width: 30%;
                }}
                .error-detail {{
                    background-color: #fdf2f2;
                    border-left: 4px solid #de350b;
                    color: #ab1f1f;
                    padding: 16px;
                    font-size: 15px;
                    font-family: Consolas, Monaco, monospace;
                    border-radius: 4px;
                    margin-bottom: 20px;
                    word-break: break-word;
                }}
                .traceback-container {{
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    padding: 18px;
                    font-family: Consolas, Monaco, monospace;
                    font-size: 13px;
                    border-radius: 6px;
                    overflow-x: auto;
                    white-space: pre-wrap;
                    line-height: 1.5;
                }}
                .footer {{
                    background-color: #f1f2f4;
                    color: #666666;
                    padding: 15px 24px;
                    font-size: 12px;
                    text-align: center;
                    border-top: 1px solid #e1e4e8;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    ⚠️ Weather ETL Pipeline Failure Alert
                </div>
                <div class="content">
                    <p style="margin-top: 0; font-size: 16px;">
                        The scheduled Weather Marketing Ingestion pipeline encountered a critical error during execution. Action is required.
                    </p>
                    
                    <table class="meta-table">
                        <tr>
                            <td class="label">Pipeline Name:</td>
                            <td>Weather-Triggered Marketing Ingestion</td>
                        </tr>
                        <tr>
                            <td class="label">Failure Time:</td>
                            <td>{timestamp}</td>
                        </tr>
                        <tr>
                            <td class="label">Environment:</td>
                            <td>Production Sandbox</td>
                        </tr>
                    </table>
                    
                    <div class="label" style="margin-bottom: 8px; font-weight: bold;">Error Detail:</div>
                    <div class="error-detail">
                        {error_message}
                    </div>
                    
                    <div class="label" style="margin-bottom: 8px; font-weight: bold;">Traceback / Call Stack:</div>
                    <div class="traceback-container">{traceback_str}</div>
                </div>
                <div class="footer">
                    This is an automated notification. Please do not reply directly to this email.
                </div>
            </div>
        </body>
        </html>
        """
        return html

    @classmethod
    def send_alert_email(cls, error_message: str, traceback_str: str):
        """
        Delivers the error email alert via SMTP. Falls back to saving a local HTML log 
        if SMTP config is incomplete or if MOCK_ALERTING is enabled.
        """
        html_content = cls.generate_html_body(error_message, traceback_str)
        
        # Determine if we should mock the alert or send it via real SMTP
        use_mock = MOCK_ALERTING or not SMTP_USER or not SMTP_PASSWORD
        
        if use_mock:
            # Write to a mock file in logs folder
            mock_file_path = LOG_DIR / "failed_run_alert.html"
            try:
                with open(mock_file_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.warning(
                    f"MOCK ALERTING ENABLED/CREDENTIALS MISSING: Saved fallback alert HTML "
                    f"diagnostics block to disk: '{mock_file_path}'"
                )
                return
            except Exception as e:
                logger.critical(f"Backup alerter failed writing HTML disk fallback: {str(e)}")
                return

        # Attempt actual SMTP email transfer
        logger.info(f"Initiating SMTP connection to {SMTP_SERVER}:{SMTP_PORT} to send failure alert.")
        
        # Build the message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "🚨 CRITICAL: Weather ETL Pipeline Ingestion Failure"
        msg["From"] = ALERT_SENDER_EMAIL
        msg["To"] = ALERT_RECEIVER_EMAIL
        msg.attach(MIMEText(html_content, "html"))

        try:
            # Connect using standard starttls fallback support
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15) as server:
                server.ehlo()
                if SMTP_PORT == 587:
                    server.starttls()
                    server.ehlo()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(ALERT_SENDER_EMAIL, ALERT_RECEIVER_EMAIL, msg.as_string())
                logger.info(f"ETL Failure email alert successfully sent to {ALERT_RECEIVER_EMAIL}")
        except Exception as e:
            # Fallback to local logs on connection failures to prevent silencing primary stack trace
            backup_msg = (
                f"SMTP Alert sending failed: {str(e)}. "
                f"Original Exception: {error_message}"
            )
            logger.critical(backup_msg)
            
            # Save backup HTML to local disk log
            backup_file_path = LOG_DIR / "failed_run_alert_fallback.html"
            try:
                with open(backup_file_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.info(f"Stored backup diagnostics file at '{backup_file_path}'")
            except Exception as disk_err:
                logger.critical(f"Failed writing backup alert to disk: {str(disk_err)}")
