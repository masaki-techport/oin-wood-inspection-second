import os
import sys
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SOURCE_DIR = ROOT_DIR + "/source"
CONFIG_DIR = ROOT_DIR + "/config"
sys.path.append(SOURCE_DIR)
CONFIG_FILE_NAME = "settings.ini"