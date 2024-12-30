# FortunaISK

**FortunaISK** is a lottery module designed for Alliance Auth, enabling you to organize, manage, and track lottery participation and winners within your community. This module automates tedious tasks such as payments and verifications while providing an intuitive interface.

## Features

- **Admin Dashboard**: Provides an overview of global statistics, detected anomalies, and lottery management options.
- **Automatic or Manual Lottery Management**: Simplifies the creation and management of recurring or one-time lotteries.
- **Ticket Purchases**: Allows users to purchase tickets to participate in a lottery.
- **Automatic Payment Verification**: Integration with `allianceauth-corp-tools` for automatic payment validation.
- **Anomaly Management**: Identifies and facilitates the resolution of anomalies in transactions or participation.
- **Automatic Winner Selection**: Automatically selects winners at the end of each lottery based on predefined criteria.
- **Periodic Tasks**: Automates processes such as payment checks, status updates, and finalizing lotteries using Celery.
- **History Display**: Lists previous winners with details of prizes awarded.
- **User-Friendly Interface**: A clear interface to participate in and track ongoing or past lotteries.
- **Discord Integration**: Sends notifications via Discord webhooks.
- **Winner Leaderboard**: Highlights top winners with a podium based on their cumulative winnings.

## Installation

0. This app is built as a submodule of [CorpTools](https://github.com/pvyParts/allianceauth-corp-tools), so please install this first.

1. Install the app:

   ```bash
   pip install fortunaisk
   ```

1. Add `'fortunaisk',` to your `INSTALLED_APPS` in your project's `local.py`:

   ```python
   INSTALLED_APPS += ["fortunaisk"]
   ```

1. Run migrations, collect static files, and restart Auth:

   ```bash
   python manage.py migrate fortunaisk
   python manage.py collectstatic
   supervisorctl restart all
   ```

1. Navigate to the following address to set up default cron tasks:

   ```bash
   AUTH_ADDRESS/fortunaisk/admin_create_tasks/
   ```

1. Set up your permissions as documented below.

1. Add characters and corp tokens as required.

1. Optionally, set up update tasks if you want data to auto-update (see the Usage section).

## Usage

### Creating an Automatic Lottery

1. Go to the admin interface and click "Create Automatic Lottery."

1. Fill out the form with the following details:

   - **Lottery Name**: A unique name for the lottery.
   - **Frequency**: Set the recurrence (e.g., every month).
   - **Ticket Price**: Cost of each ticket in ISK.
   - **Duration**: Time period the lottery will remain open.
   - **Number of Winners**: Number of winners to be selected.
   - **Prize Distribution**: Allocate percentages to winners (total must be 100%).
   - **Max Tickets per User**: (Optional) Limit the number of tickets per user.
   - **Payment Receiver**: Select the corporation that will receive ticket payments.

1. Submit the form to save the configuration.

### Creating a Standard Lottery

1. Go to the admin interface and click "Create a New Lottery."

1. Fill out the form with details similar to an automatic lottery:

   - **Ticket Price**, **Duration**, **Number of Winners**, **Prize Distribution**, and **Max Tickets per User**.
   - **Payment Receiver** is also configurable.

1. Submit the form to launch the lottery.

### User Participation

- Users can browse active lotteries and view details such as ticket prices and total pots.
- Participation instructions (sending ISK via a specified corporation) are clearly displayed.
- Once payments are made, the module automatically verifies transactions and validates entries.

### Managing Winners

- The module automatically selects winners at the end of each lottery.
- Winners and their prizes are displayed in the history.
- A dedicated interface allows admins to distribute prizes and mark winners as "rewarded."

### Resolving Anomalies

1. Access the admin dashboard and click "Total Anomalies."
1. Review listed anomalies, including transaction details.
1. Use the "Resolve" button to mark anomalies as resolved.

### Lottery History

- Displays past lotteries, including details on tickets sold, participants, and total pots.
- Winners are listed with their respective rewards.

## Permissions

The following table outlines the permissions available in **FortunaISK** and the corresponding actions they enable:

| **Permission**                 | **Description**                                                                      |
| ------------------------------ | ------------------------------------------------------------------------------------ |
| `fortunaisk.admin`             | Grants access to the admin dashboard for managing lotteries, anomalies, and winners. |
| `fortunaisk.create_lottery`    | Allows creating new standard or automatic lotteries.                                 |
| `fortunaisk.edit_lottery`      | Allows editing the details of existing lotteries.                                    |
| `fortunaisk.terminate_lottery` | Enables termination of active lotteries prematurely.                                 |
| `fortunaisk.resolve_anomaly`   | Allows resolving detected anomalies.                                                 |
| `fortunaisk.distribute_prize`  | Permits marking prizes as distributed to winners.                                    |

Ensure the appropriate permissions are assigned to users or groups to provide controlled access to the module's features.

## Contributing

Contributions are welcome! To report an issue or propose a feature:

1. Fork this repository.

1. Create a branch for your feature or fix:

   ```bash
   git checkout -b feature/your-feature-name
   ```

1. Submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

______________________________________________________________________

Thank you for using **FortunaISK**! If you have any questions or feedback, feel free to open an issue or contact me directly.
