from flask import Flask, Response
from flask_cors import CORS, cross_origin
import re
import json
import requests

import geopandas

gdf = geopandas.read_file("./combined.json")
gdf.set_index("PID")
gdf.columns = map(str.lower, gdf.columns)

data = json.loads(open("./data.json").read())
app = Flask(__name__)
app.config['CORS_HEADERS'] = 'Content-Type'
CORS(app)

@app.route("/<lon_min>,<lat_min>,<lon_max>,<lat_max>")
@cross_origin()
def bbox(lon_min, lon_max, lat_min, lat_max):
    data = gdf.cx[lon_min:lon_max, lat_min:lat_max].to_json()
    return Response(data, headers={"Content-Type":"application/json"})

@app.route("/<pid>.json")
@cross_origin()
def pid_data(pid):
    if not isinstance(data[pid]["photographs"], list):
        data[pid]["photographs"] = get_photos(pid)
    benchmark = data[pid]
    return benchmark

def get_photos(pid):
    url = "https://www.ngs.noaa.gov/cgi-bin/get_image.prl?PROCESSING=list&PID="+pid
    data = requests.get(url)
    print(data.text)

    return list(map(lambda i: "https://www.ngs.noaa.gov/"+i.replace("thumbnail", "image"), re.findall(r'src="(.*?)"', data.text)))

if __name__ == "__main__":
    app.run("localhost", 8081)
