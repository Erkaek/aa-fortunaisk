# FortunaISK

A comprehensive lottery system for [Alliance Auth](https://allianceauth.org/) that brings excitement and community engagement to your corporation or alliance. Run fair, transparent lotteries with automated management and real-time tracking.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Django 4.0+](https://img.shields.io/badge/django-4.0+-blue.svg)](https://www.djangoproject.com/)

______________________________________________________________________

## ✨ Features

### 🎲 **Easy Lottery Participation**

- **Simple ISK Transfer System** - Just send money with the lottery reference in the reason
- **Real-time Ticket Tracking** - Monitor your purchases and remaining allowances
- **Personal Dashboard** - Complete history of tickets, winnings, and payments
- **Automatic Notifications** - Get notified instantly when you win

### 🏆 **Flexible Prize Distribution**

- **Multi-winner Support** - Configure multiple winners per lottery
- **Custom Prize Percentages** - Set exact prize distribution for each winner
- **Automated Calculations** - System handles all prize calculations automatically
- **Transparent Results** - Public winner announcements with full details

### ⚡ **Automated Management**

- **Recurring Lotteries** - Set up lotteries that run automatically on schedule
- **Smart Payment Processing** - Automated validation and anomaly detection
- **Lifecycle Management** - Automatic transitions from active to completed
- **24-hour Reminders** - Automated closure notifications

### 📊 **Administrative Excellence**

- **Rich Admin Dashboard** - Real-time statistics and system monitoring
- **Anomaly Resolution** - Advanced tools to handle payment discrepancies
- **Prize Distribution Tracking** - Monitor and confirm prize deliveries
- **Comprehensive Audit Trails** - Complete logging of all actions
- **CSV Export** - Export participant and winner data

### 🔔 **Discord Integration**

- **Rich Notifications** - Beautiful embeds for all lottery events
- **Winner Announcements** - Automatic celebration of lottery results
- **Admin Alerts** - Immediate notification of anomalies or issues
- **Customizable Webhooks** - Configure notifications for your community

______________________________________________________________________

## 📋 Requirements

- **Alliance Auth** v4.0+
- **[Alliance Auth Corp Tools](https://github.com/pvyParts/allianceauth-corp-tools)** - For wallet integration
- **[AA Discord Notify](https://apps.allianceauth.org/apps/detail/aa-discordnotify)** (Optional) - For Discord notifications

______________________________________________________________________

## 🚀 Installation

### Step 1 - Install the Package

```bash
pip install fortunaisk
```

### Step 2 - Configure Settings

Add the following to your Alliance Auth's `local.py`:

```python
# Add to INSTALLED_APPS
INSTALLED_APPS += [
    "fortunaisk",
]
```

### Step 3 - Finalize Installation

```bash
python manage.py migrate
python manage.py collectstatic
```

Restart your Alliance Auth instance:

```bash
supervisorctl restart all
```

### Step 4 - Setup Permissions

Visit your admin interface and assign permissions to appropriate groups:

| Permission                            | Purpose                     |
| ------------------------------------- | --------------------------- |
| `fortunaisk \| Can access FortunaISK` | Basic lottery participation |
| `fortunaisk \| Can admin FortunaISK`  | Full administrative access  |

### Step 5 - Configure Discord (Optional)

Visit `/admin/fortunaisk/webhookconfiguration/` to set up Discord notifications.

______________________________________________________________________

## 🎮 How to Use

### For Players

1. **🔍 Find Active Lotteries** - Check the lottery page to see what's currently running
1. **🎫 Buy Tickets** - Send ISK to the specified corporation with the lottery reference in the reason
1. **📊 Track Progress** - Monitor your tickets and see real-time lottery statistics
1. **🏆 Check Results** - Winners are announced automatically via Discord and notifications

### For Administrators

1. **➕ Create Lotteries** - Set ticket prices, duration, winners, and prize distribution
1. **🔄 Setup Recurring Lotteries** - Configure automated lotteries that repeat on schedule
1. **📈 Monitor Activity** - Watch real-time participant counts and revenue tracking
1. **🔧 Resolve Issues** - Use advanced tools to handle payment anomalies
1. **💰 Distribute Prizes** - Track and confirm prize distributions to winners

______________________________________________________________________

## 📸 Screenshots

### 🎲 User Experience

| **FortunaISK in Action**                                          | **Personal Dashboard**                                                 |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------- |
| ![FortunaISK Overview](docs/screenshots/fortunaisk_home_page.gif) | ![User Dashboard](docs/screenshots/fortunaisk_user_dashboard_page.png) |
| *Complete lottery system overview*                                | *Track tickets, winnings, and payments*                                |

**Lottery History**
![Lottery History](docs/screenshots/fortunaisk_lottery_history_page.png)
*Browse past lotteries with detailed results and statistics*

### 🛠️ Admin Interface

| **Admin Dashboard**                                                      | **Lottery Details**                                                      |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| ![Admin Dashboard](docs/screenshots/fortunaisk_admin_dashboard_page.png) | ![Lottery Details](docs/screenshots/fortunaisk_lottery_details_page.png) |
| *Real-time statistics and monitoring*                                    | *Participant tracking and anomaly resolution*                            |

### 🏆 Results & 🔔 Discord Integration

| **Winner Announcements**                                       | **Discord Notifications**                                                         |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| ![Winner Results](docs/screenshots/fortunaisk_winner_page.png) | ![New Lottery Discord](docs/screenshots/fortunaisk_new_lottery_discord_embed.png) |
| *Transparent prize distribution*                               | *Rich embeds for community engagement*                                            |

| **24-Hour Closure Reminders**                                                       |
| ----------------------------------------------------------------------------------- |
| ![24h Reminder Discord](docs/screenshots/fortunaisk_24h_remind_closure_discord.png) |
| *Automated reminders to boost participation before lottery closure*                 |

______________________________________________________________________

## 🆕 Latest Updates

### Version 1.0.0 - Stable Release! 🎉

- ✅ Multi-winner lottery support with custom prize distribution
- ✅ Automated recurring lotteries with flexible scheduling
- ✅ Enhanced admin dashboard with real-time statistics
- ✅ Advanced anomaly detection and resolution
- ✅ Comprehensive Discord integration
- ✅ CSV export functionality
- ✅ Complete audit trails and security improvements

### What's Coming Next

- 🎁 Physical prize lottery support

______________________________________________________________________

## 🔄 Updating

### Step 1 - Update Package

```bash
pip install -U fortunaisk
```

### Step 2 - Apply Changes

```bash
python manage.py migrate
python manage.py collectstatic
supervisorctl restart all
```

**⚠️ Important for v0.6.6+ users:** Discord webhook configuration has changed. Please reconfigure your webhooks at `/admin/fortunaisk/webhookconfiguration/` after updating.

______________________________________________________________________

## 🤝 Contributing

We welcome contributions! Whether it's bug fixes, new features, or documentation improvements:

1. **🍴 Fork** the repository
1. **🌿 Create** your feature branch: `git checkout -b feature/amazing-feature`
1. **📝 Commit** your changes: `git commit -m 'Add amazing feature'`
1. **🚀 Push** to the branch: `git push origin feature/amazing-feature`
1. **📬 Submit** a pull request

For major changes, please open an issue first to discuss your ideas.

______________________________________________________________________

## 🆘 Support

- **📚 Documentation**: [View the full documentation](https://github.com/your-repo/wiki)
- **🐛 Bug Reports**: [Report issues](https://github.com/your-repo/issues)
- **💬 Community**: Join the Alliance Auth Discord for support
- **✉️ Contact**: Reach out to the maintainer for direct support

______________________________________________________________________

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

______________________________________________________________________

**FortunaISK** - Bringing fair and exciting lotteries to your Alliance Auth community! 🎲✨

*Made with ❤️ for the EVE Online community*
