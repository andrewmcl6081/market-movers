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