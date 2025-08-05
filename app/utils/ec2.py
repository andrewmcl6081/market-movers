import boto3
import requests
import threading
import time
import logging

logger = logging.getLogger(__name__)

def terminate_self(region: str):
  try:
    instance_id = requests.get("http://169.254.169.254/latest/meta-data/instance-id", timeout=2).text
    ec2 = boto3.client("ec2", region_name=region)
    ec2.terminate_instances(InstanceIds=[instance_id])
    logger.info(f"Termination command sent for instance: {instance_id}")
  except Exception:
    logger.exception("Failed to self terminate EC2 instance")

def delayed_termination(region: str, delay: int = 30):
  def terminate_later():
    logger.info(f"Waiting {delay} seconds before terminating instance...")
    time.sleep(delay)
    terminate_self(region)
  threading.Thread(target=terminate_later, daemon=True).start()