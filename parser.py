import re
import glob
import json
import sys
import requests

def parse_file(filename):
    with open(filename, "r") as f:
        data = f.read().split("\n")

    raw_benchmarks = split_lines_to_benchmarks(data)
    benchmarks = {}
    for index, raw_benchmark in enumerate(raw_benchmarks):
        pid, data = parse_benchmark_lines(raw_benchmark)
        benchmarks[pid] = data
        sys.stderr.write(f"{index+1} {len(raw_benchmarks)}\r")
        sys.stderr.flush()
    return benchmarks

def split_lines_to_benchmarks(data):
    raw_benchmarks = []
    benchmark_buffer = []
    for line in data:
        if line.startswith("1 "):
            raw_benchmarks.append(benchmark_buffer)
            benchmark_buffer = []
        benchmark_buffer.append(line)
    del raw_benchmarks[0]
    return raw_benchmarks

def parse_benchmark_lines(data):
    pid = None
    properties = {}
    properties["published"] = True

    # get date line
    raw_date = data.pop(0).split(" = ")[1]
    properties["database_retrieval"] = raw_date

    # pid header
    pid = data.pop(0)[1:7]
    properties["pid"] = pid

    # ==================
    # + BASIC METADATA +
    # ==================
    properties["special_categories"] = []
    while True:
        if match := re.match(" " + pid + "  (CORS|FBN|CBN|PACS|SACS|HT_MOD|WATER LEVEL|DATUM ORIG|TIDAL BM)", data[0]):
            properties["special_categories"].append(match.group(1))
            del data[0]
        else:
            break


    while True:
        if match := re.match(" " + pid + r"  ([\s_\/A-Z]+?)\s*\-  (.*)$", data[0]):
            properties[match.group(1).replace(" ", "_").lower()] = match.group(2)
            del data[0]
        else:
            break

    # ==================
    # + SURVEY CONTROL +
    # ==================
    del data[0:3] # remove header lines

    # lat/lon ===============================
    if match := re.match(r" " + pid + r"\* (?P<datum>.*?) POSITION- (?P<lat_degrees>\d+) (?P<lat_minutes>\d+) (?P<lat_seconds>[\d\.]+)\s*\((?P<lat_hemisphere>[NS])\) (?P<lon_degrees>\d+) (?P<lon_minutes>\d+) (?P<lon_seconds>[\d\.]+)\s*\((?P<lon_hemisphere>[EW])\)\s+(?P<method>.*?)$", data[0]):
        location = {"datum":match.group("datum"), "method":match.group("method")}

        # latitude
        lat_dd = int(match.group("lat_degrees")) + (int(match.group("lat_minutes"))/60.0) + (float(match.group("lat_seconds"))/3600.0)
        if match.group("lat_hemisphere") == "S": lat_dd *= -1
        location["latitude"] = lat_dd

        lon_dd = int(match.group("lon_degrees")) + (int(match.group("lon_minutes"))/60.0) + (float(match.group("lon_seconds"))/3600.0)
        if match.group("lon_hemisphere") == "W": lon_dd *= -1
        location["longitude"] = lon_dd

        properties["location"] = location
        del data[0]

    # ellipsoid height ================================
    if match := re.match(r" " + pid + r"\* (?P<datum>.*?) ELLIP HT-\s*(?P<height>[,\-\d\.]+) \((?P<unit>\w*?)\)\s*\((?P<date>[\d\?\/]+)\)\s*(?P<method>[\w]+)$", data[0]):
        ellipsoid_height = {
            "datum":match.group("datum"),
            "method":match.group("method"),
            "height":float(match.group("height")),
            "unit":match.group("unit"),
            "date":match.group("date")
        }
        properties["ellipsoid_height"] = ellipsoid_height
        del data[0]

    # epoch date ====================================
    if match := re.match(r" " + pid + r"\* (?P<datum>.*?) EPOCH\s*-\s*(?P<epoch>[,\-\d\.]+)\s*$", data[0]):
        properties["epoch"] = {"datum":match.group("datum"),"epoch":match.group("epoch")}
        del data[0]


    # orthometric height ==============================
    if match := re.match(r" " + pid + r"\* (?P<datum>.*?)\s*ORTHO HEIGHT\s*-\s*(?P<meters>[\d,\-\.\*]+)\s+\(meters\)\s+(?P<feet>[,\d\-\.\*]+)\s+\(feet\)\s*(?P<method>.*?)$", data[0]):
        try:
            meters = float(match.group("meters"))
        except ValueError:
            meters = None
        try:
            feet = float(match.group("feet"))
        except ValueError:
            feet = None
        properties["orthometric_height"] = {
            "datum":match.group("datum"),
            "method":match.group("method"),
            "meters":meters,
            "feet":feet
        }
        del data[0]

    properties["warnings"] = ""
    while True:
        prefix = " "+pid+"  **"
        if data[0].startswith(prefix):
            properties["warnings"] += data[0].lstrip(prefix) + "\n"
            del data[0]
        else:
            break
    del data[0] # delete seperator

    # geoid_undulation_model =========================
    if match := re.match(" "+pid+r" (?P<datum>.*?)\s*orthometric height was determined with geoid model\s*(?P<method>.*?)$", data[0]):
        properties["geoid_undulation_ortho_model"] = {"datum": match.group("datum"), "model": match.group("method")}
        del data[0]

    while True:
        if match := re.match(" "+pid+r" GEOID HEIGHT\s+\-\s+(?P<undulation>[\.\d\*,]+)\s+\((?P<unit>[\s\w]+)\)\s+(?P<model>.*?)$", data[0]):
            properties["geoid_undulation_model"] = {"undulation": match.group("undulation"), "unit":match.group("unit"),"model": match.group("model")}
            del data[0]
        else:
            break

    # cartesian coordinates ==========================
    cartesian = {}
    while True:
        if match := re.match(" "+pid+r" (?P<datum>.*)\s+(?P<axis>[XYZ])\s+\-\s+(?P<value>[\d,\-\.]+)\s+\((?P<unit>[\s\w]+)\)\s+(?P<method>.*)$", data[0]):
            cartesian[match.group("axis").lower()] = {
                "datum":match.group("datum"),
                "value":float(match.group("value").replace(",","")),
                "unit":match.group("unit"),
                "method":match.group("method")
            }
            del data[0]
        else:
            break
    properties["cartesian"] = cartesian

    # laplace correction ============================
    if match := re.match(" "+pid+r" LAPLACE CORR\s+\-\s+(?P<value>[\.\d\*,]+)\s+\((?P<unit>[\s\w]+)\)\s+(?P<deflection>.*?)$", data[0]):
        properties["laplace_correction"] = {"value": match.group("value"),"unit":match.group("unit"), "deflection": match.group("deflection")}
        del data[0]

    # dynamic height ================================
    if match := re.match(r" " + pid + r"\s+DYNAMIC HEIGHT\s*-\s*(?P<meters>[\d,\-\.\*]+)\s+\(meters\)\s+(?P<feet>[,\d\-\.\*]+)\s+\(feet\)\s*(?P<method>.*?)$", data[0]):
        properties["dynamic_height"] = {
            "datum":match.group("datum"),
            "method":match.group("method"),
            "meters":float(match.group("meters")),
            "feet":float(match.group("feet"))
        }
        del data[0]

    # gravity ======================
    if match := re.match(" "+pid+r" MODELED GRAVITY\s+\-\s+(?P<value>[\.\d\*,]+)\s+\(mgal\)\s+(?P<datum>.*?)$", data[0]):
        properties["modeled_gravity"] = {"value": match.group("value"),"datum": match.group("datum")}
        del data[0]

    # ==================
    # +   ACCURACY     +
    # ==================
    # skip all ths for now??
    while True:
        if len(data[0]) < 9 or data[0][7] != ".":
            del data[0]
        else:
            break
    # ==================
    # +DATA METHODOLOGY+ (and PROJECTIONS)
    # ==================
    properties["data_notes"] = ""
    while True:
        line_content = data[0].lstrip(" "+pid)
        if len(line_content)==0 or line_content[0] in ':;!.':
            properties["data_notes"] += line_content + "\n"
            del data[0]
        else:
            break

    if match := re.match(" "+pid+r"_U\.S\. NATIONAL GRID SPATIAL ADDRESS:\s+(?P<address>.*)$", data[0]):
        properties["us_national_grid_address"] = {"address": match.group("address")}
        del data[0]
    del data[0]

    # ==================
    # + BOX SCORE      +
    # ==================
    references = []
    if data[0][7] == "|":
        del data[0:3]
        while data[0][8] != "-":
            if match := re.match(r" "+pid+r"\|\s+(?P<pid>\w+)\s+(?P<name>[\s\w]+?)\s{2,}(APPROX\.\s*)?(?P<distance>[\.\d,]+)\s+(?P<unit>\w+)\s+(?P<degrees>\d{3})(?P<minutes>\d{2})(?P<seconds>\d\d\.?\d?)?", data[0]):
                bearing = int(match.group("degrees")) + (int(match.group("minutes"))/60.0)
                if match.group("seconds"):
                    bearing += (float(match.group("seconds"))/3600.0)
                references.append({
                    "pid": match.group("pid"),
                    "name": match.group("name"),
                    "distance": match.group("distance"),
                    "unit": match.group("unit"),
                    "bearing": bearing
                })
            del data[0]
        del data[0]
    properties["references"] = references

    # ==================
    # + SUPERSEDED     +
    # ==================
    #ignore for now:

    while True:
        if len(data) > 1 and (len(data[0]) < 9 or (data[0][7] != "_" and ("HISTORY" not in data[0]))):
            del data[0]
        else:
            break
    # ==================
    # + MONUMENTATION  +
    # ==================
    properties["photographs"] = get_photos(pid)

    # marker type ===================================
    if match := re.match(r" "+pid+r"_MARKER: (?P<code>\w+)\s+=\s+(?P<description>.+).*$", data[0]):
        properties["marker_type"] = {"code": match.group("code"), "description": match.group("description")}
        del data[0]
    else:
        properties["marker_type"] = None

    # setting =======================================
    if match := re.match(r" "+pid+r"_SETTING: (?P<code>\d+)\s+=\s+(?P<description>.+).*$", data[0]):
        properties["setting"] = {"code": int(match.group("code")), "description": match.group("description")}
        del data[0]
    else:
        properties["setting"] = None
    if properties["setting"] and (match := re.match(r" "+pid+r"\+WITH SETTING: (?P<value>.*)$", data[0])):
        properties["setting"]["description"] += " " + match.group("value")
        del data[0]
    if match := re.match(r" "+pid+r"_SP_SET:\s+(?P<description>.+).*$", data[0]):
        properties["sp_set"] = match.group("description")
        del data[0]
    else:
        properties["sp_set"] = None


    # stamping ======================================
    if match := re.match(r" "+pid+r"_STAMPING: (?P<stamping>.*)$", data[0]):
        properties["stamping"] = match.group("stamping")
        del data[0]
    else:
        properties["stamping"] = pid

    # logo ======================================
    if match := re.match(r" "+pid+r"_MARK LOGO: (?P<logo>.*)$", data[0]):
        properties["logo"] = match.group("logo")
        del data[0]
    else:
        properties["logo"] = None

    # projection =======================================
    if match := re.match(r" "+pid+r"_PROJECTION: (?P<direction>\w+)\s*(?P<amount>[\w\d ]+)?.*$", data[0]):
        properties["projection"] = {"direction":match.group("direction"),"amount":match.group("amount")}
        del data[0]
    else:
        properties["projection"] = None

    # magnetic =======================================
    if match := re.match(r" "+pid+r"_MAGNETIC: (?P<code>\w+)\s+=\s+(?P<description>.+)$", data[0]):
        properties["magnetic"] = {"code": match.group("code"), "description": match.group("description")}
        del data[0]
    else:
        properties["magnetic"] = None
    # stability ======================================
    if match := re.match(r" "+pid+r"_STABILITY: (?P<code>\w+)\s+=\s+(?P<description>.+)$", data[0]):
        properties["stability"] = {"code": match.group("code"), "description": match.group("description")}
        del data[0]
    else:
        properties["stability"] = None
    if properties["stability"] and (match := re.match(r" "+pid+r"\+STABILITY: (?P<value>.*)$", data[0])):
        properties["stability"]["description"] += " " + match.group("value")
        del data[0]


    # satellite ======================================
    if match := re.match(r" "+pid+r"_SATELLITE:\s+(?P<description>.*)$", data[0]):
        properties["satellite"] = match.group("description")
        del data[0]
    else:
        properties["satellite"] = None
    if properties["satellite"] and (match := re.match(r" "+pid+r"\+SATELLITE: (?P<value>.*)$", data[0])):
        properties["satellite"] += " " + match.group("value")
        del data[0]

    # rod_pipe_depth =================================
    if match := re.match(r" "+pid+r"_ROD\/PIPE-DEPTH: (?P<value>.*)$", data[0]):
        properties["rod_pipe_depth"] = match.group("value")
        del data[0]
    else:
        properties["rod_pipe_depth"] = None

    # sleeve_depth =================================
    if match := re.match(r" "+pid+r"_SLEEVE-DEPTH: (?P<value>.*)$", data[0]):
        properties["sleeve_depth"] = match.group("value")
        del data[0]
    else:
        properties["sleeve_depth"] = None
    while "HISTORY" not in data[0] and "STATION DESCRIPTION" not in data[0]:
        del data[0]

    del data[0]
    # ==================
    # +   HISTORY      +
    # ==================
    history = []
    while True:
        if match:=re.match(r" "+pid+r"\s+HISTORY\s+\-\s+(?P<year>(\d\d\d\d)|(UNK))(?P<month>\d\d)?(?P<day>\d\d)?\s+(?P<condition>.*?)\s+(?P<organization>.+)$", data[0]):
            history.append({
                "date": match.group("year") + "/" + (match.group("month")or"??") + "/" + (match.group("day")or"??"),
                "condition": match.group("condition"),
                "org_code": match.group("organization")
            })
            del data[0]
        else:
            break
    properties["history"] = history

    # ==================
    # +   DESCRIPTION  +
    # ==================
    del data[0]
    if "STATION DESCRIPTION" in data[0]:
        del data[0:2]
        prefix = " "+pid+"'"
        description = ""
        described_by = data[0].lstrip(prefix)
        del data[0]
        while len(data) > 0 and len(data[0]) >= 8 and data[0][7] == "'":
            description += data[0] + " "
            del data[0]
        properties["description"] = description + "\n" + described_by
    for index, _ in enumerate(properties["history"]):
        if index == 0:
            continue
        if len(data) == 0:
            break
        del data[0:3]
        organization = data[0].lstrip(" "+pid+"'RECOVERY NOTE BY ")
        note = ""
        del data[0]
        while len(data) > 0 and len(data[0]) >= 8 and data[0][7] == "'":
            addition = data[0].lstrip(prefix)
            if addition != "":
                note += addition + " "
            else:
                note += "\n"
            del data[0]
        properties["history"][index]["note"] = note.strip()
        properties["history"][index]["organization"] = organization



    # end =============================================

    # while len(data)>1:
        # print(data[0])
        # del data[0]
    # print("\n\n========================================================================\n\n")

    return pid, properties

def get_photos(pid):
    url = "https://www.ngs.noaa.gov/cgi-bin/get_image.prl?PROCESSING=list&PID="+pid
    return url
    # data = requests.get(url)
    # return list(map(lambda i: "https://www.ngs.noaa.gov/"+i.replace("thumbnail", "image"), re.findall(r'src="(.*?)"', data.text)))

def parse_nonpub(filename):
    nonpub = {}
    with open(filename) as f:
        data = f.read().split("\n")
    while not data[0].startswith(" >"):
        del data[0]
    for line in data:
        if match := re.match(r" >(?P<pid>\w+)\s+(?P<name>.+?)\s{2,}(?P<lat_d>\d+)\s+(?P<lat_m>\d+)\s+(?P<lat_s>\d+)\.\s+\/(?P<lon_d>\d+)\s+(?P<lon_m>\d+)\s+(?P<lon_s>\d+)\.\s{1,10}(?P<elevation>[\d\.]+)?.*?(?P<h_nonpub>[A-Z])(?P<v_nonpub>[A-Z])$", line):
            nonpub[match.group("pid")] = {
                "pid": match.group("pid"),
                "stamping": match.group("name"),
                "location": {
                    "latitude": int(match.group("lat_d") or 0) + (int(match.group("lat_m") or 0)/60.0) + (float(match.group("lat_s") or 0.0)/3600.0),
                    "longitude": int(match.group("lon_d") or 0) + (int(match.group("lon_m") or 0)/60.0) + (float(match.group("lon_s") or 0.0)/3600.0),
                },
                "suspected_elevation": match.group("elevation"),
                "horizontal_nonpub_reason": match.group("h_nonpub"),
                "vertical_nonpub_reason": match.group("v_nonpub"),
                "published": False,
                "history":[{"condition":"nonpublished"}]
            }
    return nonpub


# data_nonpub = parse_nonpub("data/nonpub.dat")
data = {}
filenames = glob.glob("data/datasheets/*.txt")
for index, filename in enumerate(filenames):
    print(f"{index+1}/{len(filenames)}", filename)
    try:
        data |= parse_file(filename)
    except Exception as e:
        print(e)
    print()
with open("./data.json", "w+") as f:
    f.write(json.dumps(data))

geojson = {"type":"FeatureCollection","features":[]}
for index, value in enumerate(data.items()):
    pid, properties = value
    # if index > 100: break
    try:
        condition = properties["history"][-1]["condition"]
    except:
        condition = "none"
    geojson["features"].append({
        "type": "Feature",
        "properties": {
            "pid":pid,
            "published":properties["published"],
            "condition":condition
        },
        "geometry": {
            "coordinates": [properties["location"]["longitude"], properties["location"]["latitude"]],
            "type": "Point"
        }
    })
with open("./geojson.json", "w+") as f:
    f.write(json.dumps(geojson))
