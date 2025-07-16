import logging
import sendgrid
from datetime import date
from config import get_config
from typing import List, Optional
from sendgrid.helpers.mail import Mail, Email, To, Content

logger = logging.getLogger(__name__)

class EmailService:
  def __init__(self):
    self.config = get_config()
    self.sg_client = None
    
    if self.config.SENDGRID_API_KEY:
      self.sg_client = sendgrid.SendGridAPIClient(api_key=self.config.SENDGRID_API_KEY)
    else:
      logger.warning("SendGrid API key not configured. Email sending disabled")
  
  def send_report(self, html_content: str, report_date: date) -> bool:
    if not self.sg_client:
      logger.warning("Email client not configured")
      return False

    if not self.config.EMAIL_RECIPIENTS:
      logger.warning("No email recipients configured")
      return False
    
    try:
      subject = f"Market Movers Daily Report - {report_date.strftime('%B %d, %Y')}"
      
      message = Mail(
        from_email=Email(self.config.EMAIL_FROM),
        to_emails=[To(self.config.EMAIL_RECIPIENTS)],
        subject=subject,
        html_content=Content("text/html", html_content)
      )
      
      response = self.sg_client.send(message)
      
      if response.status_code in [200, 201, 202]:
        logger.info(f"Report email sent successfully to {len(self.config.EMAIL_RECIPIENTS)} recipients")
        return True
      else:
        logger.error(f"Failed to send email. Status code: {response.status_code}")
        return False
    
    except Exception as e:
      logger.error(f"Error sending email: {e}")
      return False
  
  def send_error_notification(self, error_message: str, report_date: date) -> bool:
    if not self.sg_client:
      return False
    
    try:
      subject = f"[ERROR] Market Movers Report Generation Failed - {report_date}"
      
      html_content = f"""
      <html>
        <body>
          <h2>Report Generation Error</h2>
          <p>The daily market report generation failed for {report_date}.</p>
          <h3>Error Details:</h3>
          <pre style="background-color: #f5f5f5; padding: 10px; border-radius: 5px;">{error_message}</pre>
          <p>Please check the system logs for more details.</p>
        </body>
      </html>
      """
      
      message = Mail(
        from_email=Email(self.config.EMAIL_FROM),
        to_emails=[To(self.config.EMAIL_RECIPIENTS)],
        subject=subject,
        html_content=Content("text/html", html_content)
      )
      
      response = self.sg_client.send(message)
      
      if response.status_code in [200, 201, 202]:
        logger.info("Error notification sent successfully")
        return True
      else:
        logger.error(f"Failed to send error notification. Status code: {response.status_code}")
        return False
    
    except Exception as e:
      logger.error(f"Error sending error notification: {e}")
      return False