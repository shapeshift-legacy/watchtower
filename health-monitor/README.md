# Watchtower Health Monitor
Monitors watchtower block ingesters to ensure they do not fall too far behind coinquery.  Alerting is handled through Datadog log monitors

## Development

### Build Image

From root watchtower directory:

```
docker build  -f ./health-monitor/Dockerfile -t wt-monitor .
```

### Run Monitor

```
docker run -e "MONITOR_WATCHTOWER_BASE_URL=https://watchtower.staging..../api/v1/" -e "ENV=staging" -e "COSMOS_GAIACLI_URL=https://cosmos-203.cointainers...." wt-monitor monitor
```
