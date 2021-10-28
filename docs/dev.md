# Dev flow

Manage Configuration:

* Read stage sops
* Update local configs

config notes:
    Local uses .env file

Manage tasks:
```
watchtower/settings/base.py
```

CELERY_BEAT_SCHEDULE:
    Target asset you with to develop on

Comment out all tasks but target asset

YOU MUST LEAVE BTC ON! (I think)

start
```
docker-compose up -d
```

note: (if you cant find watchtower_watchtower remove -d and check logs for error)

stop
```
docker-compose down -v
```

## list

```
docker container ls
```

```
CONTAINER ID        IMAGE
df9fb1c93791        watchtower_watchtower  
```

get container id

## Logging

```
docker logs df9fb1c93791 -f
```

