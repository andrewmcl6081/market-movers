import os
import pytest
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

@pytest.mark.skipif(
  not os.getenv("SENDGRID_API_KEY"),
  reason="SENDGRID_API_KEY not set in environment"
)
def test_sendgrid_email_success():
  api_key = os.getenv("SENDGRID_API_KEY")
  sender = os.getenv("EMAIL_FROM")
  recipient = os.getenv("EMAIL_RECIPIENTS")
  
  assert api_key, "SENDGRID_API_KEY is missing"
  assert sender, "EMAIL_FROM is missing"
  assert recipient, "EMAIL_RECIPIENT is missing"
  
  message = Mail(
    from_email=sender,
    to_emails=recipient,
    subject="SendGrid Test Email",
    html_content="<strong>This is a test</strong>"
  )
  
  try:
    sg = SendGridAPIClient(api_key)
    response = sg.send(message)
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Body: {response.body}")
    print(f"Headers: {response.headers}")
    
    assert response.status_code in (200, 202), "Email failed to send"
  except Exception as e:
    pytest.fail(f"SendGrid API call failed: {e}")