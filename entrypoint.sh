#!/bin/sh
cd /app
mkdir /static
cp -r /app/assets/static/* /static
find /static -mindepth 1 -mtime +1 -delete
python3 server.py --host=0.0.0.0
