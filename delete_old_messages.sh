#!/bin/sh
cd ~/gawvertretung
export PYTHONPATH=${PYTHONPATH}:${HOME}/asynctelebot
echo "$PYTHONPATH"
python3.7 delete_old_messages.py > output/delete_old_messages.txt 2>&1