import logging
import sendgrid
from typing import List
from sqlalchemy.orm import Session
from datetime import date, datetime, timezone
from sendgrid.helpers.mail import Mail, Email, To, Content

from app.config import get_config
from app.db.models import UserSubscription

logger = logging.getLogger(__name__)

class EmailService:
  def __init__(self):
    self.config = get_config()
    self.sg_client = None
    
    if self.config.SENDGRID_API_KEY:
      self.sg_client = sendgrid.SendGridAPIClient(api_key=self.config.SENDGRID_API_KEY)
    else:
      logger.warning("SendGrid API key not configured. Email sending disabled")
  
  def get_active_recipients(self, db: Session) -> List[str]:
    """Get all active email recipients from database"""
    
    try:
      active_subs = db.query(UserSubscription).filter_by(send_daily_report=True).all()
      recipients = [sub.email for sub in active_subs]
      logger.info(f"Found {len(recipients)} active recipients")
      return recipients
    except Exception as e:
      logger.error(f"Error fetching recipients from database: {e}")
      return []
  
  def send_report(self, html_content: str, report_date: date, db: Session = None) -> bool:
    if not self.sg_client:
      logger.warning("Email client not configured")
      return False
    
    try:
      subject = f"Market Movers Daily Report - {report_date.strftime('%B %d, %Y')}"
      recipients = self.get_active_recipients(db)
      
      if not recipients:
        logger.warning("No active recipients found in database")
        return False
      
      success_count = 0
      failed_recipients = []
      
      for recipient_email in recipients:
        try:
          message = Mail(
            from_email=Email(self.config.EMAIL_FROM),
            to_emails=[To(recipient_email)],
            subject=subject,
            html_content=Content("text/html", html_content)
          )
          
          response = self.sg_client.send(message)
          
          if response.status_code in [200, 201, 202]:
            success_count += 1
            
            # Update last_email_sent for this subscriber
            subscriber = db.query(UserSubscription).filter_by(email=recipient_email).first()
            if subscriber:
              subscriber.last_email_sent = datetime.now(timezone.utc)
              subscriber.total_emails_sent = (subscriber.total_emails_sent or 0) + 1
          else:
            logger.error(f"Failed to send email to {recipient_email}. Status: {response.status_code}")
            failed_recipients.append(recipient_email)
        except Exception as e:
          logger.error(f"Error sending email to {recipient_email}: {e}")
          failed_recipients.append(recipient_email)
          
      db.commit()
      
      logger.info(f"Report emails sent: {success_count}/{len(recipients)} successful")
      if failed_recipients:
        logger.warning(f"Failed recipients: {', '.join(failed_recipients)}")
        
      return success_count > 0
    except Exception:
      logger.error("Error sending emails")
      return False

  def send_error_notification(self, error_message: str, report_date: date) -> bool:
    """Send error notification to admin email"""
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
      
      admin_email = self.config.ADMIN_EMAIL
      
      message = Mail(
        from_email=Email(self.config.EMAIL_FROM),
        to_emails=[To(admin_email)],
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