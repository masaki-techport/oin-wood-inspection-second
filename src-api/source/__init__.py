import os
import sys
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SOURCE_DIR = ROOT_DIR + "/source"
CONFIG_DIR = ROOT_DIR + "/config"
sys.path.append(SOURCE_DIR)
CONFIG_FILE_NAME = "settings.ini"

# Additional config file paths
DIO_CONFIG_FILE = os.path.join(CONFIG_DIR, "DIO_setting.yaml")
PARAMS_CONFIG_FILE = os.path.join(CONFIG_DIR, "params.yaml")
SENSOR_CONFIG_FILE = os.path.join(CONFIG_DIR, "sensor_config.yaml")