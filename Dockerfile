FROM python:3.10-bullseye

ENV PYTHONUNBUFFERED 1
RUN apt-get update && apt-get install -y \
  build-essential \
  libcairo2-dev \
  cargo \
  libfreetype6-dev \
  gcc \
  libgdk-pixbuf2.0-dev \
  gettext \
  libjpeg-dev \
  liblcms2-dev \
  libffi-dev \
  musl-dev \
  libopenjp2-7-dev \
  libssl-dev \
  libpango1.0-dev \
  poppler-utils \
  postgresql-client \
  libpq-dev \
  python3-dev \
  rustc \
  tcl-dev \
  libtiff5-dev \
  tk-dev \
  zlib1g-dev

RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"
RUN rustup update

RUN pip3 install cryptography
COPY ./ /DiscordBot
WORKDIR /DiscordBot
RUN pip3 install -r requirements.txt

CMD ["python3", "main.py"]