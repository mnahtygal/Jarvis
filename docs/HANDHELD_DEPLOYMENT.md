# Jarvis Handheld HTTPS Deployment

This runbook deploys the v0.4 handheld API behind a narrow HTTPS boundary on
Thor. It is intentionally staged: validate TLS and Nginx before restarting the
API with its loopback-only bind, and change the firewall last.

The deployed LAN surface is limited to:

- `GET /health`, which remains unauthenticated.
- `POST /handheld/v1/chat`, which requires the dedicated bearer token.

Nginx returns `405` for the wrong method on either approved path and `404` for
all other paths. Existing Jarvis routes remain available locally through
`127.0.0.1:5000`; Nginx does not expose them.

## Prerequisites and trust boundary

Thor must retain its router DHCP reservation for `10.0.0.213`. The server
certificate is valid for the IP address only when its Subject Alternative Name
contains `IP:10.0.0.213`. Do not rely on the certificate Common Name or on an
unverified local hostname.

The trust boundary is:

```text
ESP32 -- HTTPS + bearer token --> Nginx :443
                                      |
                                      +--> GET 127.0.0.1:5000/health
                                      +--> POST 127.0.0.1:5000/handheld/v1/chat

Thor-local clients -----------------> Flask 127.0.0.1:5000 (all local routes)
```

TLS authenticates Thor and encrypts the connection. The bearer token
authenticates the handheld endpoint. Possession of extracted ESP32 firmware may
allow recovery of the token and public CA certificate, so the token must be
dedicated, revocable, and never reused for another service.

This deployment does not add port forwarding, a DMZ, remote access, or public
Internet exposure.

## Deployed artifacts

Create backups under a timestamped, root-only directory before replacing any
deployed configuration.

| Artifact | Deployed location | Owner and mode |
| --- | --- | --- |
| CA private key while signing | `/root/.local/share/jarvis-pki/private/jarvis-handheld-ca.key` | `root:root`, `0600`; move offline afterward |
| Public CA certificate | `/etc/jarvis/pki/ca/jarvis-handheld-ca.crt` | `root:root`, `0644` |
| Server certificate | `/etc/jarvis/pki/certs/jarvis-handheld-server.crt` | `root:root`, `0644` |
| Server private key | `/etc/jarvis/pki/private/jarvis-handheld-server.key` | `root:root`, `0600` |
| API environment | `/etc/jarvis/jarvis-api.env` | `root:root`, `0600` |
| Systemd drop-in | `/etc/systemd/system/jarvis-api.service.d/10-handheld-env.conf` | `root:root`, `0644` |
| Nginx site | `/etc/nginx/sites-available/jarvis-handheld` | `root:root`, `0644` |
| Enabled Nginx site | `/etc/nginx/sites-enabled/jarvis-handheld` symlink | root-managed |
| Backups | `/var/backups/jarvis-handheld/<timestamp>/` | `root:root`, `0700` |

The ESP32 receives only the public CA certificate and its matching dedicated
token through ignored local configuration. It must never receive the CA private
key or server private key.

Never commit the CA private key, server private key, token, deployed environment
file, deployed Nginx configuration, certificate material, or ESP32 local
configuration. The files under `deploy/` and `config/jarvis-api.env.example` are
value-free tracked templates.

## Certificate requirements

Use a private local CA held offline where practical. Issue a Thor server
certificate with:

- RSA 2048-bit key.
- SHA-256 signature.
- `subjectAltName = IP:10.0.0.213`.
- `extendedKeyUsage = serverAuth`.
- `keyUsage = digitalSignature,keyEncipherment`.
- A documented, bounded validity period and renewal date.

Verify the resulting public certificates without displaying private-key data:

```bash
openssl verify \
  -CAfile /etc/jarvis/pki/ca/jarvis-handheld-ca.crt \
  /etc/jarvis/pki/certs/jarvis-handheld-server.crt
openssl x509 \
  -in /etc/jarvis/pki/certs/jarvis-handheld-server.crt \
  -noout -checkend 2592000
openssl x509 \
  -in /etc/jarvis/pki/certs/jarvis-handheld-server.crt \
  -noout -ext subjectAltName
```

The final command must report the reserved IP SAN. Move the CA private key to
offline storage after signing.

## Back up current deployment state

Keep an existing SSH session open throughout deployment, and verify a second
SSH login before any UFW work.

```bash
stamp="$(date +%Y%m%d-%H%M%S)"
backup="/var/backups/jarvis-handheld/$stamp"
sudo install -d -o root -g root -m 0700 "$backup"
sudo cp -a /etc/systemd/system/jarvis-api.service "$backup/"
sudo cp -a /etc/systemd/system/jarvis-llama.service "$backup/"
sudo cp -a /etc/ufw "$backup/ufw"
sudo ufw status verbose | sudo tee "$backup/ufw-status.txt" >/dev/null
sudo ufw status numbered | sudo tee "$backup/ufw-numbered.txt" >/dev/null
```

After Nginx is installed, back it up before changing sites:

```bash
sudo cp -a /etc/nginx "$backup/nginx"
```

## Generate the API environment without displaying the token

Do not use `set -x`, `echo`, `cat`, or a command-line argument containing the
token. The following creates a mode-0600 staging file and writes OpenSSL output
directly into it:

```bash
umask 077
token_staging="$(mktemp)"
{
  printf 'JARVIS_HANDHELD_TOKEN='
  openssl rand -hex 32
  printf 'JARVIS_API_BIND_HOST=127.0.0.1\n'
} > "$token_staging"
sudo install -o root -g root -m 0600 "$token_staging" /etc/jarvis/jarvis-api.env
shred -u "$token_staging"
```

Transfer the matching token to the ESP32 ignored local configuration through a
private local workflow. Do not paste it into a terminal transcript, issue,
commit, documentation, or chat conversation.

Install the systemd drop-in without restarting the API yet:

```bash
sudo install -d -o root -g root -m 0755 \
  /etc/systemd/system/jarvis-api.service.d
sudo install -o root -g root -m 0644 \
  deploy/systemd/jarvis-api.service.d/10-handheld-env.conf.example \
  /etc/systemd/system/jarvis-api.service.d/10-handheld-env.conf
sudo systemctl daemon-reload
```

## Install and validate Nginx first

Installation requires separate runtime-change approval:

```bash
sudo apt-get update
sudo apt-get install --yes nginx
sudo systemctl disable --now nginx
sudo cp -a /etc/nginx "$backup/nginx"
```

Install the site and disable the distribution default only after preserving the
backup:

```bash
sudo install -o root -g root -m 0644 \
  deploy/nginx/jarvis-handheld.conf.example \
  /etc/nginx/sites-available/jarvis-handheld
sudo ln -s /etc/nginx/sites-available/jarvis-handheld \
  /etc/nginx/sites-enabled/jarvis-handheld
sudo unlink /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable --now nginx
```

Nginx must validate and serve TLS successfully while Flask is still reachable
under its pre-deployment bind. Test the narrow boundary using the public CA:

```bash
curl --fail --cacert /etc/jarvis/pki/ca/jarvis-handheld-ca.crt \
  https://10.0.0.213/health
```

The response must remain exactly `{"status":"ok"}`.

Confirm that non-approved routes are rejected:

```bash
curl --cacert /etc/jarvis/pki/ca/jarvis-handheld-ca.crt \
  --output /dev/null --write-out '%{http_code}\n' https://10.0.0.213/
curl --cacert /etc/jarvis/pki/ca/jarvis-handheld-ca.crt \
  --output /dev/null --write-out '%{http_code}\n' https://10.0.0.213/text
curl --cacert /etc/jarvis/pki/ca/jarvis-handheld-ca.crt \
  --output /dev/null --write-out '%{http_code}\n' https://10.0.0.213/api/status/dashboard
```

Each must return `404`. A `POST` to `/health` and a `GET` to
`/handheld/v1/chat` must return `405`. An unauthenticated chat request must
return `401` without reaching the model.

### Authenticated chat test

Run an authenticated live-model request only after explicit approval of a
harmless prompt. Avoid placing the token in the command line or printing it by
using a root-only temporary curl configuration:

```bash
sudo sh -c '
  set -a
  . /etc/jarvis/jarvis-api.env
  set +a
  umask 077
  cfg="$(mktemp /run/jarvis-handheld-curl.XXXXXX)"
  {
    printf "url = \"https://10.0.0.213/handheld/v1/chat\"\n"
    printf "request = \"POST\"\n"
    printf "cacert = \"/etc/jarvis/pki/ca/jarvis-handheld-ca.crt\"\n"
    printf "header = \"Authorization: Bearer %s\"\n" "$JARVIS_HANDHELD_TOKEN"
    printf "header = \"Content-Type: application/json\"\n"
    printf "data = \"{\\\"prompt\\\":\\\"APPROVED HARMLESS TEST\\\"}\"\n"
  } > "$cfg"
  curl --config "$cfg"
  result=$?
  shred -u "$cfg"
  exit "$result"
'
```

Do not retain the temporary curl configuration or copy its contents into logs.

## Activate Flask loopback binding

Only after the proxy passes all preceding checks, restart the API so systemd
loads the protected environment file and the tracked loopback default:

```bash
sudo systemctl restart jarvis-api.service
systemctl is-active jarvis-api.service
ss -ltnp '( sport = :5000 )'
curl --fail http://127.0.0.1:5000/health
curl --fail --cacert /etc/jarvis/pki/ca/jarvis-handheld-ca.crt \
  https://10.0.0.213/health
```

Port 5000 must appear only on `127.0.0.1` or another explicitly approved
loopback address. Existing local routes remain reachable from Thor at
`127.0.0.1:5000`.

## Vite and llama.cpp follow-up

The Vite UI on port 5173 and text llama.cpp on port 8080 must also be rebound to
loopback before claiming Nginx is the sole LAN boundary. The vision service is
already on loopback and should remain unchanged. Treat each bind change as a
separate, backed-up runtime change and verify its local consumer before moving
to the next one.

If those rebinds are deferred, UFW must deny LAN access to ports 5000, 5173,
8080, and 8081.

## Configure UFW last

UFW is currently inactive. Review proposed rules without exposing SSH access:

```bash
sudo ufw status verbose
sudo ufw status numbered
```

Before enabling UFW, determine Thor's effective SSH port without assuming the
default and add an allowance for that verified port. Confirm the rule is
present, and keep two verified SSH sessions open. Then permit HTTPS from the
smallest practical source scope. If the handheld does not have a reserved
address, the local `/24` is the broader fallback:

```bash
sudo sshd -T | awk '$1 == "port" { print $1, $2 }'
sudo ufw allow in on enP2p1s0 to any port <VERIFIED_SSH_PORT> proto tcp \
  comment 'Thor SSH'
sudo ufw allow in on enP2p1s0 from 10.0.0.0/24 \
  to any port 443 proto tcp comment 'Jarvis handheld HTTPS'
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw enable
sudo ufw status verbose
```

Do not allow ports 80, 5000, 5173, 8080, or 8081. Prefer replacing the `/24`
allowance with the handheld's reserved address when one is available.

## Rollback

Rollback in reverse order. Keep UFW and SSH access under direct observation.

1. UFW: use `sudo ufw status numbered`, delete only the newly added HTTPS rule,
   restore each recorded prior rule by its original specification, and disable
   UFW if it was inactive before this deployment. Never delete the SSH rule.
2. Loopback changes: restore the backed-up service/start configuration and
   restart only the affected service. For an API emergency, revert the bind
   change before restarting; do not leave a wildcard listener exposed without
   firewall protection.
3. API environment: restore or remove the systemd drop-in, run
   `sudo systemctl daemon-reload`, and restart `jarvis-api.service`. Move the
   protected environment file into the root-only backup rather than displaying
   it.
4. Nginx: run `sudo systemctl disable --now nginx`, restore the complete backed
   up `/etc/nginx` tree, run `sudo nginx -t`, then start it only if it was active
   before deployment.
5. Certificates: stop Nginx before moving the newly deployed certificates and
   keys into the root-only backup. If the CA was added to system trust, remove
   only that CA copy and run `sudo update-ca-certificates`.

After rollback, compare listeners, service states, Git HEAD, and UFW rules with
the recorded pre-deployment state.
