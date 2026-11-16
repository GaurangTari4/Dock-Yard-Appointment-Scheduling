import argparse, json
from .core import validate_directory
p=argparse.ArgumentParser(); p.add_argument('directory'); p.add_argument('--injected',action='store_true'); a=p.parse_args()
print(json.dumps(validate_directory(a.directory,a.injected),indent=2))
