FROM ubuntu:20.04
RUN apt-get update && \
    apt-get install -yq tzdata && \
    ln -fs /usr/share/zoneinfo/America/New_York /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get install -y python3-pip


COPY ./ /DiscordBot
WORKDIR /DiscordBot

RUN pip install -r requirements.txt

CMD python3 -u main.py
