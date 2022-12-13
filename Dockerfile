FROM python:3.9.15-slim-bullseye

COPY ./ /DiscordBot
WORKDIR /DiscordBot

RUN pip install -r requirements.txt
RUN playwright install
RUN playwright install-deps
RUN apt-get update && apt-get install -y xvfb && apt-get install -y xauth

ENV DISPLAY :0
CMD xvfb-run python3 -u main.py