#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

curl -Lso postsrsd.tar.gz https://github.com/roehling/postsrsd/archive/1.2.tar.gz
tar xzf postsrsd.tar.gz
make -C postsrsd-1.2
