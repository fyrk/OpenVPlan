# syntax=docker/dockerfile:1
FROM python:3.9-alpine

COPY requirements.txt /app/requirements.txt
RUN apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev openssl-dev python3-dev cargo \
    && pip3 install -r /app/requirements.txt \
    && apk del .build-deps gcc musl-dev libffi-dev openssl-dev python3-dev cargo \
    && rm -r /root/.cache  # reduce image size drastically

ARG mode
COPY requirements-dev.txt /app/requirements-dev.txt
RUN if [ "$mode" = "dev" ] ; then pip3 install -r /app/requirements-dev.txt && pip install debugpy -t /tmp ; fi

# thanks, nginx
RUN mkdir /var/log/openvplan && ln -sf /dev/stdout /var/log/openvplan/openvplan.log

COPY LICENSE /app/
COPY entrypoint.sh /
COPY config/ /config/
COPY app/ /app/app/
COPY static/ /app/static/

EXPOSE 8000
CMD [ "/entrypoint.sh" ]
