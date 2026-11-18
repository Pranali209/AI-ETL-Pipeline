import pandas as pd

from etl_ai_pipeline.db import get_engine


def extract_csv(path):
    """ extract the csv file from the given path"""
    try:
        return pd.read_csv(path)
    except UnicodeDecodeError:
        return pd.read_csv(path ,encoding="cp1252")
        
    


def inspect_csv(path,sample_row=5):
    """ inspect the csv file """
    df = extract_csv(path)
    return{
        "columns" : list(df.columns),
        "dtypes" : {col : str(dtype) for col , dtype in df.dtypes.items()},
        "row_count" : len(df),
        "null_count" : df.isnull().sum().to_dict(),
        "sample_count" : df.head(sample_row).to_dict(orient="records")
    }



def load_to_sql(df,table_name,mode="fail"):
    """ load the data to sql """
    if mode not in ("fail" , "append" , "replace"):
        raise ValueError("mode must be either 'fail', 'append', or 'replace'")

    engine = get_engine()
    df.to_sql(
        name = table_name,
        con = engine,
        if_exists = mode,
        index = False,
        chunksize = 1000,
        method = "multi",
        
    )
    return len(df)
    






