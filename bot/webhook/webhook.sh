#!/bin/bash
cd "$(dirname "$0")/.."
export PYTHONPATH=${PYTHONPATH}:${HOME}/asynctelebot/

if [ "$1" = "halt" ]
then
  python3.7 ./webhook/remove_webhook.py
else
  python3.7 ./webhook/set_webhook.py
fi

exit 0