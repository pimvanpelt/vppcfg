import os, sys

ROOT_DIR = os.path.dirname(__file__)

# fix the module load path
sys.path.insert(0, ROOT_DIR)

# fix the yaml search path
os.chdir(ROOT_DIR)
