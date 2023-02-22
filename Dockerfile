# SchildCafé Servitør
# Copyright Carsten Thiel 2023
#
# SPDX-Identifier: Apache-2.0

FROM python:3.8-slim-buster

WORKDIR /app

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY barista.py .

CMD [ "python3", "./barista.py"]
