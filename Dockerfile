FROM python:3.10-slim

ENV PYTHONUNBUFFERED 1

COPY ./ /DiscordBot
WORKDIR /DiscordBot
RUN pip3 install cryptography
RUN pip3 install -r requirements.txt

CMD ["python3", "main.py"]