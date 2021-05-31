import sys, os, tempfile, json, logging, arcpy
import datetime as dt
from urllib import request
from urllib.error import URLError

def feedRoutine (url, workGDB):
    # Configure and format (define var) the log file
    logging.basicConfig(filename="coral_reef_exercise.log", level=logging.INFO)
    log_format = "%Y-%m-%d %H:%M:%S"

    # Check if you need to create the FGDB and set the default workspace
    print("Starting workGDB...")
    logging.info("Starting workGDB... {0}".format(dt.datetime.now().strftime(log_format)))
    # Check if workGDB already exists
    if arcpy.Exists(workGDB): # changed arcpy.env.workspace to workGDB
        arcpy.env.workspace = workGDB
        for feat in arcpy.ListFeatureClasses ("alert_*"):   
            arcpy.management.Delete(feat)
    else:
        arcpy.management.CreateFileGDB(os.path.dirname(workGDB), os.path.basename(workGDB))
        arcpy.env.workspace = workGDB
    # arcpy.management.CreateFileGDB(os.path.dirname(workGDB), os.path.basename(workGDB)) # original code placed above the workspace environment setting!
    # arcpy.env.workspace = workGDB # original code

    ### Retrieve and map data ###
    # Download and split json file
    print("Downloading data...")
    logging.info("Downloading data... {0}".format(dt.datetime.now().strftime(log_format)))
    # Creates a temporary directory in the most secure manner possible. There are no race conditions in the directory’s creation. The directory is readable, writable, and searchable only by the creating user ID.
    temp_dir = tempfile.mkdtemp() # Creates a temp. folder like C:\Users\User\AppData\Local\Temp\tmpcpwka2sy
    filename = os.path.join(temp_dir, 'latest_data.json')
    
    try:
        response = request.urlretrieve(url, filename)
    except URLError: # catch common error  when URL is unavailable. (must be imported from urllib!)
        logging.exception("Failed on: request.urlretrieve(url, filename) {0}".format(dt.datetime.now().strftime(log_format)))
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

    # Close the Log File
    logging.shutdown()

    # Return
    print("Done!")
    logging.info("Done! {0}".format(dt.datetime.now().strftime(log_format)))
    return True

# In Aggregated Live Feed (ALF) methodology, the deployment logic process is the part of the feed roputine that grabs the latest data from the internet (our WorkGDB) and overwrites the live data (Live.gdb has the layers in our ArcGIS Pro project!)
def deployLogic():
    pass

# Standalone routine (i.e from cmd prompt)
if __name__ == "__main__":
    # Get the URL and FGDB path from cmd prompt args (2nd and remaining args, should be only 2)
    # 2nd arg should be C:\Temp\Work.gdb
	[url, workGDB] = sys.argv[1:]
	feedRoutine (url, workGDB)