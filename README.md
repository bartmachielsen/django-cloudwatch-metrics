# Django Opensearch DSL signals


# Getting started
1. Start running opensearch:
```bash
docker run -p 9200:9200 -p 9600:9600 -e "discovery.type=single-node" --name opensearch-node -d opensearchproject/opensearch:latest
```