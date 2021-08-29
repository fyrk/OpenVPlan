# syntax=docker/dockerfile:1
FROM python:alpine
WORKDIR /app
COPY requirements.txt requirements.txt
RUN apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev openssl-dev python3-dev cargo \
    && pip3 install -r requirements.txt \
    && apk del .build-deps gcc musl-dev libffi-dev openssl-dev python3-dev cargo \
    && rm -r /root/.cargo && rm -r /root/.cache  # reduce image size drastically

ARG mode
COPY requirements-dev.txt requirements-dev.txt
RUN if [ "$mode" = "dev" ] ; then pip3 install -r requirements-dev.txt ; fi

# thanks, nginx
RUN mkdir /var/log/gawvertretung && ln -sf /dev/stdout /var/log/gawvertretung/gawvertretung.log

COPY . .

COPY entrypoint.sh "/"
EXPOSE 8080
CMD [ "/entrypoint.sh" ]
