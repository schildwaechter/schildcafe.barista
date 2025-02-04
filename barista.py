#!/usr/bin/env python3
#
# SchildCafé Barista
# Copyright Carsten Thiel 2023
#
# SPDX-Identifier: Apache-2.0

import requests
import json
import sys
import os
import logging
import peewee
import dns.resolver
import socket
import random
import string
from urllib.parse import urlparse, urlunparse
from datetime import datetime
from gelfformatter import GelfFormatter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

import mysql.connector

# Set up tracing
resource = Resource(attributes={SERVICE_NAME: "barista"})
traceProvider = TracerProvider(resource=resource)
if "OTEL_TRACES_ENDPOINT" in os.environ:
    processor = BatchSpanProcessor(OTLPSpanExporter(
        endpoint="http://" + os.environ.get('OTEL_TRACES_ENDPOINT', 'localhost:4318') + "/v1/traces"))
else:
    processor = BatchSpanProcessor(ConsoleSpanExporter())

traceProvider.add_span_processor(processor)
trace.set_tracer_provider(traceProvider)

# start traging
tracer = trace.get_tracer(__name__)
tracer.start_as_current_span("barista")
span_context = trace.get_current_span().get_span_context()
traceparent = "00-" + format(span_context.trace_id, 'x') + "-" + format(span_context.span_id, 'x') + "-01"

# create the X-REQUEST-ID template
hostname = socket.gethostname()
all_letters = string.ascii_lowercase
random_string = ''.join(random.choice(all_letters) for i in range(6))
request_str_template = hostname + '-' + random_string + '-'
request_counter = 0


def get_request_id():
    global request_counter
    request_counter += 1
    return (request_str_template + str(request_counter))

# patch logger for _extra data - https://stackoverflow.com/a/59176750


def make_record_with_extra(self, name, level, fn, lno, msg, args, exc_info, func=None, extra=None, sinfo=None):
    record = original_makeRecord(self, name, level, fn, lno, msg, args, exc_info, func, extra, sinfo)
    record._extra = extra
    return record


original_makeRecord = logging.Logger.makeRecord
logging.Logger.makeRecord = make_record_with_extra


class myPlainFormatter(logging.Formatter):
    def format(self, record):
        return super().format(record)


# configure logger
if "GELF_LOGGING" in os.environ:
    formatter = GelfFormatter()
else:
    formatter = myPlainFormatter('%(asctime)s - %(name)s - %(levelname)s - %(_extra)s - %(message)s')

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
python_debug = os.environ.get('PYTHON_DEBUG', 'FALSE')
if python_debug == 'TRUE':
    logging.basicConfig(level=logging.DEBUG, handlers=[handler])
else:
    logging.basicConfig(level=logging.INFO, handlers=[handler])

logging.debug("# SchildCafe Barista started at " + datetime.now().isoformat())

provided_coffee_machines = json.loads(os.environ.get('COFFEE_MACHINES', '["http://localhost:1337"]'))
coffee_machines = []
# resolve all hostnames to IPs to support kubernetes deployements
for entry in provided_coffee_machines:
    logging.debug("IP resolving coffee machine " + entry)
    old_url = urlparse(entry)
    # get IP addresses
    result = dns.resolver.resolve(old_url.hostname)
    for ipval in result:
        url_lst = list(old_url)
        if old_url.port != None:
            url_lst[1] = ipval.to_text() + ':' + str(old_url.port)
        else:
            url_lst[1] = ipval.to_text()
        logging.debug("entry updated to " + urlunparse(url_lst))
        coffee_machines.append(urlunparse(url_lst))

MYSQL_USER = os.environ['MYSQL_USER']
MYSQL_PASS = os.environ['MYSQL_PASS']
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_PORT = os.environ.get('MYSQL_PORT', '3306')
MYSQL_DB = os.environ.get('MYSQL_DB', 'cafe')

mysqldb = peewee.MySQLDatabase(MYSQL_DB, user=MYSQL_USER, password=MYSQL_PASS,
                               host=MYSQL_HOST, port=int(MYSQL_PORT))


class Order(peewee.Model):
    ID = peewee.CharField(column_name='id')
    OrderReceived = peewee.CharField(column_name='order_received', null=True)
    OrderReady = peewee.CharField(column_name='order_ready', null=True)
    OrderRetrieved = peewee.CharField(column_name='order_retrieved', null=True)
    OrderSize = peewee.IntegerField(column_name='order_size')
    OrderBrewed = peewee.IntegerField(column_name='order_brewed')

    class Meta:
        table_name = 'orders'
        database = mysqldb


class CoffeeListItem(peewee.Model):
    ID = peewee.CharField(column_name='id')
    Product = peewee.CharField(column_name='product')
    OrderID = peewee.CharField(column_name='order_id')
    OrderReceived = peewee.CharField(column_name='order_received')
    Machine = peewee.CharField(column_name='machine', null=True)
    JobStarted = peewee.CharField(column_name='job_started', null=True)
    JobReady = peewee.CharField(column_name='job_ready', null=True)
    JobRetrieved = peewee.CharField(column_name='job_retrieved', null=True)

    class Meta:
        table_name = 'coffee_list_items'
        database = mysqldb


# retrieve finished jobs
for job in CoffeeListItem.select().where(CoffeeListItem.Machine.is_null(False) & CoffeeListItem.JobRetrieved.is_null(True)):
    logging.debug("checking job " + job.ID)
    # get comparable timestamps
    jobReady = datetime.fromisoformat(job.JobReady).isoformat(timespec='seconds')
    present = datetime.utcnow().isoformat(timespec='seconds')
    if (jobReady < present):
        this_request_id = get_request_id()
        logging.debug("trying to receive job " + job.ID, extra={"x-request-id": this_request_id, "traceparent": traceparent})
        response = requests.get(job.Machine + "/retrieve-job/" + job.ID, headers={"X-Request-ID": this_request_id, "traceparent": traceparent})
        jsonResponse = response.json()
        job.JobRetrieved = datetime.utcnow().isoformat(timespec='seconds')
        job.save()
        logging.info("job " + job.ID + " retrieved from " + job.Machine + " at " + job.JobRetrieved,
                     extra={"x-request-id": this_request_id, "traceparent": traceparent})
        # update progress counter
        order = Order.select().where(Order.ID == job.OrderID).get()
        order.OrderBrewed += 1
        # if we're done, mark the time
        if order.OrderSize == order.OrderBrewed:
            order.OrderReady = job.JobRetrieved
            logging.info("order " + order.ID + " ready")
        order.save()

# find empty machines
for pot in coffee_machines:
    this_request_id = get_request_id()
    logging.debug("getting machine status for " + pot, extra={"x-request-id": this_request_id, "traceparent": traceparent})
    machineStatus = requests.get(pot + "/status", headers={"X-Request-ID": this_request_id, "traceparent": traceparent})
    if (machineStatus.status_code == 200):
        logging.debug("looking for a job to submit to machine " + pot)
        # get one job to schedule on the machine
        for job in CoffeeListItem.select().where(CoffeeListItem.Machine.is_null(True)).limit(1):
            this_request_id = get_request_id()
            logging.debug("trying to start job " + job.ID + " on machine " + pot, extra={"x-request-id": this_request_id, "traceparent": traceparent})
            response = requests.post(pot + "/start-job", data=json.dumps({"product": job.Product}),
                                     headers={"Content-Type": "application/json", "X-Request-ID": this_request_id, "traceparent": traceparent})
            jsonResponse = response.json()
            job.Machine = pot
            logging.debug("submitted job " + job.ID + " has (new) jobID " + jsonResponse["jobId"],
                          extra={"x-request-id": this_request_id, "traceparent": traceparent})
            job.ID = jsonResponse["jobId"]
            job.JobReady = jsonResponse["jobReady"]
            logging.info("job " + job.ID + " sent to " + job.Machine + ", ready at " + job.JobReady,
                         extra={"x-request-id": this_request_id, "traceparent": traceparent})
            job.JobStarted = datetime.utcnow().isoformat(timespec='seconds')
            job.save()

logging.debug("# SchildCafe Barista finished at " + datetime.now().isoformat())

sys.exit()
