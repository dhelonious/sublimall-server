# Set up your own Sublimall server

## Requirements

You'll need:
 - Python 3.5
 - Database like Postgresql is optional if you use Sublimall only for yourself or few users

## Installation

Use the ```install.sh``` script or do it manually:

```
cd /var/www
git clone https://github.com/dhelonious/sublimall-server.git sublimall
cd sublimall
virtualenv -p /usr/bin/python3 venv
source venv/bin/activate
pip install -r requirements.txt
cp sublimall/local_settings_example.py sublimall/local_settings.py
./manage.py migrate
./manage.py createsuperuser
pip install gunicorn
chown -R www-data:www-data /var/www/sublimall
touch /var/log/sublimall.auth.log
chown www-data /var/log/sublimall.auth.log
```

**Note**: I disabled the sign up links, since I use the server only for myself. If you want to allow for registrations, feel free to uncomment the lines corresponding to *Sign up* in `templates/home.html` and `templates/base.html`.

### Fail2ban setup

To increase security the authentication log should be watched by fail2ban. A basic fail2ban configuration for sublimall is given below.

*/etc/fail2ban/filter.d/sublimall-auth.conf*:
```
[Definition]
failregex = Login Fail.*by <HOST>
ignoreregex =
```

*/etc/fail2ban/jail.d/defaults-DISTRIBUTION.conf* (where DISTRIBUTION can be debian, raspbian, ...):
```
[sublimall]
enabled = true
port = 80,443
protocol = tcp
filter = sublimall-auth
maxretry = 3
bantime = 5400
logpath = /var/log/sublimall.auth.log
```

## Deployment

Create a daemon at ```/etc/systemd/system/sublimall.service```:

```
[Unit]
Description=Sublimall Server for synchronizing Sublime Text settings

[Service]
Type=simple
PIDFile=/run/sublimall.pid
User=www-data
Group=www-data
WorkingDirectory=/var/www/sublimall
ExecStart=/var/www/sublimall/venv/bin/gunicorn sublimall.wsgi:application --log-file=- -b 127.0.0.1:9002
Restart=always

[Install]
WantedBy=multi-user.target
```

For Apache2 use:

```
<VirtualHost *:80>
  ServerName example.com
  ServerAdmin webmaster@example.com
  Redirect / https://example.com

  ErrorLog ${APACHE_LOG_DIR}.sublimall.error.log
  CustomLog ${APACHE_LOG_DIR}/sublimall.access.log combined
</VirtualHost>

<VirtualHost *:443>
  ServerName example.com
  ServerAdmin webmaster@example.com
  DocumentRoot /var/www/sublimall

  ProxyPreserveHost On
  ProxyRequests off

  ProxyPass        / http://localhost:9002/
  ProxyPassReverse / http://localhost:9002/
  RequestHeader set Origin http://localhost:9002/

  Alias /static /var/www/sublimall/static
  <Directory /var/www/sublimall/static>
    AllowOverride None
    Order allow,deny
    Allow from all
  </Directory>

  SSLProxyEngine On
  SSLProtocol all -SSLv2 -SSLv3
  SSLHonorCipherOrder on
  SSLCipherSuite "EECDH+ECDSA+AESGCM EECDH+aRSA+AESGCM EECDH+ECDSA+SHA384 EECDH+ECDSA+SHA256 EECDH+aRSA+SHA384 EECDH+aRSA+SHA256 EECDH+aRSA+RC4 EECDH EDH+aRSA RC4 !aNULL !eNULL !LOW !3DES !MD5 !EXP !PSK !SRP !DSS +RC4 RC4"
  SSLCertificateFile      /etc/apache2/ssl/sublimall/cert.pem;
  SSLCertificateKeyFile   /etc/apache2/ssl/sublimall/privkey.pem
  SSLCertificateChainFile /etc/apache2/ssl/sublimall/chain.pem

  Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"

  ErrorLog ${APACHE_LOG_DIR}/error.log
  CustomLog ${APACHE_LOG_DIR}/access.log combined

</VirtualHost>
```

For nginx use:

```
server {
    listen 80;
    server_name example.com;

    error_log /var/log/nginx/sublimall.error.log;
    access_log /var/log/nginx/sublimall.access.log;

    client_max_body_size 150m;

    location /api {
        proxy_hide_header Server;

        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forward-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Ssl on;
        proxy_pass http://127.0.0.1:9002;
    }

    location / {
        rewrite ^ https://example.com$request_uri permanent;
    }
}
server {
    listen 443 ssl spdy;
    server_name example.com;

    ssl_certificate /etc/nginx/ssl/sublimall.public.crt;
    ssl_certificate_key /etc/nginx/ssl/sublimall.private.rsa;

    error_log /var/log/nginx/sublimall.error.log;
    access_log /var/log/nginx/sublimall.access.log;

    if ($http_host != "sublimall.org") {
        rewrite ^ https://example.com$request_uri permanent;
    }

    location /api {
        rewrite ^ http://example.com$request_uri permanent;
    }

    location /static {
        autoindex on;
        root /var/www/sublimall;
    }

    location / {
        proxy_hide_header Server;

        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forward-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Ssl on;
        proxy_pass http://127.0.0.1:9002;
    }
}
```

For extra security failed logins should be logged and watched by ```fail2ban```.

## Plugin

You have to change your Sublime Text plugin settings:

```
"api_root_url": "https://example.com",
```

[0]: http://supervisord.org/
