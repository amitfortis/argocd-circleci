FROM python:3.10-slim

WORKDIR /app

COPY ./requirements.txt .

RUN pip install --no-cache-dir --upgrade -r requirements.txt  

ADD web-project.tar.gz .

RUN mkdir -p /var/log/flask /var/log/gunicorn &&  chmod -R 755 /var/log/flask /var/log/gunicorn 

EXPOSE 5000

WORKDIR /app/web-project

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "wsgi:application"]


