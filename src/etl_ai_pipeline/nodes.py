from typing import TypedDict , Optional
from etl_ai_pipeline.plan import TransformSpec
import json
import os
from etl_ai_pipeline.backend import load_to_sql
from etl_ai_pipeline.ast_guard import UnsafeCodeError ,check_code
from etl_ai_pipeline.sandbox import SandboxError , run_transform
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from etl_ai_pipeline.backend import inspect_csv  ,extract_csv
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt ,Command
from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver
import re



TABLE_RE = re.compile(r"[a-z][a-z0-9_]{0,62}")
Max_Retries = 3


def validate_table_name(table_name: str) -> None:
    if not isinstance(table_name, str) or not TABLE_RE.fullmatch(table_name):
        raise ValueError(
            f"Invalid table name: {table_name!r}. Must start with a lowercase "
            "letter, contain only lowercase letters, digits, or underscores, "
            "and be at most 63 characters."
        )


class AgentState(TypedDict):
    request:str
    filepath:str
    instruction: str
    schema: str
    spec: Optional[dict]
    error: Optional[str]
    retries:int
    preview:str
    approved:bool
    result:str
    status:str
    row_count:int
    history:str

load_dotenv()

class ETLAgent:
    
  def __init__(self):
    llm =  ChatOpenAI(
                 api_key=os.getenv("OPENAI_API_KEY"),
                 model = "gpt-6-luna",
                 )
    self.structured_llm =llm.with_structured_output(TransformSpec)
    self.prompt = ChatPromptTemplate.from_messages([
        ("system" , "you are a data engineer expert .write python that transforms pandas Dataframe.\n"
         "Rules:\n"
         "- First decide kind. Use 'analyze' when the user only asks a question about the data "
         "- (how many, are there any, is it skewed, what is the average). Then transform() must return "
         "- a SMALL DataFrame holding the answer, such as one row with a column named count. "
         "- Never change the data for an analyze question.\n"
         "- Use 'transform' when the user wants the data cleaned, changed or reshaped.\n"
         "- Define exactly one function: def transform(df): ... and return a DataFrame.\n"
         "- Only these imports are allowed: pandas as pd, numpy as np, re, math, datetime.\n"
         "- Do NOT read or write files, use the network, or call eval/exec/open/getattr.\n"
         "- Use only the columns that exist in the schema.\n"
         "- Pick a snake_case table_name.\n"),
        ("human" , 
        "CSV schema :\n{schema}\n\n"
        "Instructions: {instruction}\n\n"
        "Earlier requests in this session (context only):\n{history}\n\n"
        "Feedback from previous attempt:\n{feedback}")      
    ])
       
    self.app = self.build_graph()
    self.chain = self.prompt| self.structured_llm



  def inspect_node(self,state):
      info = inspect_csv(state["filepath"])
      return {"schema" : json.dumps(info ,indent=2 ,default=str) ,"retries" : 0 }


  def code_node(self,state):
    """Generate the transform code using the LLM, given the schema and instructions."""
    feedback  = "None - this is the first attempt."
      
    if state.get("error"):
        prev = (state.get("spec") or{}).get("code" ,"")
        feedback = f"Your previous attempt failed.\nCode:\n{prev}\nError:\n{state['error']}\nFix it."
    try:
        spec = self.chain.invoke({
                "schema": state["schema"],
                "instruction": state["instruction"],
                "feedback": feedback,
                "history" :state.get("history" ,"None")
        })
    
        return {"spec" : spec.model_dump() , "error" : None }
    except Exception as e:
        return {"error": f"LLM output invalide : {e}" , "retries" : state.get("retries" ,0) + 1}



  def dry_run_node(self ,state):
      """ testing the dry_run first before updating the database"""
      try:
          out = self._run_spec(state["filepath"],state["spec"])
      except (UnsafeCodeError , SandboxError , ValueError) as e:
          return {"error": str(e), "retries": state.get("retries", 0) + 1}
      preview = json.loads(out.head(10).to_json(orient="records" , date_format ="iso"))
      return {"error" : None , "row_count" : len(out) , "preview": preview}
  
  
  
  def confirm_node(self ,state) :
      """Seeking for human approval"""
      decision = interrupt({
        "explanation" : state["spec"]["explanation"],
        "code" : state["spec"]["code"],
        "table_name" : state["spec"]["table_name"],
        "preview" : state["preview"],
        "row_count" : state["row_count"],
      })
      if isinstance(decision, dict):
          approved = bool(decision.get("approved", False))
          if approved:
              table_name = decision.get("table_name", state["spec"]["table_name"])
              spec = {**state["spec"], "table_name": table_name}
              return {"approved": True, "spec": spec}
          return {"approved": False}
      return {"approved" : bool(decision)}
  
  
  
  def _run_spec(self,filepath:str,spec:dict):
      """ Run the transform code on the extracted dataframe and return the transformed dataframe."""
      check_code(spec['code'])
      validate_table_name(spec["table_name"])
      df = extract_csv(filepath)
      out = run_transform(spec['code'],df)
      if out is None or len(out) == 0:
            raise ValueError("Transform returned an empty DataFrame.")
      return out
      
  
  def load_node(self ,state):
      """ Load to database with Dry_run False"""
      if not state["approved"]:
          return{"status" : "Cancelled"}
      try:
          out = self._run_spec(state["filepath"],state["spec"])
          load_to_sql(out , state["spec"]['table_name'] ,mode ="fail")
      except Exception as e:
          return{"status" : "failed" , "error" : str(e)}      
      return {"status" : "loaded"}

  
  def after_code(self ,state):
      if state.get("error"):
          return "code" if state.get("retries",0) < Max_Retries else END
      return "dry_run"
  
  def after_dry_run(self , state):
      if state.get("error"):
        return "code" if state["retries"] < Max_Retries else END
    
      if state["spec"]["kind"] == "analyze":
        return END
      
      return "confirm"
  
  
# Streamlit should only be able to do two things: start a run,
# and resume it after the human decides  So we wrap the graph in two simple methods. 
   
  def _cfg(self , thread_id:str):
      return {"configurable" : {"thread_id" :thread_id}}
  
  def start(self,filepath:str,instruction:str ,thread_id:str,history:str="None"):
      return self.app.invoke(
          {"filepath": filepath, "instruction": instruction , "history" : history},
            self._cfg(thread_id))
      
      
  def resume(
      self, thread_id: str, approved: bool, table_name: Optional[str] = None
  ):
      decision: dict[str, bool | str] = {"approved": approved}
      if table_name is not None:
          decision["table_name"] = table_name
      return self.app.invoke(Command(resume=decision),
                             self._cfg(thread_id))
  
#   Orchestator
  def build_graph(self):
        g = StateGraph(AgentState)
        g.add_node("inspect" , self.inspect_node)
        g.add_node("code", self.code_node)
        g.add_node("dry_run", self.dry_run_node)
        g.add_node("confirm", self.confirm_node)
        g.add_node("load", self.load_node)
        
        g.add_edge(START , "inspect")
        g.add_edge("inspect" , "code")
        g.add_conditional_edges("code", self.after_code,
                            {"dry_run" :"dry_run" , "code" : "code" , END : END})
        g.add_conditional_edges("dry_run", self.after_dry_run,
                            {"code": "code", "confirm": "confirm", END : END})
        
        g.add_edge("confirm", "load")
        g.add_edge("load", END)        
        return g.compile(checkpointer=MemorySaver())
        
      
   

    
    


    




