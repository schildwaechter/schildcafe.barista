# SchildCafé: Barista

![SchildCafé](logo.png)

This is a [Python](https://go.dev/) implementation of the Barista script used in the SchildCafé,
built with [peewee](http://docs.peewee-orm.com/en/latest/).

## Manual execution

Prepare
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Make sure to provide the MySQL credentials as environment variables and run
```
python3 barista.py
```
