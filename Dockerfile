# 1. Install Nginx based image for ease of deployment for the application
FROM debian:12
# 2. Environment variable to avoid creation of compiled binaries in python
ENV PYTHONDONTWRITEBYTECODE=1
RUN mkdir -p /usr/local/code_repo/logs
# 3. Update package manager and install PIP, Supervisor, Python venv packages
RUN apt-get update && apt-get install -y python3-pip supervisor python3-venv
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 11
# 3.1 Install dependencies for MYSQL
RUN apt-get install python3-dev default-libmysqlclient-dev build-essential -y
RUN apt-get install -y \
    libtiff5-dev \
    libjpeg62-turbo-dev \
    libopenjp2-7-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    tcl8.6-dev \
    tk8.6-dev \
    python3-tk \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1-dev

# Create a virtual environment and activate it
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

# 4. Install fundamental package requirements for developing Django applications
COPY requirements.txt /tmp/pip-tmp/
RUN pip3 --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt \
    && rm -rf /tmp/pip-tmp

# 6.0 Copy Nginx configuration file
COPY ./installation/etc_nginx_config.conf /etc/nginx/nginx.conf
COPY ./installation/app_nginx_config.conf /etc/nginx/sites-enabled

# 6.1 Copy gunicorn configuration file to be run by supervisor
COPY ./installation/app_supervisor_config.conf /etc/supervisor/conf.d

# 7. Copy source code
COPY . /usr/local/code_repo/
WORKDIR /usr/local/code_repo

# Ensure you use the Python binary from venv
RUN /venv/bin/python manage.py collectstatic --noinput

EXPOSE 80
CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]

