import fabric.api


def serve():
    fabric.api.local('python manage.py runserver')


def test():
    fabric.api.local('coverage run manage.py test')


def coverage():
    fabric.api.local('coverage run manage.py test')
    fabric.api.local('coverage html')
    fabric.api.local('open coverage_html_report/index.html')


def redis():
    fabric.api.local('redis-server --daemonize yes --port 6380')
    fabric.api.local('redis-cli -p 6380 monitor')


def celery_scheduler():
    fabric.api.local('mkdir -p .celery/processes && celery -A watchtower beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler --pidfile=.celery/processes/scheduler.pid')  # noqa


def celery_workers():
    fabric.api.local('mkdir -p .celery/processes && mkdir -p .celery/worker_logs && celery -A watchtower worker -l info --logfile=.celery/worker_logs/%n%I.log --pidfile=.celery/processes/%n%I.pid')  # noqa


def celery_monitor():
    fabric.api.local('celery -A watchtower events -l info --camera django_celery_monitor.camera.Camera --frequency=2.0')  # noqa


def celery_purge():
    fabric.api.local('celery -A watchtower purge')


def celery_dashboard():
    fabric.api.local('celery -A watchtower flower --port=5555 --persistent=True --db=flower --broker=redis://redis:6379/0 --broker_api=redis://redis:6379/0') # noqa

def celery_kill_workers():
    fabric.api.local('pkill -f "celery worker"')
