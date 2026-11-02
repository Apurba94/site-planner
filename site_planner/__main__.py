"""Start the app: python -m site_planner [data.db] [--port 8036]"""
import sys

from .fieldkit import main_cli
from .web import create_app

sys.exit(main_cli(create_app, "siteplan.db", 8036, sys.argv))
