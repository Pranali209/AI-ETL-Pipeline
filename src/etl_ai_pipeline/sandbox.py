import numpy as np
import pandas as pd
import re, math, datetime



class SandboxError(Exception):
    pass

def run_transform(code:str ,df:pd.DataFrame) ->pd.DataFrame :
    namespace = {"pd": pd, "np": np, "re": re, "math": math, "datetime": datetime}
    
    try: 
        exec(code,namespace)
        result = namespace["transform"](df.copy())
    except Exception as e:
        raise SandboxError(f"Code crashed: {e}")
    if not isinstance(result , pd.DataFrame):
        raise SandboxError("Transform() must return a DataFrame")
    return result
   
