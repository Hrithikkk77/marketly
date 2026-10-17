<<<<<<< HEAD
# Marketly: Flask + MySQL e-commerce

## Run locally in VS Code
Prerequisites: Python 3.10+ and MySQL 8 (MySQL Community Server; remember the root password you set).

1. Unzip, then in VS Code: File > Open Folder > `marketly`. Open a terminal (Ctrl+`).
2. Create and activate a virtual environment.
   - Windows (Command Prompt or PowerShell): `python -m venv venv` then `venv\Scripts\activate`
     (if `python` isn't found use `py`; if PowerShell says "running scripts is disabled", run
     `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or switch the terminal to Command Prompt)
   - Mac/Linux: `python3 -m venv venv && source venv/bin/activate`
3. When VS Code asks to use the new environment, click Yes (or Ctrl+Shift+P > Python: Select Interpreter > `venv`).
4. `pip install -r requirements.txt`
5. `python create_database.py`   (enter MySQL admin user `root` and its password)
6. `python seed.py`   (creates tables, admin user, sample products)
7. `python run.py`, then open http://127.0.0.1:5000

Admin login: `admin@marketly.local` / `Admin@12345` (from `.env`), admin panel at /admin.

## Deploy on AWS (EC2 + RDS MySQL)
1. **RDS**: create a MySQL 8 instance (not publicly accessible) and note the master username/password and endpoint.
   Security group: allow port 3306 only from the EC2 security group.
2. **EC2**: Ubuntu 22.04 `t3.small`. Security group: 22 (your IP), 80, 443.
3. On the server:
```bash
sudo apt update && sudo apt install -y python3-venv nginx git
git clone <your-repo> /opt/marketly && cd /opt/marketly
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env     # DB_HOST = RDS endpoint, strong SECRET_KEY, admin password, FLASK_ENV=production
./venv/bin/python create_database.py  # use the RDS master user/password
./venv/bin/python seed.py
```
4. **systemd** `/etc/systemd/system/marketly.service`:
```
[Unit]
Description=Marketly
After=network.target
[Service]
WorkingDirectory=/opt/marketly
ExecStart=/opt/marketly/venv/bin/gunicorn -w 3 -b 127.0.0.1:8000 wsgi:app
Restart=always
User=ubuntu
[Install]
WantedBy=multi-user.target
```
`sudo systemctl enable --now marketly`
5. **nginx** `/etc/nginx/sites-available/marketly`:
```
server {
  listen 80; server_name yourdomain.com;
  location /static/ { alias /opt/marketly/static/; }
  location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto $scheme; }
}
```
`sudo ln -s /etc/nginx/sites-available/marketly /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl reload nginx`
6. HTTPS: `sudo apt install certbot python3-certbot-nginx && sudo certbot --nginx -d yourdomain.com`
   (`FLASK_ENV=production` makes cookies HTTPS-only, so do this step or login will not stick.)

Health check URL: `/health`.

## Not included
Online payments (add Stripe/Razorpay in `checkout`), email, product reviews, image upload, password reset.
=======
# marketly
>>>>>>> 76a7d1274301e080a28b7e7466f0eb2767277096
