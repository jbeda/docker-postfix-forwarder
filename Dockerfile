FROM buildpack-deps:wheezy-scm
MAINTAINER Joe Beda

RUN echo "deb http://http.debian.net/debian wheezy-backports main" >>/etc/apt/sources.list
RUN apt-get update \
  && apt-get -t wheezy-backports install -y --no-install-recommends \
    sasl2-bin \
    postfix \  
    opendkim \
    opendkim-tools \
  && rm -rf /var/lib/apt/lists/*

 ADD . /opt
