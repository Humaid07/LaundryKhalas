# Postgres image with PostGIS + pgvector + uuid-ossp available.
# Base image already ships PostGIS; we add the pgvector extension package
# from the same PGDG apt repo the postgis image is built from.
FROM postgis/postgis:16-3.4

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
