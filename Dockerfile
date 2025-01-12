FROM python:3

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY ./requirements.txt /usr/src/app/
COPY ./ /usr/src/app

COPY requirements.txt ./
RUN apt-get update &&\
    apt-get install -y binutils libproj-dev gdal-bin
RUN apt-get update
RUN apt-get install -y gdal-bin libgdal-dev g++
RUN python -m pip install shapely pyproj fiona pyogrio rtree
RUN pip install --no-cache-dir -r requirements.txt



# RUN python ./fetch_data.py

EXPOSE 80

CMD ["python", "main.py"]
