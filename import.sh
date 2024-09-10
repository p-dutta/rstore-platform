#!/usr/bin/env bash
set -e

docker-compose up -d db
sleep 5
docker cp db_saleor.sql rstore-platform_db_1:/home
docker exec -it rstore-platform_db_1 psql -U saleor -f /home/db_saleor.sql