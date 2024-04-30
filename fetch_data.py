import requests
import re
import zipfile
from requests_toolbelt import MultipartEncoder
from io import BytesIO
import geopandas
import pandas
import os
import glob

os.makedirs("./data/shapefiles/", exist_ok=True)
os.makedirs("./data/datasheets_zips/", exist_ok=True)
os.makedirs("./data/datasheets/", exist_ok=True)

SHAPEFILE_URL = "https://www.ngs.noaa.gov/cgi-bin/sf_archive.prl"

def get_zipfile_item(response:requests.Response, itempath:str) -> bytes:
    resp_b = BytesIO(response.content)
    try:
        zipf = zipfile.ZipFile(resp_b)
    except:
        print("\tno data")
        return b""
    print(zipf.namelist())
    shapefile = zipf.open(itempath, 'r')
    return shapefile.read()

shapefile_list = requests.get(SHAPEFILE_URL).text
shapefile_regions = re.findall(r'<option value="(?P<key>\w+)">(?P<region>.*)<\/option>', shapefile_list)
for key, region in shapefile_regions:
    print(f"fetching shapefile for {region} ({key})")

    if not os.path.isfile(f"data/shapefiles/{key}.zip"):
        multipart = MultipartEncoder(fields={"StateSelected":key,"CompressType":"Zipped"})
        response = requests.post(SHAPEFILE_URL, data=multipart, headers={"Content-Type":multipart.content_type}, stream=True)
        with open(f"data/shapefiles/{key}.zip", "wb") as outfile:
            outfile.write(response.raw.read())

    print(f"fetching datasheet for {region} ({key})")
    if not os.path.isfile(f"data/datasheets/{key}.txt"):
        try:
            response2 = requests.get(f"https://geodesy.noaa.gov/pub/DS_ARCHIVE/DataSheets/{key}.ZIP")
        except KeyboardInterrupt:
            continue
        print("got")
        datasheets = get_zipfile_item(response2, key.lower()+".txt")
        with open(f"data/datasheets/{key}.txt", "wb") as outfile:
            outfile.write(datasheets)

dataframes = []
filenames = glob.glob("./data/shapefiles/*.zip")
for index, filename in enumerate(filenames):
    print(f"{index}/{len(filenames)}", filename, end="\n")
    try:
        dataframes.append(geopandas.read_file(filename).to_crs("EPSG:4152").filter(['PID', 'geometry']))
    except Exception as e:
        print(e)
        print("unsupported/no data in", filename)

combined = pandas.concat(dataframes)
print(combined)
combined.to_file("combined.json", driver="GeoJSON")
