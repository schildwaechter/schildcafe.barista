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
import peewee
import dns.resolver
from urllib.parse import urlparse, urlunparse
from datetime import datetime
from dateutil import parser

import mysql.connector

provided_coffee_machines = json.loads(os.environ.get('COFFEE_MACHINES','["http://localhost:1337"]'))
coffee_machines = []
# resolve all hostnames to IPs to support kubernetes deployements
for entry in provided_coffee_machines:
    old_url = urlparse(entry)
    # get IP addresses
    result = dns.resolver.resolve(old_url.hostname)
    for ipval in result:
        url_lst = list(old_url)
        if old_url.port != None:
            url_lst[1] = ipval.to_text()+':'+str(old_url.port)
        else:
            url_lst[1] = ipval.to_text()
        coffee_machines.append(urlunparse(url_lst))

MYSQL_USER = os.environ['MYSQL_USER']
MYSQL_PASS = os.environ['MYSQL_PASS']
MYSQL_HOST = os.environ.get('MYSQL_HOST','localhost')
MYSQL_PORT = os.environ.get('MYSQL_PORT','3306')
MYSQL_DB = os.environ.get('MYSQL_DB','cafe')

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
    Product = peewee.CharField(column_name='product')
    OrderID = peewee.CharField(column_name='order_id')
    OrderReceived = peewee.CharField(column_name='order_received')
    Machine = peewee.CharField(column_name='machine', null=True)
    JobID = peewee.CharField(column_name='job_id')
    JobStarted = peewee.CharField(column_name='job_started', null=True)
    JobReady = peewee.CharField(column_name='job_ready', null=True)
    JobRetrieved = peewee.CharField(column_name='job_retrieved', null=True)

    class Meta:
        table_name = 'coffee_list_items'
        database = mysqldb

# retrieve finished jobs
for job in CoffeeListItem.select().where(CoffeeListItem.Machine.is_null(False) & CoffeeListItem.JobRetrieved.is_null(True)):
    # get comparable timestamps
    jobReady = datetime.fromisoformat(job.JobReady).isoformat(timespec='seconds')
    present = datetime.utcnow().isoformat(timespec='seconds')
    if (jobReady < present):
        response = requests.get(job.Machine+"/retrieve-job/"+job.JobID)
        jsonResponse = response.json()
        job.JobRetrieved = datetime.utcnow().isoformat(timespec='seconds')
        job.save()
        # update progress counter
        order = Order.select().where(Order.ID == job.OrderID).get()
        order.OrderBrewed += 1
        # if we're done, mark the time
        if order.OrderSize == order.OrderBrewed:
            order.OrderReady = job.JobRetrieved
        order.save()
        print(jsonResponse)


# find empty machines
for pot in coffee_machines:
    machineStatus = requests.get(pot+"/status")
    if (machineStatus.status_code == 200):
        # get one job to schedule on the machine
        for job in CoffeeListItem.select().where(CoffeeListItem.Machine.is_null(True)).limit(1):
            response = requests.post(pot+"/start-job", data=json.dumps({"product": job.Product}), headers={"Content-Type":"application/json"})
            jsonResponse = response.json()
            job.Machine = pot
            job.JobID = jsonResponse["jobId"]
            job.JobReady = jsonResponse["jobReady"]
            print("job "+job.JobID+" sent to "+job.Machine+", ready at "+job.JobReady)
            job.JobStarted = datetime.utcnow().isoformat(timespec='seconds')
            job.save()

sys.exit()
