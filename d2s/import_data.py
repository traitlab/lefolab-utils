import csv
from datetime import datetime
from d2spy.workspace import Workspace
import os
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
        flight.add_data_product(
            filepath=dsm,
            data_type="dsm"
        )
        rgb = f"{conrad_path}/{name}/{name}_rgb.cog.tif"
        flight.add_data_product(
            filepath=rgb,
            data_type="ortho"
        )
        ptc = f"{conrad_path}/{name}/{name}_pg.copc.laz"
        flight.add_data_product(
            filepath=ptc,
            data_type="point_cloud"
        )
