# Changelog

All notable changes to **FortunaISK** are documented in this file.

## [1.0.0] – 2025-05-30

### 🎉 **First Stable Release**

**FortunaISK** is now production-ready! This major release marks the transition from beta to stable with comprehensive features, enhanced security, and improved user experience.

### Added

- **Multi-winner lottery support** with customizable prize distribution percentages
- **Automated recurring lotteries** with flexible scheduling (minutes, hours, days, months)
- **Comprehensive admin dashboard** with real-time statistics and system monitoring
- **Advanced anomaly detection and resolution system** with detailed audit trails
- **Prize distribution management** with automated tracking and confirmation workflow
- **CSV export functionality** for winners, participants, and lottery data
- **Enhanced Discord integration** with rich embeds and automated notifications
- **User personal dashboard** showing complete ticket purchase and winning history
- **Lottery history interface** with filtering, pagination, and detailed records
- **24-hour closure reminders** for active lotteries
- **Thread-safe payment processing** with database locking mechanisms
- **Comprehensive audit trails** for all administrative actions
- **Data integrity validation** with consistency checks across all operations
- **Robust error handling** with automatic recovery mechanisms

### Changed

- **Promoted from Beta to Stable** - Production-ready with enterprise-grade reliability
- **Enhanced notification system** with improved Discord webhook configuration
- **Optimized database performance** with proper indexing and efficient queries
- **Improved user interface** with responsive design and better accessibility
- **Streamlined admin tools** with intuitive management interfaces
- **Enhanced security measures** with comprehensive permission system

### Technical Improvements

- **Celery-based background processing** for scalable lottery management
- **Automated task scheduling** with intelligent conflict prevention
- **Database optimization** with efficient queries and proper relationships
- **Alliance Auth integration** with seamless permission management
- **Corp Tools compatibility** for automated payment processing
- **EVE Online character management** integration

### Security & Reliability

- **Complete audit logging** for all system operations
- **Transaction validation** with duplicate payment prevention
- **Concurrent operation safety** with proper locking mechanisms
- **Data consistency enforcement** across all lottery operations
- **Backup and recovery** considerations for production environments

### Performance

- **Optimized queries** with reduced database load
- **Efficient pagination** for large datasets
- **Caching implementation** for improved response times
- **Background task optimization** for better scalability

______________________________________________________________________

## [0.6.6] – 2025-05-13

### Added

- Integration of **aa-discordnotify** via `DiscordProxyClient` for private Discord DM notifications

### Changed

- Bump version to **0.6.6** in `fortunaisk/__init__.py` and `pyproject.toml`
- Refactor `fortuna­isk/notifications.py` to replace manual `DiscordBotService` loading with `DiscordProxyClient`, enhance logging, and simplify code
- Update `requirements.txt` to include the `aa-discordnotify` dependency
- Streamline `CHANGELOG.md` to a Keep a Changelog–compliant format
- Update `README.md` to document the use of the Discord notify module for private messages

:contentReference[oaicite:0]{index=0}\
::contentReference[oaicite:1]{index=1}

## [0.2.36] – 2025-01-02

### Changed

- Bumped package version to **0.2.36** :contentReference[oaicite:0]{index=0}

## [0.2.35] – 2025-01-02

### Changed

- Bumped package version to **0.2.35** :contentReference[oaicite:1]{index=1}

## [0.2.0] – 2024-12-31

### Added

- Enhanced user & admin dashboards with detailed ticket-and-prize statistics
- Added a decimal-formatting filter for ISK amounts

### Changed

- Refactored admin interfaces to show participant counts in `LotteryAdmin`
- Updated migration instructions for Celery and django-celery-beat
- Bumped package version to **0.2.0** :contentReference[oaicite:2]{index=2}

## [0.1.7] – 2024-12-30

### Changed

- Bumped package version to **0.1.7** :contentReference[oaicite:3]{index=3}

## [0.1.6] – 2024-12-30

### Added

- **User dashboard** to view purchased tickets and winnings
- **Admin dashboard** listing recent anomalies and resolution actions
- Signal-driven notifications for:
  - Ticket purchase confirmation
  - Payment anomalies
  - Winner announcements
  - Prize distribution
- Enforcement of per-user ticket limits with anomaly recording
- Models, views and templates refactored for robust anomaly handling
- Initial support for recurring lotteries via `AutoLottery` and Celery tasks

### Changed

- Renamed package to **fortunaisk** and updated Flit/`pyproject.toml`
- Added `{% participant_count %}` display in admin list views
- Improved CSV export mixin for admin models

### Fixed

- Resolved issues in winner-list queries for correct prize totals
- Fixed migration generation on new installs :contentReference[oaicite:4]{index=4}
