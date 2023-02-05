FROM python:3.9-slim-bullseye

COPY ./ /DiscordBot
WORKDIR /DiscordBot

RUN pip install -r requirements.txt

CMD ["python3", "-m", "main"]