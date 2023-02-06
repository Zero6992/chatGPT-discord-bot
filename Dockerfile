FROM python:3.10-alpine

ENV PYTHONUNBUFFERED 1
RUN apk add --update \
  build-base \
  cairo \
  cairo-dev \
  cargo \
  freetype-dev \
  gcc \
  gdk-pixbuf-dev \
  gettext \
  jpeg-dev \
  lcms2-dev \
  libffi-dev \
  musl-dev \
  openjpeg-dev \
  openssl-dev \
  pango-dev \
  poppler-utils \
  postgresql-client \
  postgresql-dev \
  py-cffi \
  python3-dev \
  rust \
  tcl-dev \
  tiff-dev \
  tk-dev \
  zlib-dev

RUN pip install cryptography

COPY ./ /DiscordBot
WORKDIR /DiscordBot
RUN pip3 install -r requirements.txt


CMD ["python3", "main.py"]