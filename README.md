# SchildCafé: Barista

![SchildCafé](logo.png)

This is a [Python](https://go.dev/) implementation of the Barista script used in the SchildCafé,
built with [peewee](http://docs.peewee-orm.com/en/latest/).

## Manual execution

Prepare

```shell
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Make sure to provide the MySQL credentials as environment variables and run

```shell
python3 barista.py
```

## Evironment variables

MySQL credentials are required

```shell
MYSQL_USER=<user>
MYSQL_PASS=<pass>
```

MySQL overrides are possible

```shell
MYSQL_HOST="localhost"
MYSQL_PORT="3306"
MYSQL_DB="cafe"
```

The available coffee machines must be in an arry

```shell
COFFEE_MACHINES='["http://localhost:1337"]'
```

To enable debug logging use

```shell
PYTHON_DEBUG='TRUE'
```

To log in [Gelf](https://go2docs.graylog.org/5-0/getting_in_log_data/gelf.html#GELFPayloadSpecification) format, set

```shell
GELF_LOGGING='TRUE'
```

To send traces to an OTEL endpoint, specify its address

```shell
export OTEL_TRACES_ENDPOINT="localhost:4318"
```
