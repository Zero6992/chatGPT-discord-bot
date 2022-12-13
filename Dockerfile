FROM python:3.9.15-slim-bullseye

COPY ./ /DiscordBot
WORKDIR /DiscordBot

RUN pip install -r requirementsDocker.txt

CMD ["python3", "-u", "main.py"]
