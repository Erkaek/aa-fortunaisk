"""App Tasks"""

# Standard Library
import logging

# Third Party
from celery import shared_task

logger = logging.getLogger(__name__)

# Create your tasks here


# fortunaisk Task
@shared_task
def fortunaisk_task():
    """fortunaisk Task"""

    pass
