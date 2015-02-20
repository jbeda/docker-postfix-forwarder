# docker-postfix-forwarder

This is the start of a Docker container that will forward mail using postfix.

The container will support acting as an MTA for outgoing mail from that forwarded address and will implement SRS so that all forwarded messages will be trusted.

## DNS records

For each domain you want to forward, set something like this:

name | type | value
-----|------|------
mail.example.com | A | x.x.x.x
example.com | MX | 1 mail.example.com.
example.com | TXT | "v=spf1 mx ~all"

For the one domain that you'll use for SRS, do this:

name | type | value
-----|------|------
srs.example.com | MX | 1 mail.example.com.
srs.example.com | TXT | "v=spf1 mx ~all"

## Config file

Copy `config.example.yaml` to `config.yaml` and edit as appropriate.  There are comments on each value.

## Build/upload

If you are using the Google Cloud Registry, simply run `make upload-gcr`.  This will build and upload the Docker image to a private registry.

**DO NOT** push this image to a public registry and it has sensitive information (passwords).

## Run

To run the image, do something like this:

```bash
sudo mkdir /opt/postfix-forwarder
GCEPROJECT=$(gcloud config -q --format text list project | cut -d ' ' -f 2 | tr - _)
gcloud docker pull gcr.io/$GCEPROJECT/postfix-forwarder
docker run --name postfix \
  -v /opt/postfix-forwarder:/var/spool/postfix \
  -p 587:587 -p 25:25 \
  -d gcr.io/$GCEPROJECT/postfix-forwarder
```

As all of the important data is stored in a host volume, you kill/delete/restart the container as necessary to change configuration.  Note that the account IDs used in the container (for the `postfix` user, and `postfix` and `postdrop` groups) won't line up with your host system so if you back up this directory (using tar or whatever) use numeric IDs.

## Configuring GMail

If you are using GMail, you can configure it to send mail through this account.  To do that:

1. Go to "Settings" and then "Accounts and Import"
2. Click on "Add another email address you own"
3. Enter the full email address: `user@example.com` and click "Next Step"
4. Set up the SMTP server:
  1. Set the SMTP server to `mail.example.com` and the port to `587`.
  2. Set the username to the full email address (not just the user part): `user@example.com`
  3. Enter your password for this account
  4. Select "Secure connection using TLS"
  5. Click "Add Account"
5. Click on the verify link as it is sent.  This might get directed to spam.

## Gotcha: Logging

Everything from the postfix install will be output to stdout and logged with Docker.  This means that `docker logs postfix` will give you some good info.  But, unfortunately, those logs are never truncated or rotated.  Eventually they will fill up your disk and bad stuff will happen.

If you are running logrotate on the host system, you truncate/rotate logs by dropping this file in `/etc/logrotate.d/docker`:

```
/var/lib/docker/containers/*/*-json.log {
    rotate 5
    copytruncate
    missingok
    notifempty
    compress
    maxsize 10M
    daily
    create 0644 root root
}
```

No guarantees here as this is a bit of a hack.  This is a big hole in Docker right now.  If things are logging fast, the `copytruncate` directive may miss some log lines.

## TODOs

* [ ] Figure out DKIM
* [ ] More flexibilty in rewriting/aliases

## References

A lot of Google-ing was done to get to this point.  However, this seemed to be the most relevant article: http://seasonofcode.com/posts/setting-up-dkim-and-srs-in-postfix.html