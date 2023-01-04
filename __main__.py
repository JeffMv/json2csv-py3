import os

from . import json2csv
from . import gen_outline


if __name__ == "__main__":  # pragma: no cov
    args = os.sys.argv
    prog = args[1]
    
    if prog.strip().lower() in ["gen_outline", "go", "gen", "outline"]:
      gen_outline.main(args[2:])  # pragma: no cov
    elif prog.strip().lower() in ["json2csv", "json2csv-py3", "j2c"]:
      json2csv.main(args[2:])  # pragma: no cov
    else:
      json2csv.main(args[1:])  # pragma: no cov
    
      