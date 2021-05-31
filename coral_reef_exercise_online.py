import sys, os, tempfile, json, logging, arcpy, fnmatch, shutil, subprocess, arcgis
from arcgis.gis import GIS
import datetime as dt
from urllib import request
from urllib.error import URLError

def feedRoutine (url, workGDB, itemid, original_sd_file, service_name, arcgis_url, username, password):
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
    deployLogic(workGDB, itemid, original_sd_file, service_name, arcgis_url, username, password)

    # Close the Log File
    logging.shutdown()

    # Return
    print("Done!")
    logging.info("Done! {0}".format(dt.datetime.now().strftime(log_format)))
    return True

# In Aggregated Live Feed (ALF) methodology, the deployment logic process is the part of the feed roputine that grabs the latest data from the internet (our WorkGDB) and overwrites the live data (Live.gdb has the layers in our ArcGIS Pro project!)
def deployLogic(workGDB, itemid, original_sd_file, service_name, arcgis_url, username, password):
    # Get the feature service to be updated (arcgis.com is default URL anyway, but this arcgis_url var is from user input 
    gis = GIS(url=arcgis_url, username=username, password=password) # cmd prompt asks for password
    print("Successfully logged in as: " + gis.properties.user.username)
    item = gis.content.get(itemid)
    sd_file_name = os.path.basename(original_sd_file)
    if sd_file_name != item.related_items("Service2Data")[0].name:
        raise Exception('Erroneous itemid, service name, or original sd file'.format(itemid))
    
    # Unpack original_sd_file using 7-zip
    path_7z = fnmatch.filter(os.environ['path'].split(';'), '*7-Zip')
    temp_dir = tempfile.mkdtemp()
    if len(path_7z):
        exe_7z = os.path.join(path_7z[0], '7z.exe')
        call_unzip = '{0} x {1} -o{2}'.format(exe_7z, original_sd_file, temp_dir)
    else:
        raise Exception('7-Zip could not be found in the PATH environment variable')
    subprocess.call(call_unzip)
    
    # Replace Live.gdb content w/ Work.gdb content
    liveGDB = os.path.join(temp_dir, 'p20', 'live.gdb')
    shutil.rmtree(liveGDB)
    os.mkdir(liveGDB)
    for root, dirs, files in os.walk(workGDB):
        files = [f for f in files if '.lock' not in f]
        for f in files:
            shutil.copy2(os.path.join(workGDB, f), os.path.join(liveGDB, f))

    # Zip  Live.gdb into a new service def file (w/ original sd file!)
    os.chdir(temp_dir)
    updated_sd = os.path.join(temp_dir, sd_file_name)
    call_zip = '{0} a {1} -m1=LZMA'.format(exe_7z, updated_sd)
    subprocess.call(call_zip)

    # Use the item's manager method to overwrite the feature service!
    manager = arcgis.features.FeatureLayerCollection.fromitem(item).manager
    status = manager.overwrite(updated_sd)
    # Return
    return True

# Standalone routine (i.e from cmd prompt)
if __name__ == "__main__":
    # Get the URL and FGDB path from cmd prompt args (2nd and remaining args, should be only 2)
    # 2nd arg should be C:\Temp\Work.gdb
    print('Starting main program')
    arcgis_url = input('Enter the URL for the AGOL or Portal web page: ') # The arcgis_url can be AGOL (https://arcgis.com) or a Portal url (http://webadaptorhost (the server).domainname.com/webadaptorname (arcgis is default name))
    username = input('Enter the case-sensitive username for the AGOL or Portal account: ')
    password = input('Enter the password for the AGOL or Portal account: ')
    [url, workGDB, itemid, original_sd_file, service_name] = sys.argv[1:] # URL to NOAA's data is https://coralreefwatch.noaa.gov/product/vs/vs_polygons.json (from day before today usually) ## The test URL is historic data from 02-19-2019, https://downloads.esri.com/LearnArcGIS/update-real-time-data-with-python/vs_polygons.json
    feedRoutine (url, workGDB, itemid, original_sd_file, service_name, arcgis_url, username, password)