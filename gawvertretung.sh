#!/bin/bash
cd ~/gawvertretung
export PYTHONPATH=${PYTHONPATH}:${HOME}/asynctelebot
echo "$PYTHONPATH"
nohup python3.7 build_snippets.py > /dev/null 2> output/build_snippets.txt &
sleep 10  # sleep so that mysql has started
nohup python3.7 bot_sender.py > /dev/null > /dev/null 2> output/bot_sender.txt &
nohup python3.7 bot_listener_students.py > /dev/null 2> output/bot_listener_students.txt &
nohup python3.7 bot_listener_teachers.py > /dev/null 2> output/bot_listener_teachers.txt &