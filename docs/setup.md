# Setup Guide

This guide will help you set up LuminaLearn for local development.

## Prerequisites

Before you begin, ensure you have the following installed on your system:

- **Python 3.8 or higher**: Download from [python.org](https://www.python.org/downloads/)
- **Git**: Download from [git-scm.com](https://git-scm.com/downloads)
- **Pip**: Usually comes with Python.

## Local Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Chidwan3578/LuminaLearn.git
cd LuminaLearn
```

### 2. Create and Activate Virtual Environment

It is recommended to use a virtual environment to manage dependencies.

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

Create a `.env` file in the project root by copying the template below (or use the one provided in the repository if available):

```env
DEBUG=True
SECRET_KEY=your-django-secret-key-here
DATABASE_URL=sqlite:///db.sqlite3

# Stellar Blockchain Settings
STELLAR_TESTNET=True
STELLAR_HORIZON_URL=https://horizon-testnet.stellar.org
STELLAR_RPC_URL=https://soroban-testnet.stellar.org
STELLAR_CONTRACT_ID=your-soroban-contract-id-here
```

> [!NOTE]
> For local development, `DEBUG` should be `True`. You can generate a secret key using standard Django tools or a random string generator.

### 5. Database Initialization

LuminaLearn uses Django's migration system.

```bash
python manage.py migrate
```

### 6. Create a Superuser

To access the admin dashboard, create an administrator account:

```bash
python manage.py createsuperuser
```

### 7. Stellar Testnet Setup

The application interacts with the Stellar blockchain. Ensure you have:

1. A valid `STELLAR_CONTRACT_ID` for a deployed Soroban attendance contract.
2. If you don't have one, you'll need to deploy the contract located in `LuminaLearnContract/`.

The system automatically handles wallet creation and funding (via Friendbot) for new users on the testnet.

### 8. Run the Development Server

```bash
python manage.py runserver
```

Open your browser and navigate to `http://127.0.0.1:8000/`.

---

## Technical Support

If you encounter issues during setup, please check the [Architecture Documentation](architecture.md) or open an issue in the repository.
