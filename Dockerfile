FROM python:3.8.2-alpine

RUN apk update && apk upgrade
RUN apk add --no-cache make g++ bash git openssh curl
RUN apk update
RUN apk add --virtual build-deps gcc python3-dev musl-dev
RUN apk add libc-dev geos-dev
RUN apk del build-deps

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY ./requirements.txt /usr/src/app/
RUN python -m pip install -U --force-reinstall pip
RUN python -m pip install shapely pyproj fiona pyogrio rtree
RUN pip install --no-cache-dir -r requirements.txt
COPY ./ /usr/src/app
RUN python ./fetch_data.py

EXPOSE 80

CMD ["python", "main.py"]
