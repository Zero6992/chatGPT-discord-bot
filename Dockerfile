FROM ubuntu:20.04
RUN apt-get update && \
    apt-get install -yq tzdata && \
    ln -fs /usr/share/zoneinfo/America/New_York /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get install -y python3-pip


COPY ./ /DiscordBot
WORKDIR /DiscordBot

RUN pip install -r requirements.txt
RUN playwright install
RUN playwright install-deps
RUN apt-get install -y xvfb && apt-get install -y xauth

ENV DISPLAY :0
CMD xvfb-run python3 -u main.py