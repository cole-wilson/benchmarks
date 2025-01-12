FROM python:3

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY ./requirements.txt /usr/src/app/
COPY ./ /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


RUN python -m pip install shapely pyproj fiona pyogrio rtree

RUN python ./fetch_data.py

EXPOSE 80

CMD ["python", "-m", "http.server"]
