# Deployment

The bot is a long-running process: it needs a **persistent, always-on host** with
enough RAM for a local LLM. Recommended free option:

## Oracle Cloud Always Free (2 OCPU / 12 GB ARM) — $0/month

This is the only mainstream free tier big enough to run Ollama + the bot + the
dashboard 24/7. (As of 2026 the Always Free Ampere A1 allowance is **2 OCPU /
12 GB**; pick that during creation and you will never be charged.)

### 1. Provision a VM

1. Sign up at https://cloud.oracle.com (needs a card for identity verification,
   but Always Free usage stays at $0. Choose “Pay As You Go” upgrade if prompted
   for reliable capacity; Still-Free credits cover this instance).
2. **Create a VM instance**:
   - *Shape*: **VM.Standard.A1.Flex** (Ampere ARM), **2 OCPU / 12 GB memory**
   - *OS image*: **Ubuntu 22.04 or 24.04** (arm64)
   - *Boot volume*: default 47 GB (storage is free, 200 GB allowance)
   - *SSH*: upload/paste a public key (generate key pair for SSH)
3. **Firewall** — add an ingress rule in *Networking → VCN → Security Lists →
   Default Security List → Add Ingress Rules*: allow **TCP 8079** (IPv4) from
   `0.0.0.0/0`. SSH (22) is already open.
4. Note the instance's public IP.

### 2. Deploy (one command)

From your machine, SSH in and run the bootstrap:

```bash
ssh ubuntu@<SERVER_IP>
sudo bash -c 'curl -fsSL https://raw.githubusercontent.com/Mistledan/volvox-trader/main/deploy/install.sh | bash'
```

This installs Ollama + the model, clones the repo, sets up the venv, and
installs two systemd services that auto-start on boot.

### 3. Verify

```bash
sudo systemctl status volvox-bot        # autonomous loop
sudo systemctl status volvox-dashboard  # web UI
tail -f /opt/volvox-trader/logs/ai-trader.log
```

Dashboard: **http://<SERVER_IP>:8079**

### 4. Updates / restart

```bash
sudo bash /opt/volvox-trader/deploy/install.sh   # re-runs install, fresh clone+pip
# or just push code changes and:
cd /opt/volvox-trader && sudo -u volvox git pull && sudo -u volvox ./.venv/bin/pip install -e . --no-deps
sudo systemctl restart volvox-bot volvox-dashboard
```

### SSL / custom domain

Until then the dashboard is plain HTTP. When you want a domain, put [Caddy](https://caddyserver.com)
in front and proxy `:8079` with an automatic HTTPS certificate:

```caddyfile
volvox.example.com {
    reverse_proxy 127.0.0.1:8079
}
```

## Alternative: Docker

A Dockerfile (ARM/x86) that bundles Ollama + bot + dashboard is included:

```bash
docker build -t volvox-trader .
docker run -d -p 8079:8079 -v volvox-data:/app/logs volvox-trader
```

The paper state lives in `logs/paper_state.json` — mount `/app/logs` so it
survives container restarts.

## Why not Vercel?

Vercel (and most serverless) is unsuitable: the trading loop must run
continuously at a fixed cadence, and there is no persistent filesystem for the
paper portfolio. The platform needs to be a *host*, not a serverless function
runner. Paper mode means no real money is at risk while you trial it.