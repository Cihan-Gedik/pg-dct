# Patroni switchover (Docker lab) — komutlar

**PG-DCT bu komutları çalıştırmaz.** Sadece senin terminalinde, test ortamında kullan.

Switchover leader değiştirir. Sabit IP ile PostgreSQL’e bağlanan uygulamalar etkilenir. Önce Patroni proxy’nin ayakta olduğundan emin ol.

## Ön hazırlık

```bash
cd ~/Downloads/pg-dct
./scripts/expose-patroni-ports.sh
```

## 1. Mevcut leader’ı gör

**lc-pg-main** (port 18080):

```bash
curl -s http://127.0.0.1:18080/cluster | python3 -m json.tool
```

**lc-pg-vanilla** (port 19080):

```bash
curl -s http://127.0.0.1:19080/cluster | python3 -m json.tool
```

`role: leader` olan satırdaki `name` = mevcut leader.

## 2. Switchover (REST)

`LEADER` ve `CANDIDATE` değerlerini bir önceki çıktıdan al.

**lc-pg-main** örneği:

```bash
curl -s -X POST http://127.0.0.1:18080/switchover \
  -H 'Content-Type: application/json' \
  -d '{"leader":"LEADER_NAME","candidate":"REPLICA_NAME"}'
```

**lc-pg-vanilla** örneği:

```bash
curl -s -X POST http://127.0.0.1:19080/switchover \
  -H 'Content-Type: application/json' \
  -d '{"leader":"LEADER_NAME","candidate":"REPLICA_NAME"}'
```

Başarı: `Successfully switched over to "..."`

## 3. Leader değiştiyse proxy’yi yenile

Host proxy sabit IP’ye bağlı kalabilir; switchover sonrası:

```bash
./scripts/expose-patroni-ports.sh
```

## 4. PG-DCT’de discover (opsiyonel)

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/clusters/lc-pg-main/discover
curl -s -X POST http://127.0.0.1:8080/api/v1/clusters/lc-pg-vanilla/discover
```

## 5. Geri almak (eski leader’a)

Yine `cluster` çıktısına bak; leader ve candidate’i ters çevir:

```bash
curl -s -X POST http://127.0.0.1:18080/switchover \
  -H 'Content-Type: application/json' \
  -d '{"leader":"CURRENT_LEADER","candidate":"OLD_LEADER"}'
```

## Container içinden (alternatif)

```bash
docker exec -it logcollector-cihangedik-node0 patronictl list
docker exec -it logcollector-cihangedik-node0 patronictl switchover
```

Vanilla cluster için container adı: `logcollector-dev-cihangedik-node0`.
