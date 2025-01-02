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

## Future Developments

- **Compatibility with Memberaudit and CorpTools**: Provide support for both Memberaudit and CorpTools, allowing users to integrate **FortunaISK** with either member management tool based on their preference.

- **Bulk Ticket Purchases**: Enable users to purchase multiple tickets in a single transaction, streamlining the purchasing process and improving user experience.

- **Prized Lotteries**: Enhance the current lottery system by allowing administrators to offer tangible prizes instead of solely distributing the total ticket revenue. This will provide more diverse reward options and increase participant engagement.

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

### Step 3 - Maintain Alliance Auth

- Run migrations:

  ```bash
  python manage.py makemigrations
  python manage.py migrate
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

| **Permission**                   | **Description**                                                                |
| -------------------------------- | ------------------------------------------------------------------------------ |
| `fortunaisk.can_access_this_app` | Allows access to the user's personal dashboard and viewing their winnings.     |
| `fortunaisk.can_admin_this_app`  | Grants full administrative rights to manage lotteries, resolve anomalies, etc. |

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

## Update

### Step 1 - Update app

```bash
pip install -U fortunaisk
```

### Step 2 - Maintain Alliance Auth

- Run migrations:

  ```bash
  python manage.py makemigrations
  python manage.py migrate
  ```

- Restart Auth:

  ```bash
  supervisorctl restart all
  ```

______________________________________________________________________

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

______________________________________________________________________

Thank you for using **FortunaISK**! For questions or feedback, feel free to open an issue or contact the maintainer.
