# Celery Configuration for FortunaIsk

## Overview

FortunaIsk uses Celery to schedule and run background tasks such as:
- Checking lotteries that have ended (`check_lotteries`)
- Processing wallet entries (`process_wallet_tickets`)
- Automatically creating lotteries from `AutoLottery` (`create_lottery_from_auto`)

## Requirements

1. **Redis** or another broker is required to run Celery.
2. Install Celery in your environment:
   ```bash
   pip install celery