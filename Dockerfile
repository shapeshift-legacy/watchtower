FROM python:3.7.3

LABEL maintainer="ShapeShift.io"

ENV DOCKERIZE_VERSION v0.6.1
RUN wget https://github.com/jwilder/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && tar -C /usr/local/bin -xzvf dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && rm dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz

# Add sops for secrets
RUN apt update && apt install -y wget build-essential awscli jq vim

# Set the working directory to /watchtower
WORKDIR /watchtower

COPY requirements.txt .

# Install app dependencies
#RUN pip install pip --upgrade
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
