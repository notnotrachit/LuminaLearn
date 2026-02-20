# Deployment Guide

This guide covers the steps required to deploy LuminaLearn to a production environment.

## Production Requirements

- **Server**: Linux (Ubuntu 22.04 LTS recommended)
- **Web Server**: Nginx
- **Application Server**: Gunicorn
- **Database**: PostgreSQL (recommended)
- **Domain & SSL**: Certbot (Let's Encrypt)
- **Stellar Account**: A funded mainnet or persistent testnet account.

## 1. Environment Configuration

In production, ensure you have a separate `.env` file with secure settings:

```env
DEBUG=False
SECRET_KEY=highly-secure-random-string
DATABASE_URL=postgres://user:password@localhost/luminalearn
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Stellar Blockchain Settings
STELLAR_TESTNET=False  # Set to False for mainnet
STELLAR_HORIZON_URL=https://horizon.stellar.org
STELLAR_CONTRACT_ID=your-production-contract-id
```

## 2. Database Migration

Install PostgreSQL and create the database. Then run migrations:

```bash
python manage.py migrate
python manage.py collectstatic --no-input
```

## 3. Gunicorn Setup

Create a Gunicorn service file (e.g., `/etc/systemd/system/gunicorn.service`):

```ini
[Unit]
Description=gunicorn daemon
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/LuminaLearn
ExecStart=/var/www/LuminaLearn/venv/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind unix:/var/www/LuminaLearn/luminalearn.sock \
          attendance_system.wsgi:application

[Install]
WantedBy=multi-user.target
```

## 4. Nginx Configuration

Configure Nginx to proxy requests to Gunicorn:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    location /static/ {
        root /var/www/LuminaLearn;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/LuminaLearn/luminalearn.sock;
    }
}
```

## 5. SSL Setup (HTTPS)

Use Certbot to obtain and install an SSL certificate:

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

## 6. Security Hardening

- **Private Keys**: Ensure `stellar_seed` is encrypted at rest.
- **Firewall**: Use `ufw` to allow only SSH, HTTP, and HTTPS.
- **Updates**: Regularly update basic system packages and project dependencies.

---

## Maintenance

- **Backups**: Set up regular backups for your PostgreSQL database.
- **Logs**: Monitor Gunicorn and Nginx logs for any errors.
  ```bash
  sudo journalctl -u gunicorn
  sudo tail -f /var/log/nginx/error.log
  ```
