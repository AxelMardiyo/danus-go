# DanusGo: pintasan perintah. Butuh Docker + GNU Make.
-include .env
export

DB_USER ?= danusgo
DB_NAME ?= danusgo
DC      = docker compose
PSQL    = $(DC) exec -T db psql -U $(DB_USER) -d $(DB_NAME) -v ON_ERROR_STOP=1

.PHONY: help up down reset psql logs indexes indexes-drop tools crash wal ps

help:
	@echo "make up            nyalakan database (init otomatis bila volume kosong)"
	@echo "make down          matikan (data tetap)"
	@echo "make reset         HAPUS data lalu bangun ulang dari 01/02/06"
	@echo "make psql          masuk psql interaktif"
	@echo "make indexes       terapkan db/04_indexes.sql (Bab 5)"
	@echo "make indexes-drop  lepas indeks buatan (ukur kondisi tanpa indeks)"
	@echo "make tools         jalankan pgAdmin di http://localhost:5050"
	@echo "make crash         matikan paksa DB (SIGKILL), demo Bab 4"
	@echo "make wal           tampilkan 40 record terakhir pg_waldump"

up:
	$(DC) up -d db
	@$(DC) ps

down:
	$(DC) down

reset:
	$(DC) down -v
	$(DC) up -d db

ps:
	$(DC) ps

psql:
	$(DC) exec db psql -U $(DB_USER) -d $(DB_NAME)

logs:
	$(DC) logs -f db

indexes:
	$(PSQL) < db/04_indexes.sql

indexes-drop:
	$(PSQL) < db/04_indexes_drop.sql

tools:
	$(DC) --profile tools up -d pgadmin

# Demo crash: SIGKILL ke proses utama = postmaster mati tanpa shutdown bersih.
# Setelah itu: make up, lalu make logs untuk membaca log recovery.
crash:
	$(DC) kill -s KILL db

wal:
	$(DC) exec -u postgres db bash -c 'cd /var/lib/postgresql/data/pg_wal && pg_waldump -p . $$(ls | grep -E "^[0-9A-F]{24}$$" | tail -1) 2>&1 | tail -n 40'
