#!/bin/bash

cd /var/www &&\
git clone https://github.com/dhelonious/sublimall-server.git sublimall &&\
cd sublimall &&\
virtualenv -p /usr/bin/python3 venv &&\
source venv/bin/activate &&\
pip install -r requirements.txt &&\
cp sublimall/local_settings_example.py sublimall/local_settings.py &&\
./manage.py migrate &&\
./manage.py createsuperuser &&\
pip install gunicorn &&\
chown -R www-data:www-data /var/www/sublimall &&\
touch /var/log/sublimall.auth.log &&\
chown www-data /var/log/sublimall.auth.log
