import sys, os, tempfile, json, logging, arcpy
import datetime as dt
from urllib import request
from urllib.error import URLError

def feedRoutine (url, workGDB):
    # Log file
    logging.basicConfig(filename="coral_reef_exercise.log", level=logging.INFO)
    log_format = "%Y-%m-%d %H:%M:%S"
    # Create workGDB and default workspace
    print("Starting workGDB...")
    logging.info("Starting workGDB... {0}".format(dt.datetime.now().strftime(log_format)))
    arcpy.env.workspace = workGDB
    if arcpy.Exists(arcpy.env.workspace):
        for feat in arcpy.ListFeatureClasses ("alert_*"):   
            arcpy.management.Delete(feat)
    else:
        arcpy.management.CreateFileGDB(os.path.dirname(workGDB), os.path.basename(workGDB))
    
    # Download and split json file
    print("Downloading data...")
    logging.info("Downloading data... {0}".format(dt.datetime.now().strftime(log_format)))
    temp_dir = tempfile.mkdtemp()
    filename = os.path.join(temp_dir, 'latest_data.json')
    try:
        response = request.urlretrieve(url, filename)
    except URLError:
        logging.exception("Failed on: request.urlretrieve(url, filename) {0}".format(
                          dt.datetime.now().strftime(log_format)))
        raise Exception("{0} not available. Check internet connection or url address".format(url))
    with open(filename) as json_file:
        data_raw = json.load(json_file)
        data_stations = dict(type=data_raw['type'], features=[])
        data_areas = dict(type=data_raw['type'], features=[])
    for feat in data_raw['features']:
        if feat['geometry']['type'] == 'Point':
            data_stations['features'].append(feat)
        else:
            data_areas['features'].append(feat)
    # Filenames of temp json files
    stations_json_path = os.path.join(temp_dir, 'points.json')
    areas_json_path = os.path.join(temp_dir, 'polygons.json')
    # Save dictionaries into json files
    with open(stations_json_path, 'w') as point_json_file:
        json.dump(data_stations, point_json_file, indent=4)
    with open(areas_json_path, 'w') as poly_json_file:
        json.dump(data_areas, poly_json_file, indent=4)
    # Convert json files to features
    print("Creating feature classes...")
    logging.info("Creating feature classes... {0}".format(dt.datetime.now().strftime(log_format)))
    arcpy.conversion.JSONToFeatures(stations_json_path, 'alert_stations') 
    arcpy.conversion.JSONToFeatures(areas_json_path, 'alert_areas')
    # Add 'alert_level ' field
    arcpy.management.AddField('alert_stations', 'alert_level', 'SHORT', field_alias='Alert Level')
    arcpy.management.AddField('alert_areas', 'alert_level', 'SHORT', field_alias='Alert Level')
    # Calculate 'alert_level ' field
    arcpy.management.CalculateField('alert_stations', 'alert_level', "int(!alert!)")
    arcpy.management.CalculateField('alert_areas', 'alert_level', "int(!alert!)")

    # Deployment Logic
    print("Deploying...")
    logging.info("Deploying... {0}".format(dt.datetime.now().strftime(log_format)))
    deployLogic()

    # Close Log File
    logging.shutdown()

    # Return
    print("Done!")
    logging.info("Done! {0}".format(dt.datetime.now().strftime(log_format)))
    return True

def deployLogic():
    pass

if __name__ == "__main__":
    [url, workGDB] = sys.argv[1:]
    feedRoutine (url, workGDB)