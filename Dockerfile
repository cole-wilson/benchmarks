FROM python:3.8.2-alpine

RUN apk update && apk upgrade && \
    apk add --no-cache make g++ bash git openssh curl
RUN apk update \
    && apk add --virtual build-deps gcc python3-dev musl-dev \
    && apk del build-deps

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY ./requirements.txt /usr/src/app/
WORKDIR /tmp
RUN wget http://download.osgeo.org/libspatialindex/spatialindex-src-1.8.5.tar.gz && \
  tar -xvzf spatialindex-src-1.8.5.tar.gz && \
  cd spatialindex-src-1.8.5 && \
  ./configure && \
  make && \
  make install && \
  cd - && \
  rm -rf spatialindex-src-1.8.5* && \
  ldconfig
WORKDIR /usr/src/app
RUN python -m pip install -U --force-reinstall pip
RUN pip install --no-cache-dir -r requirements.txt
COPY ./ /usr/src/app
RUN python ./fetch_data.py

EXPOSE 80

CMD ["python", "main.py"]
