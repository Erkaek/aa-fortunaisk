# Celery Configuration for FortunaIsk

## Overview

FortunaIsk uses Celery to schedule and run background tasks such as:

- Checking lotteries that have ended (`check_lotteries`)
- Processing wallet entries (`process_wallet_tickets`)
- Automatically creating lotteries from `AutoLottery` (`create_lottery_from_auto`)

## Requirements

1. **Redis** or another broker is required to run Celery.
1. Install Celery in your environment:
   pip install celery

## Running Celery

1. Start Celery worker:
   celery -A allianceauth worker -l info

1. Periodic tasks are scheduled using `django-celery-beat`. Run:
   python manage.py migrate django_celery_beat

1. Make sure the tasks (`check_lotteries`, `process_wallet_tickets`, etc.) are set up.\
   python manage.py setup_tasks

1. You should see the tasks in the Django admin under **Periodic Tasks**.
