# PG-DCT — Kurulum ve kullanım (teknik rehber)

## 1. İndirme

```bash
git clone git@github.com:Cihan-Gedik/pg-dct.git
cd pg-dct
```

## 2. Kurulum (tek komut)

```bash
chmod +x install.sh scripts/expose-patroni-ports.sh scripts/register-docker-clusters.sh scripts/e2e-smoke.sh
./install.sh
```

- Docker varsa: container ile API
- Yoksa: `backend/.venv` + manuel `uvicorn`

## 3. Docker Patroni lab (AnyDBVer / logcollector)

Mac host, container bridge IP’lerine (`172.18.x`) doğrudan erişemez. Önce proxy:

```bash
./scripts/expose-patroni-ports.sh
```

Test:

```bash
curl -s http://127.0.0.1:18080/cluster | head -c 120
curl -s http://127.0.0.1:19080/cluster | head -c 120
```

## 4. API + UI başlatma

Terminal 1:

```bash
cd backend
source .venv/bin/activate
pip install -e ".[dev]"
cd ../ui && npm install && npm run build
cd ../backend
uvicorn app.main:app --reload --port 8080
```

Tarayıcı: **http://127.0.0.1:8080/ui/**

## 5. Cluster ekleme

Yöntem A — UI: **Settings** → Bootstrap Docker clusters

Yöntem B — API:

```bash
./scripts/register-docker-clusters.sh
```

Yöntem C:

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/bootstrap/docker
```

Kayıtlı cluster’lar `config/docker-clusters.yaml` dosyasından gelir:

| ID | Patroni (host) | Docker containers |
|----|----------------|-------------------|
| lc-pg-main | http://127.0.0.1:18080 | logcollector-cihangedik-node0..2 |
| lc-pg-vanilla | http://127.0.0.1:19080 | logcollector-dev-cihangedik-node0..2 |

Discover (node listesi):

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/clusters/lc-pg-main/discover
```

## 6. Tüm cluster logları çekilebilir mi?

**Evet (live tail).** API her node için `docker exec` ile şu kaynakları okur:

| Kaynak | Komut |
|--------|--------|
| patroni | `journalctl -u patroni` |
| postgres | PostgreSQL log dosyaları (tail) |
| etcd | `journalctl -u etcd` |
| os | `journalctl` (genel) |

Endpoint:

```bash
curl -s "http://127.0.0.1:8080/api/v1/clusters/lc-pg-main/logs?node=all&severity=critical,warning,info"
```

UI: **Live Monitor** veya **Lets Check Logs** — filtreler (cluster, node, severity, kaynak, search).

Gereksinimler:

- Docker CLI erişimi
- `config/docker-clusters.yaml` içinde `docker_hosts` eşlemesi
- İlgili container’lar çalışıyor olmalı

## 7. UI akışları

| Sayfa | İşlev |
|-------|--------|
| Dashboard | Cluster listesi |
| Live Monitor | Patroni live + 5s log refresh + filtreler |
| Lets Check Logs | Aynı log API, arşiv modu |
| Bundles | Faz 2 (manuel upload yakında) |
| Settings | Bootstrap / config bilgisi |

## 8. Test

```bash
make test
./scripts/e2e-smoke.sh
```

## 9. Geliştirme (UI hot reload)

```bash
# Terminal 1 — API
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8080

# Terminal 2 — UI dev
cd ui && npm run dev
# http://localhost:5173/ui/
```
