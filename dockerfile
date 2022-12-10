FROM python:3.9.15-slim-bullseye
COPY ./ /DiscordBot
WORKDIR /DiscordBot
RUN pip install -r requirements.txt
CMD ["python", "-u", "main.py"]