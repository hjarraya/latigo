FROM python:3.7-stretch
# apt-get and system utilities
RUN apt-get update && apt-get install -y curl apt-transport-https debconf-utils vim locales supervisor
RUN locale-gen en_US.UTF-8
RUN update-locale
WORKDIR /app
COPY app/requirements.txt ./
RUN pip install -r requirements.txt
COPY app/ .
COPY deploy/ ./deploy
RUN pwd
RUN find .
RUN python setup.py install
RUN chmod +x deploy/entrypoint.sh
CMD ["deploy/entrypoint.sh"]
