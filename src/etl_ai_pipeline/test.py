from etl_ai_pipeline.backend import load_to_sql , extract_csv ,inspect_csv
# from etl_ai_pipeline.db import get_engine
# from sqlalchemy import text
# from langgraph.types import Command
# from etl_ai_pipeline.nodes import ETLAgent
from etl_ai_pipeline.ast_guard import check_code , UnsafeCodeError
from etl_ai_pipeline.ast_guard import UnsafeCodeError ,check_code
from etl_ai_pipeline.sandbox import SandboxError , run_transform
from etl_ai_pipeline.nodes import ETLAgent
import json
import pandas as pd

def test_phase1():
    info = inspect_csv("E:/Python/ETL_AI_Pipeline/src/data/data.csv")
    print("Columns:", info["columns"])
    print("Dtypes:", info["dtypes"])
    print("Rows:", info["row_count"])
    print("Nulls:", info["null_count"])


    df = extract_csv("E:/Python/ETL_AI_Pipeline/src/data/data.csv")
    print(df)

    rows = load_to_sql(df, "sales_raw", mode="replace")
    print(f"Loaded {rows} rows")

    with get_engine().connect() as conn:
        print("Rows in MySQL:", conn.execute(text("SELECT COUNT(*) FROM sales_raw")).scalar())



def test_phase2():
    plan = PipelinePlan.model_validate({
        "steps": [
            {"action": "extract", "params": {"path": "E:/Python/ETL_AI_Pipeline/src/data/data.csv"}},
            {"action": "clean_text", "params": {"column": "region", "method": "upper"}},
            {"action": "cast", "params": {"column": "amount", "dtype": "float"}},
            {"action": "cast", "params": {"column": "order_date", "dtype": "datetime"}},
            {"action": "dropna", "params": {"subset": ["customer_id", "amount"]}},
            {"action": "dedupe", "params": {}},
            {"action": "load", "params": {"table": "sales_clean", "mode": "fail"}},
        ]
    })

    df ,log = run_plan(plan, dry_run = True)
    print("\n".join(log))
    print(df)


def test_phase3():
    agent = ETLAgent()
    app = agent.build_graph()
    config = {"configurable": {"thread_id": "run-1"}}
    
    state = {
        "request": input("What should I do with the data? "),
        "filepath": "E:/Python/ETL_AI_Pipeline/src/data/data.csv",
        "plan": None, "error": None, "retries": 0,
        "approved": False, "result": "",
    }
    
    out = app.invoke(state ,config)
    
    if "__interrupt__" in out:
        info = out["__interrupt__"][0].value
        print("\n" .join(info["log"]))
        print(info["preview"])
        ok = input("\n Load this into MySQL ? y\n").lower() =="y"
        out = app.invoke(Command(resume =ok) ,config)
    print(out["result"])
    

def test_phase4():
    check_code("import pandas as pd\ndef transform(df): return df")   # should pass silently

    for bad in ["import os", "from subprocess import run", "import os.path"]:
        try:
            check_code(bad)
            print("NOT BLOCKED:", bad)
        except UnsafeCodeError as e:
            print("blocked:", e)
    

def test_phase5():
    df = pd.DataFrame({"region" : ["N" , "S", "W"] , "sales" : [10 , None ,50]})
    
    # 1. good code: should pass the guard and run
    good = """def transform(df):
        return df.dropna()"""
        
    check_code(good)
    print(run_transform(good, df))
    
    # 2. bad code: the guard should block it
    bad = """import os
    def transform(df):
        return df"""
    try:
        check_code("import os\ndef transform(df): return df")
    except UnsafeCodeError as e :
        print("Blocked:", e)
    
    # 3. code that passes the guard but crashes: the sandbox should report it
    broken =  """def transform(df):
        return df['not_a column']"""     
    check_code(broken)
    try:
        run_transform(broken ,df)
    except SandboxError as e:
        print("Sandbox error : " ,e)
        

def test_phase6():
    path = "data/data.csv"
    print(json.dumps(inspect_csv(path), indent=2, default=str))
    df = extract_csv(path)
    code = """def transform(df):
        return df.head(3)"""
    check_code(code)
    print(run_transform(code, df))

def test_phase7():
    agent = ETLAgent()
    
    result = agent.start("data/data.csv", "remove rows with missing values", thread_id="t1")

    # the graph should be paused at confirm_node
    info = result["__interrupt__"][0].value
    print("TABLE:", info["table_name"])
    print("EXPLANATION:", info["explanation"])
    print("CODE:\n", info["code"])
    print("ROWS:", info["row_count"])
    print("PREVIEW:", info["preview"][:3])

    # cancel on purpose
    final = agent.resume("t1", approved=False)
    print("STATUS:", final["status"])




def test_phase8():
    agent = ETLAgent()

    result = agent.start("data/data.csv", "remove rows with missing values", thread_id="t3")
    info = result["__interrupt__"][0].value
    print("TABLE:", info["table_name"], "| ROWS:", info["row_count"])

    final = agent.resume("t3", approved=True)
    print("STATUS:", final["status"])
    print("ERROR:", final.get("error"))


def test_phase9():
    agent = ETLAgent()
    result = agent.start("data/data.csv", "how many values in column A have special characters?", "t4")
    print("KEYS:", list(result.keys()))
    print("ERROR:", result.get("error"))
    print("RETRIES:", result.get("retries"))
    if "spec" in result:
        print("KIND:", result["spec"].get("kind"))
        print("PREVIEW:", result.get("preview"))
    print("PAUSED:", "__interrupt__" in result)

test_phase9()

    
    
    
    
    
    




