#!/usr/bin/python

# Copyright 2015 Joe Beda
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from subprocess import *
import yaml
import io
import logging
import os

CONFIG_FILE='/opt/config.yaml'
SYSLOG_FIFO='/var/log/syslog-fifo'

def main():
  global config

  logging.getLogger().setLevel(logging.INFO)
  logging.info('Reading config: %s' % CONFIG_FILE)
  with open(CONFIG_FILE, 'r') as f:
    config = yaml.load(f)

  spawn_rsyslogd()
  base_postfix_config()
  configure_postscreen()
  configure_sasl()
  configure_virtual_domains()
  spawn_postsrsd()
  spawn_postfix()

  # Wait for something to exit.  As soon as some child process exits we exit
  os.wait()

def spawn_rsyslogd():
  logging.info('')
  check_call(['mkfifo', SYSLOG_FIFO])
  with open('/etc/rsyslog.conf', 'w') as f:
    f.write(r"""
$ModLoad imuxsock
$template TraditionalFormatWithPRI,"%timegenerated:::date-rfc3339% %pri-text% %HOSTNAME% %syslogtag%%msg:::drop-last-lf%\n"
$WorkDirectory /var/spool/rsyslog
*.* |/var/log/syslog-fifo;TraditionalFormatWithPRI
""".strip())
  Popen(['cat', SYSLOG_FIFO])
  Popen(['rsyslogd', '-n'])

def base_postfix_config():
  # Set up the spool directory so it hass all of the right sub-dirs.
  check_call(['postfix', 'post-install', 'create-missing'])

  # Turn off all the chrooting in postfix. This only works for postfix v2.11+.
  # We grab that from wheezy-backports.
  check_call(['postconf', '-F', '*/*/chroot = n'])

  # Set up a virtual map (placeholder for now)
  check_call(['postconf', '-e', 'myhostname=%s' % config['ptr_hostname']])
  check_call(['postconf', '-e', 'local_recipient_maps='])
  check_call(['postconf', '-e', 'mydomain=localdomain'])
  check_call(['postconf', '-e', 'mydestination='])
  check_call(['postconf', '-e', ('message_size_limit = %d' % (50*1024*1024,))])

  # Enable TLS for smtpd
  check_call(['postconf', '-e', 'smtpd_tls_security_level=may'])
  check_call(['postconf', '-e', 'smtpd_tls_auth_only=yes'])

  # Configure the submission service (587)
  check_call(['postconf', '-Me', 'submission/inet = submission inet n - n - - smtpd'])
  check_call(['postconf', '-Pe', 'submission/inet/syslog_name=postfix/submission'])
  check_call(['postconf', '-Pe', 'submission/inet/smtpd_tls_security_level=encrypt'])
  check_call(['postconf', '-Pe', 'submission/inet/smtpd_sasl_auth_enable=yes'])
  check_call(['postconf', '-Pe', 'submission/inet/smtpd_reject_unlisted_recipient=no'])
  check_call(['postconf', '-Pe', 'submission/inet/smtpd_recipient_restrictions='])
  check_call(['postconf', '-Pe', 'submission/inet/smtpd_relay_restrictions=permit_sasl_authenticated,reject'])
  check_call(['postconf', '-Pe', 'submission/inet/milter_macro_daemon_name=ORIGINATING'])

def configure_postscreen():
  if not config['postscreen']['enable']:
    return

  check_call(['postconf', '-MX', 'smtp/inet'])
  check_call(['postconf', '-Me', 'smtpd/pass = smtpd pass - - n - - smtpd'])
  check_call(['postconf', '-Me', 'smtp/inet = smtp inet n - n - 1 postscreen'])
  check_call(['postconf', '-Me', 'tlsproxy/unix = tlsproxy unix - - n - 0 tlsproxy'])
  check_call(['postconf', '-Me', 'dnsblog/unix = dnsblog unix - - n - 0 dnsblog'])

  # Before-220 tests
  check_call(['postconf', '-e', 'postscreen_dnsbl_action = enforce'])
  check_call(['postconf', '-e', 'postscreen_dnsbl_threshold = 2'])
  check_call(['postconf', '-e', 'postscreen_dnsbl_sites = zen.spamhaus.org*2 bl.spamcop.net*1 b.barracudacentral.org*1 swl.spamhaus.org*-3'])

  check_call(['postconf', '-e', 'postscreen_greet_action = enforce'])

  if config['postscreen']['enable_slow_checks']:
    # After-220 tests -- these can cause significant delays so are disabled for now.
    check_call(['postconf', '-e', 'postscreen_bare_newline_action = enforce'])
    check_call(['postconf', '-e', 'postscreen_bare_newline_enable = yes'])
    check_call(['postconf', '-e', 'postscreen_non_smtp_command_enable = yes'])
    check_call(['postconf', '-e', 'postscreen_pipelining_enable = yes'])

def configure_sasl():
  check_call(['postconf', '-e', 'smtpd_sasl_type = cyrus'])
  check_call(['postconf', '-e', 'smtpd_sasl_auth_enable = yes'])
  check_call(['postconf', '-e', 'broken_sasl_auth_clients = yes'])
  check_call(['adduser', 'postfix', 'sasl'])
  with open('/etc/postfix/sasl/smtpd.conf', 'w') as f:
    f.write("""
pwcheck_method: auxprop
auxprop_plugin: sasldb
mech_list: PLAIN
""".strip())

  for (domain, accounts) in config['virtual_domains'].items():
    for account in accounts:
      logging.info("Creating SASL account for %s@%s" % (account['name'], domain))
      cmd = ['saslpasswd2', '-p', '-c', '-u', domain, account['name']]
      p = Popen(cmd, stdin=PIPE)
      p.communicate(input=account['password'])
      retcode = p.poll()
      if retcode:
        raise CalledProcessError(retcode, cmd)

def configure_virtual_domains():
  domains = config['virtual_domains'].keys()
  check_call(['postconf', '-e', 'virtual_alias_domains=%s' % ' '.join(domains)])
  check_call(['postconf', '-e', 'virtual_alias_maps=regexp:/etc/postfix/virtual.regexp hash:/etc/postfix/virtual'])
  with open('/etc/postfix/virtual', 'w') as f:
    for (domain, accounts) in config['virtual_domains'].items():
      for account in accounts:
        def forward(alias):
          logging.info("Forwarding %s@%s to %s" % (alias, domain, account['forward']))
          f.write('%s@%s %s\n' % (alias, domain, account['forward']))
        forward(account['name'])
        for alias in account.get('aliases', []):
          forward(alias)
      f.write('\n')
  check_call(['postmap', '/etc/postfix/virtual'])

  with open('/etc/postfix/virtual.regexp', 'w') as f:
    for (domain, accounts) in config['virtual_domains'].items():
      for account in accounts:
        if account.get('dot_plus_rewrite', True):
          name = account['name']
          forward_account, forward_domain = account['forward'].split('@')
          logging.info("Forwarding %s.*@%s to %s+*@%s" % (name, domain, forward_account, forward_domain))
          f.write('/^%s((\\+|\\.)([-a-zA-Z0-9_]+))?@%s$/ %s+$3@%s\n' % (name, domain, forward_account, forward_domain))

def spawn_postsrsd():
  if not config['srs']['enable']:
    return

  check_call(['postconf', '-e', 'sender_canonical_maps = tcp:127.0.0.1:10001'])
  check_call(['postconf', '-e', 'sender_canonical_classes = envelope_sender'])
  check_call(['postconf', '-e', 'recipient_canonical_maps = tcp:127.0.0.1:10002'])
  check_call(['postconf', '-e', 'recipient_canonical_classes = envelope_recipient,header_recipient'])

  with open('/opt/srs.secret', 'w') as f:
    f.write(config['srs_secret'])

  Popen(['postsrsd-1.2/build/postsrsd', '-s/opt/srs.secret', '-upostfix', '-d%s' % config['srs_domain']])

def spawn_postfix():
  # Start up the postfix master in the foreground.  Normally this happens with:
  #   /etc/init.d/postfix start ->
  #   /usr/sbin/postfix ->
  #   /usr/lib/postfix/postfix-script ->
  #   /usr/lib/postfix/master
  #
  # The only thing I can figure that *really* matters here is that we change the
  # working directory to the spool directory.  I might be missing some env
  # variables :/
  os.chdir('/var/spool/postfix')
  Popen(['/usr/lib/postfix/master', '-d'])


if __name__ == "__main__":
  main()