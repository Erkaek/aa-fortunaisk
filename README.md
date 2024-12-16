# ⚠️ WARNING: DO NOT INSTALL ⚠️

**This project is still in active development and is not functional. Do not attempt to install or use it in any environment, especially production.**

# FortunaISK

FortunaISK is a monthly lottery module for Alliance Auth. **Please note: this project is still in development and is not yet functional for production use.**

## Features

- Configurable ticket price and unique reference ID (feature under development).
- Automatic verification of payments using `allianceauth-corp-tools` (in progress).
- History of winners available in the UI (coming soon).

## Installation

### Prerequisites

- Python 3.8+
- Alliance Auth 2.9+
- Django 3.2+
- `allianceauth-corp-tools` 1.0.0+

### Steps

1. **Clone the repository**:
   Since the package is under development, clone the repository instead of installing it via pip:

   ```bash
   git clone https://github.com/Erkaek/allianceauth-fortunaisk.git
   cd allianceauth-fortunaisk
   ```

1. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

1. **Add the module to your project**:
   Update your `INSTALLED_APPS` in your Django settings:

   ```python
   INSTALLED_APPS += [
       "fortunaisk",
   ]
   ```

1. **Apply migrations**:

   ```bash
   python manage.py migrate
   ```

1. **Collect static files**:

   ```bash
   python manage.py collectstatic
   ```

1. **Configuration**:
   The configuration is not finalized yet. Placeholder settings will be updated in future releases.

1. **Restart services**:
   Restart your application services to apply the changes.

## Current Status

- **Development**: The project is still under active development. Features may be incomplete or subject to change.
- **Testing**: Please do not use in a production environment.

## Contributions

Contributions are welcome! Feel free to open issues or submit pull requests to help improve FortunaISK.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
