# FortunaISK (Beta)

A lottery module for [Alliance Auth](https://allianceauth.org/) to organize, manage, and track community lotteries effortlessly. This module integrates seamlessly with Alliance Auth and its ecosystem, automating lottery creation, management, and winner selection.

______________________________________________________________________

## Feedback Welcome

**This module is currently in beta testing.** Your feedback, ideas for improvements, and suggestions are highly valued. Feel free to reach out with any insights or recommendations!

______________________________________________________________________

## Features

- **Ticket Handling**: Accepts and validates ticket purchases.
- **Payment Processing**: Automates payment verification and tracks anomalies.
- **Winner Selection**: Randomly selects winners using pre-defined criteria.
- **Lottery History**: Provides a detailed history of past lotteries and winners.
- **Recurring Lotteries**: Supports automated creation of recurring lotteries.
- **Administrative Tools**:
  - Anomaly resolution for mismatched transactions.
  - Prize distribution tracking.
  - Comprehensive admin dashboard for statistics and management.
- **Notifications**:
  - Discord notifications for major events like lottery completion or anomalies.
  - Alliance Auth notifications for users about ticket status and winnings.

______________________________________________________________________

## Prerequisites

- [Alliance Auth](https://allianceauth.readthedocs.io/en/v4.5.0/)
- [Alliance Auth Corp Tools](https://github.com/pvyParts/allianceauth-corp-tools)
- Django Celery and Django Celery Beat for task scheduling.

______________________________________________________________________

## Installation

### Step 1 - Install app

```bash
pip install fortunaisk
```

### Step 2 - Configure Auth settings

Add `'fortunaisk'` to your `INSTALLED_APPS` in `local.py`:

```python
INSTALLED_APPS += ["fortunaisk"]
```

### Step 3 - Maintain Alliance Auth

- Run migrations:

  ```bash
  python manage.py migrate
  ```

- Gather static files:

  ```bash
  python manage.py collectstatic
  ```

- Restart Auth:

  ```bash
  supervisorctl restart all
  ```

### Step 4 - Configure tasks

Run the following management command to set up periodic tasks:

```bash
python manage.py setup_fortuna_tasks
```

### Step 5 - Configure Webhooks

Visit the following URL to configure Discord webhooks:

```
AUTH_ADDRESS/admin/fortunaisk/webhookconfiguration/
```

______________________________________________________________________

## Permissions

| **Permission**     | **Description**                                                                |
| ------------------ | ------------------------------------------------------------------------------ |
| `fortunaisk.user`  | Allows access to the user's personal dashboard and viewing their winnings.     |
| `fortunaisk.admin` | Grants full administrative rights to manage lotteries, resolve anomalies, etc. |

______________________________________________________________________

## Settings

| **Name**                             | **Description**                              | **Default** |
| ------------------------------------ | -------------------------------------------- | ----------- |
| `FORTUNAISK_PAYMENT_VALIDATION_TASK` | Priority level for payment validation tasks. | 1           |
| `FORTUNAISK_DISCORD_NOTIFICATION`    | Priority level for Discord notifications.    | 5           |

______________________________________________________________________

## Architecture Overview

### Models

- **Lottery**: Core model representing individual lotteries, including ticket price, duration, and winner details.
- **AutoLottery**: Handles recurring lotteries with customizable schedules and durations.
- **TicketPurchase**: Tracks individual ticket purchases and their status.
- **Winner**: Records winners and their prize amounts.
- **TicketAnomaly**: Logs discrepancies in ticket purchases or payments.
- **ProcessedPayment**: Maintains a record of processed payments to prevent duplicates.
- **WebhookConfiguration**: Stores Discord webhook URLs for notifications.

### Tasks

- `check_purchased_tickets`: Validates payments and generates corresponding tickets.
- `check_lottery_status`: Monitors lotteries and marks them as completed if their duration has expired.
- `finalize_lottery`: Selects winners and completes the lottery lifecycle.
- `create_lottery_from_auto_lottery`: Automatically generates a new lottery based on recurring settings.

### Forms

- **LotteryCreateForm**: For creating standard one-time lotteries.
- **AutoLotteryForm**: For managing recurring lotteries with custom schedules and winner distributions.

### Views and Templates

- **Admin Dashboard**: Central hub for managing lotteries, resolving anomalies, and distributing prizes.
- **User Dashboard**: Personalized view for users to track their tickets and winnings.
- **Templates**:
  - `fortunaisk/base.html`: Base template providing consistent layout and navigation.
  - **Admin Views**:
    - `admin_dashboard.html`: Summarizes financial statistics, ongoing lotteries, and unresolved anomalies.
    - `anomalies_list.html`: Lists all anomalies for resolution.
    - `lottery_detail.html`: Displays details of a specific lottery, including participants and winners.
  - **User Views**:
    - `my_dashboard.html`: Displays a user's ticket purchases and winnings.
    - `lottery.html`: Shows active lotteries with participation details.
  - **Lottery Management**:
    - `create_lottery.html`: Form for creating one-time lotteries.
    - `create_auto_lottery.html`: Form for setting up recurring lotteries.
  - **Historical Data**:
    - `lottery_history.html`: Displays records of past lotteries.
    - `winner_list.html`: Lists all winners with a podium for top earners.

______________________________________________________________________

## Usage

### User Features

- **Active Lotteries**: Users can view and participate in ongoing lotteries.
- **Personal Dashboard**: View purchased tickets and winnings.
- **Lottery History**: Access records of past lotteries and their outcomes.

### Admin Features

- **Create Lotteries**: Set ticket prices, duration, winner count, and prize distribution.
- **Manage Recurring Lotteries**: Activate or deactivate automated lotteries.
- **Monitor Participants**: View ticket purchases and participant details.
- **Resolve Anomalies**: Identify and correct mismatches in ticket purchases or payments.

______________________________________________________________________

## Contributing

Contributions are welcome! To report an issue or propose a feature:

1. Fork this repository.

1. Create a branch for your feature or fix:

   ```bash
   git checkout -b feature/your-feature-name
   ```

1. Submit a pull request.

______________________________________________________________________

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

______________________________________________________________________

Thank you for using **FortunaISK**! For questions or feedback, feel free to open an issue or contact the maintainer.
