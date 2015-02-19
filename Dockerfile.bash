FROM postfix-forwarder-base
MAINTAINER Joe Beda

RUN apt-get update && apt-get install -y --no-install-recommends \
    less \
    man \
    emacs23-nox \
    procps

ENV TERM=xterm
ADD . /opt

