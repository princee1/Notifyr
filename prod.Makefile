celery_app = app.task.celery_app

###############################      CELERY                     #######################################
celery-docker:
	celery -A ${celery_app} worker --pool=gevent --concurrency=100  --loglevel=info --max-tasks-per-child=2000 --max-memory-per-child=200000

flower:
	celery -A ${celery_app} flower --port=5555

redbeat:
	celery -A ${celery_app} beat -S redbeat.RedBeatScheduler --max-interval 30 --loglevel=info

###############################     HTTPS               #######################################

https_pem:
	openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes

################################     VIRTUAL ENVIRONNEMENT            ###################################

venv:
	python -m venv .venv
	python -m pip install --upgrade pip
	pip install -r requirements_dev.txt

install	:
	pip install -r requirements_dev.txt
