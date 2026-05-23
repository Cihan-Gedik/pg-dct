# PG-DCT — Kurulum ve ilk test

## Gereksinimler

| Yol | Gereksinim |
|-----|------------|
| **Önerilen** | Docker + Docker Compose |
| Alternatif | Python 3.11+ |

## 1. İndir

```bash
git clone https://github.com/<org>/pg-dct.git
cd pg-dct
```

## 2. Kur (tek komut)

```bash
chmod +x install.sh scripts/smoke.sh
./install.sh
```

veya:

```bash
make install
```

Docker varsa API otomatik ayağa kalkar. Yoksa `backend/.venv` hazırlanır; terminalde gösterilen `uvicorn` komutunu çalıştırın.

## 3. Smoke test

```bash
make smoke
# veya
./scripts/smoke.sh
```

Beklenen: `/health` → `ok`, `/api/v1/clusters` → `[]`

## 4. Docker lab (AnyDBVer / logcollector)

Mac host genelde `172.18.x:8008` adresine **doğrudan erişemez** (timeout). Önce port proxy:

```bash
chmod +x scripts/expose-patroni-ports.sh
./scripts/expose-patroni-ports.sh
curl -s http://127.0.0.1:18080/cluster | head
curl -s http://127.0.0.1:19080/cluster | head
```

| ID | Seed Patroni (host) | Containers |
|----|---------------------|------------|
| `lc-pg-main` | http://127.0.0.1:18080 | logcollector-cihangedik-node* |
| `lc-pg-vanilla` | http://127.0.0.1:19080 | logcollector-dev-cihangedik-node* |

API çalışırken:

```bash
chmod +x scripts/register-docker-clusters.sh
./scripts/register-docker-clusters.sh
```

veya tarayıcıdan: http://127.0.0.1:8080/ui/ → **Bootstrap Docker clusters**

veya:

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/bootstrap/docker | python3 -m json.tool
```

Patroni’ye Mac’ten erişim için container’ların ayakta olduğunu doğrulayın:

```bash
curl -s http://172.18.0.2:8008/cluster | head
```

## 5. İlk cluster (manuel, Patroni erişimi olan ortamda)

```bash
export PGDCT_PORT=8080

curl -s -X POST "http://127.0.0.1:${PGDCT_PORT}/api/v1/clusters" \
  -H 'Content-Type: application/json' \
  -d '{
    "id": "prod-ha",
    "name": "prod-ha",
    "patroni_seed_url": "http://YOUR_PATRONI_HOST:8008",
    "poll_interval_sec": 5
  }'

curl -s -X POST "http://127.0.0.1:${PGDCT_PORT}/api/v1/clusters/prod-ha/discover" | jq .
```

Patroni yoksa sadece cluster kaydı oluşur; `discover` 502 döner — bu normaldir, API çalışıyor demektir.

## Günlük komutlar

| Komut | Açıklama |
|-------|----------|
| `make up` | Docker ile başlat |
| `make down` | Durdur |
| `make logs` | API logları |
| `make test` | Unit testler (CI ile aynı) |
| `make dev` | Lokal uvicorn (venv gerekir) |

## Sorun giderme

- **Port meşgul:** `.env` içinde `PGDCT_PORT=8081` ve `docker compose up -d`
- **Docker sağlıksız:** `docker compose logs api`
- **Lokal DB:** `backend/data/pgdct.db` — silmek için `make clean` (dikkat: veri gider)

## Sonraki adımlar (geliştirme)

1. Settings UI — cluster ekleme formu  
2. Live Monitor — poller + log tail  
3. Lets Check Logs — bundle upload  

English summary: run `./install.sh`, then `make smoke`, then register a cluster via `/docs`.
