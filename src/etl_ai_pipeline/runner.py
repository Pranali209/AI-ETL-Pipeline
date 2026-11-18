import sys
import pandas as pd
import numpy as np
import re
import math
import datetime

in_path , code_path , out_path = sys.argv[1] , sys.argv[2] , sys.argv[3]

df = pd.read_parquet(in_path)
code = open(code_path ,encoding="utf-8").read()

namespace = {"pd": pd, "np": np, "re": re, "math": math, "datetime": datetime}
exec(code,namespace)

result = namespace["transform"](df)
result.to_parquet(out_path)
