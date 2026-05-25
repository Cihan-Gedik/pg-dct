# Docker lab — copy/paste commands

Run each block separately. Do not copy comment lines that start with `#`.

## 0. etcd `connection refused` on 172.18.0.2:2380

Bu log, **node0** üzerinde `etcd` / `patroni` servisleri kapalıyken diğer node’ların peer’a bağlanamamasından gelir.

```bash
chmod +x scripts/heal-lab-node.sh
./scripts/heal-lab-node.sh logcollector-cihangedik-node0
./scripts/expose-patroni-ports.sh
```

PG-DCT log API varsayılan olarak bu satırları down peer için filtreler (`suppress_peer_noise=true`).

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
