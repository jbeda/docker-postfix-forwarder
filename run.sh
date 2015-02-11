#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

# Set up syslog to dump everything to stdout.  We do this by having rsyslogd
# send everything to a fifo and then just cat that fifo.
mkfifo /var/log/syslog-fifo
cat '*.* |/var/log/syslog-fifo' >/etc/rsyslog.conf &
rsyslogd -n &

# Turn off all the chrooting in postfix. This only works for postfix v2.11+.
# We grab that from wheezy-backports.
postconf -F '*/*/chroot = n'

# Start up the postfix master in the foreground.  Normally this happens with:
#   /etc/init.d/postfix start ->
#   /usr/sbin/postfix ->
#   /usr/lib/postfix/postfix-script ->
#   /usr/lib/postfix/master
#
# The only thing I can figure that *really* matters here is that we change the
# working directory to the spool directory.  I might be missing some env
# variables :/
cd /var/spool/postfix
/usr/lib/postfix/master -d