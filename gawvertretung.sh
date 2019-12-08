#!/bin/sh
cd ~/gawvertretung
export PYTHONPATH=${PYTHONPATH}:${HOME}/asynctelebot
echo "$PYTHONPATH"
nohup python3.7 build_snippets.py 2> output/build_snippets.txt &
nohup python3.7 bot_sender.py 2> output/bot_sender.txt &
nohup python3.7 bot_listener_students.py 2> output/bot_listener_students.txt &
nohup python3.7 bot_listener_teachers.py 2> output/bot_listener_teachers.txt &