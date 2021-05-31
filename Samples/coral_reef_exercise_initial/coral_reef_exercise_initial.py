import sys, arcpy, os, tempfile, json
from urllib import request

def feedRoutine (url, workGDB):
    # workGDB and default workspace
    print("Creating workGDB...")
    arcpy.env.workspace = workGDB 
    arcpy.management.CreateFileGDB(os.path.dirname(workGDB), os.path.basename(workGDB))
    
    # Download and split json file
    print("Downloading data...")
    temp_dir = tempfile.mkdtemp()
    filename = os.path.join(temp_dir, 'latest_data.json')
    response = request.urlretrieve(url, filename)
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
    deployLogic()

    # Return
    print("Done!")
    return True

def deployLogic():
    pass

if __name__ == "__main__":
    [url, workGDB] = sys.argv[1:]
    feedRoutine (url, workGDB)