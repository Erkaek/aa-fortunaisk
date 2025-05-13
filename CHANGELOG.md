# Changelog

All notable changes to **FortunaISK** are documented in this file.

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
