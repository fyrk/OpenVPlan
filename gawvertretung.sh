#!/bin/bash
cd ~/gawvertretung
export PYTHONPATH=${PYTHONPATH}:${HOME}/asynctelebot
echo "$PYTHONPATH"
echo "build snippets"
nohup python3.7 build_snippets.py > /dev/null 2> output/build_snippets.txt &
echo "starting bot_sender"
nohup python3.7 bot_sender.py > /dev/null > /dev/null 2> output/bot_sender.txt &
echo "setting webhook"
/bin/bash "${HOME}/gawvertretung/bot/webhook/webhook.sh" set