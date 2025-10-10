import csv
import os
import requests
import time

from d2spy.workspace import Workspace
from datetime import datetime
from dotenv import load_dotenv

load_dotenv("d2s/.env")

class MyWorkspace(Workspace):
    @classmethod
    def connect(cls, base_url: str, email: str = None, password: str = None):
        from d2spy.auth import Auth
        auth = Auth(base_url)
        auth.login(email=email, password=password)
        api_key = getattr(auth.session, "d2s_data", {}).get("API_KEY", "")
        return cls(base_url, auth.session, api_key)

def safe_add_data_product(flight, filepath, data_type, max_retries=3, delay=10):
    for attempt in range(max_retries):
        try:
            flight.add_data_product(filepath=filepath, data_type=data_type)
            return True
        except requests.exceptions.SSLError as e:
            print(f"SSL error on {data_type} upload (attempt {attempt+1}/{max_retries}): {e}")
            time.sleep(delay)
        except Exception as e:
            print(f"Error on {data_type} upload (attempt {attempt+1}/{max_retries}): {e}")
            time.sleep(delay)
    print(f"Failed to upload {data_type} after {max_retries} attempts.")
    return False

email = os.environ.get("D2S_EMAIL")
password = os.environ.get("D2S_PASSWORD")
project_id = os.environ.get("D2S_PROJECT_ID")
conrad_path = os.environ.get("CONRAD_PATH")
workspace = MyWorkspace.connect("https://ps2.d2s.org/", email, password)
project = workspace.get_project(project_id)

csv_path = "d2s/data/drone_missions.csv"
with open(csv_path, newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        title = row['_title']
        name = title
        date_str = title[:8]  # YYYYMMDD
        acq_date = datetime.strptime(date_str, "%Y%m%d").date()
        print(name, acq_date)
        flight = project.add_flight(
            name=name,
            acquisition_date=acq_date,
            altitude=60,
            side_overlap=75,
            forward_overlap=85,
            sensor="RGB",
            platform="M3E"
        )
        print(flight)
        dsm = f"{conrad_path}/{name}/{name}_dsm.cog.tif"
        safe_add_data_product(flight, dsm, "dsm")
        rgb = f"{conrad_path}/{name}/{name}_rgb.cog.tif"
        safe_add_data_product(flight, rgb, "ortho")
        ptc = f"{conrad_path}/{name}/{name}_pg.copc.laz"
        safe_add_data_product(flight, ptc, "point_cloud")