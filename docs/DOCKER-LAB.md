# Docker lab — copy/paste commands

Run each block separately. Do not copy comment lines that start with `#`.

## 1. Patroni port proxy

```bash
cd ~/Downloads/pg-dct
chmod +x scripts/expose-patroni-ports.sh
./scripts/expose-patroni-ports.sh
```

```bash
curl -s http://127.0.0.1:18080/cluster | head -c 200
curl -s http://127.0.0.1:19080/cluster | head -c 200
```

## 2. Start PG-DCT API

New terminal:

```bash
cd ~/Downloads/pg-dct/backend
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8080
```

## 3. Register clusters

Another terminal:

```bash
cd ~/Downloads/pg-dct
chmod +x scripts/register-docker-clusters.sh
./scripts/register-docker-clusters.sh
```

Or browser: http://127.0.0.1:8080/ui/ then click **Bootstrap Docker clusters**

## 4. Git pull (optional)

```bash
cd ~/Downloads/pg-dct
git pull
```

Do not paste `#` comment text on the same line as `git pull`.
