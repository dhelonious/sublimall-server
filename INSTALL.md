# Set up you own Sublimall server

## Requirements

You'll need:
 - Python 3.6
 - Database like Postgresql is optionnal if you use Sublimall for personnal or few users
 
## Installation

```
cd /var/www
git clone https://github.com/toxinu/sublimall-server.git sublimall
cd sublimall
virtualenv -p /usr/bin/python3 venv
source venv/bin/activate
pip install -r requirements.txt
cp sublimall/local_settings_example.py sublimall/local_settings.py
./manage.py migrate
./manage.py createsuperuser
pip install gunicorn
chown www-data:www-data /var/www/sublimall
```

## Deployment

Create daemon at ```/etc/systemd/system/sublimall.service```:

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

For nginx, this is a production server configuration file dump:

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

As you can see, configuration file include ssl, which you can drop easily.

For Apache2 with ssl use:

```
<VirtualHost *:443>
  ServerName  example.com
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

## Plugin

And you just have to change your Sublime Text plugin settings.

```
"api_root_url": "http://<ip>:<port>",
```

[0]: http://supervisord.org/
