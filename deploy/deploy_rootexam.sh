#!/bin/bash
# Deploy the RootExam platform on a shared server.
# Usage (from your machine): upload the two archives to /tmp, then run this as root:
#   cd backend; git archive --format=tar -o rootexam-backend.tar HEAD
#   cd frontend; VITE_API_BASE_URL=/api npm run build; tar -cf rootexam-frontend.tar -C dist .
#   scp rootexam-*.tar root@SERVER:/tmp/ && ssh root@SERVER 'bash -s' < deploy/deploy_rootexam.sh
# Only touches rootexam-named resources and
# /opt/exambackend + /opt/examfrontend; other sites and databases are left alone.
set -euo pipefail

APP=/opt/exambackend
FRONT=/opt/examfrontend
PORT=8031
DOMAIN=rootexam.m3had-system.cloud
APP_USER=rootexam
DB=rootexam
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP=/root/backups/rootexam-$STAMP
NGINX_SITE=/etc/nginx/sites-available/rootexam

echo "== 1. backup existing folders to $BACKUP"
mkdir -p "$BACKUP"
[ -d "$APP" ] && tar -czf "$BACKUP/exambackend.tar.gz" -C /opt exambackend
[ -d "$FRONT" ] && tar -czf "$BACKUP/examfrontend.tar.gz" -C /opt examfrontend
ls -la "$BACKUP"

echo "== 2. service user"
id "$APP_USER" >/dev/null 2>&1 || useradd --system --home-dir "$APP" --shell /usr/sbin/nologin "$APP_USER"

echo "== 3. backend code"
if [ ! -f "$APP/.env" ]; then
  # First deploy: the old folder holds only an outdated checkout (backed up above).
  rm -rf "$APP"
  mkdir -p "$APP"
else
  # Re-deploy: replace code, keep .env, .venv, media, logs.
  find "$APP" -mindepth 1 -maxdepth 1 ! -name .env ! -name .venv ! -name media ! -name logs ! -name staticfiles -exec rm -rf {} +
fi
tar -xf /tmp/rootexam-backend.tar -C "$APP"
mkdir -p "$APP/media" "$APP/logs"

echo "== 4. database"
if ! sudo -u postgres psql -Atc "select 1 from pg_roles where rolname='$DB'" | grep -q 1; then
  DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "create role $DB login password '$DB_PASSWORD'"
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "create database $DB owner $DB encoding 'UTF8'"
  NEW_DB_PASSWORD=$DB_PASSWORD
else
  echo "role $DB already exists"
  NEW_DB_PASSWORD=""
fi

echo "== 5. .env (secrets generated here, never printed)"
if [ ! -f "$APP/.env" ]; then
  [ -n "$NEW_DB_PASSWORD" ] || { echo "role exists but no .env: refusing to guess the DB password"; exit 1; }
  SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
  cat > "$APP/.env" <<EOF
DEBUG=False
SECRET_KEY=$SECRET_KEY
ALLOWED_HOSTS=$DOMAIN,127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=https://$DOMAIN
CORS_ALLOWED_ORIGINS=https://$DOMAIN

DB_NAME=$DB
DB_USER=$DB
DB_PASSWORD=$NEW_DB_PASSWORD
DB_HOST=localhost
DB_PORT=5432

# SMS (Broadnet) - required to send signup/reset codes
SMS_PROVIDER=broadnet
BROADNET_USER=
BROADNET_PASS=
BROADNET_SID=

# HyperPay - empty means paid packages show "contact us" instead of a checkout.
# Sandbox: https://eu-test.oppwa.com   Live: https://eu-prod.oppwa.com
HYPERPAY_ENTITY_ID=
HYPERPAY_AUTHORIZATION=
HYPERPAY_BASE_URL=https://eu-test.oppwa.com
HYPERPAY_BRANDS=VISA MASTER
PAYMENT_CURRENCY=JOD

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
EOF
fi
chown -R "$APP_USER:$APP_USER" "$APP"
chmod 600 "$APP/.env"

echo "== 6. python environment"
[ -x "$APP/.venv/bin/python" ] || sudo -u "$APP_USER" python3 -m venv "$APP/.venv"
sudo -u "$APP_USER" "$APP/.venv/bin/pip" install --quiet --upgrade pip
sudo -u "$APP_USER" "$APP/.venv/bin/pip" install --quiet -r "$APP/requirements.txt"
cd "$APP"
sudo -u "$APP_USER" .venv/bin/python manage.py check --deploy --fail-level ERROR
sudo -u "$APP_USER" .venv/bin/python manage.py migrate --noinput
sudo -u "$APP_USER" .venv/bin/python manage.py collectstatic --noinput --clear >/dev/null
sudo -u "$APP_USER" .venv/bin/python manage.py compilemessages >/dev/null 2>&1 || true

echo "== 7. systemd service"
cat > /etc/systemd/system/exambackend.service <<EOF
[Unit]
Description=RootExam backend (gunicorn)
After=network.target postgresql.service

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP
ExecStart=$APP/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:$PORT --workers 2 --threads 2 --timeout 60 --access-logfile -
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --quiet exambackend
systemctl restart exambackend
sleep 3
systemctl is-active exambackend

echo "== 8. frontend"
mkdir -p "$FRONT"
find "$FRONT" -mindepth 1 -delete
tar -xf /tmp/rootexam-frontend.tar -C "$FRONT"
chown -R root:root "$FRONT"
chmod -R u=rwX,go=rX "$FRONT"
# Archives built on Windows come out world-writable; this is a shared server.
chmod -R u=rwX,g=rX,o= "$APP"
chmod 600 "$APP/.env"
chmod o+x "$APP"
chmod -R o+rX "$APP/media"

echo "== 9. nginx site (HTTP; certbot adds HTTPS once DNS resolves)"
if [ ! -f "$NGINX_SITE" ]; then
cat > "$NGINX_SITE" <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name rootexam.m3had-system.cloud;

    client_max_body_size 20m;
    root /opt/examfrontend;
    index index.html;

    # Backend: API, Django admin/dashboard, its static files and language switch.
    location ~ ^/(api|admin|system-admin|static|i18n)/ {
        proxy_pass http://127.0.0.1:8031;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 90s;
    }

    location /media/ {
        alias /opt/exambackend/media/;
    }

    # Vite assets have content hashes in their names.
    location /assets/ {
        expires 30d;
        add_header Cache-Control "public, immutable";
        try_files $uri =404;
    }

    # React router: every other path is the single-page app.
    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF
fi
ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/rootexam
if nginx -t 2>/tmp/rootexam-nginx-test.txt; then
  systemctl reload nginx
  echo "nginx reloaded"
else
  cat /tmp/rootexam-nginx-test.txt
  rm -f /etc/nginx/sites-enabled/rootexam
  echo "nginx test FAILED: rootexam site disabled, other sites untouched"
  exit 1
fi

echo "== 10. daily database backup (rootexam only, 14 days kept)"
cat > /usr/local/bin/rootexam-db-backup <<'BACKUP'
#!/bin/bash
# Nightly dump of the rootexam database only; other databases on this server are not touched.
set -euo pipefail
DIR=/root/backups/rootexam-db
mkdir -p "$DIR" && chmod 700 "$DIR"
OUT="$DIR/rootexam-$(date +%Y%m%d-%H%M).sql.gz"
sudo -u postgres pg_dump --no-owner rootexam | gzip -9 > "$OUT.tmp" && mv "$OUT.tmp" "$OUT"
find "$DIR" -name 'rootexam-*.sql.gz' -mtime +14 -delete
BACKUP
chmod 700 /usr/local/bin/rootexam-db-backup
echo "15 3 * * * root /usr/local/bin/rootexam-db-backup" > /etc/cron.d/rootexam-db-backup
chmod 644 /etc/cron.d/rootexam-db-backup
/usr/local/bin/rootexam-db-backup && ls -la /root/backups/rootexam-db | tail -2

echo "== 11. smoke tests (HTTPS through nginx on this host)"
R="--resolve $DOMAIN:443:127.0.0.1"
curl -s $R -o /dev/null -w "frontend /           %{http_code}\n" "https://$DOMAIN/"
curl -s $R -o /dev/null -w "spa route /login     %{http_code}\n" "https://$DOMAIN/login"
curl -s $R -o /dev/null -w "api /api/landing     %{http_code}\n" "https://$DOMAIN/api/landing/index"
curl -s $R -o /dev/null -w "admin login          %{http_code}\n" "https://$DOMAIN/system-admin/login/"
curl -s $R -o /dev/null -w "static admin css     %{http_code}\n" "https://$DOMAIN/static/admin/css/admin.css"
curl -s $R -o /dev/null -w "reset w/o token      %{http_code} (expect 422)\n" -H "Content-Type: application/json" \
  -d '{"phone":"+962700000000","password":"x12345678","password_confirmation":"x12345678"}' "https://$DOMAIN/api/reset"
rm -f /tmp/rootexam-backend.tar /tmp/rootexam-frontend.tar
echo "DONE"
