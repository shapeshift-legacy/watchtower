FROM golang:1.13

WORKDIR /go/src/monitor

# Add sops for secrets
RUN apt update && apt install -y wget build-essential awscli jq vim

COPY config ./config
COPY health-monitor .

RUN go get -d -v
RUN go install -v
