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

## Evironment variables

MySQL credentials are required
```
MYSQL_USER=<user>
MYSQL_PASS=<pass>
```

MySQL overrides are possible
```
MYSQL_HOST="localhost"
MYSQL_PORT="3306"
MYSQL_DB="cafe"
```

The available coffee machines must be in an arry
```
COFFEE_MACHINES='["http://localhost:1337"]'
```

To enable debug logging use
```
PYTHON_DEBUG='TRUE'
```
To log in [Gelf](https://go2docs.graylog.org/5-0/getting_in_log_data/gelf.html#GELFPayloadSpecification)
 format, set
```
GELF_LOGGING='TRUE'
```