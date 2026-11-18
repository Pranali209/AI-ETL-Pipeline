import ast

ALLOWED_IMPORTS = {"pandas" , "numpy" , "re" , "math" ,"datetime"}

BANNED_NAMES = {"open", "eval", "exec", "compile", "getattr", "setattr",
                "__import__", "input", "globals", "locals"}

BANNED_ATTRS = {"to_sql", "to_csv", "to_excel", "to_parquet", "to_pickle",
                "to_json", "to_hdf", "read_csv", "read_excel", "read_sql",
                "read_parquet", "read_pickle", "read_json", "read_html",
                "read_table", "read_fwf" ,"eval"}


class UnsafeCodeError(Exception):
    pass

def check_code(code:str) -> None:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise UnsafeCodeError(f"Code has a syntax error: {e}")
    
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_IMPORTS:
                    raise UnsafeCodeError(
                        f"Import of {root} is not allowed."
                        f"Allowed :{sorted(ALLOWED_IMPORTS)}")
        elif isinstance(node,ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in ALLOWED_IMPORTS:
                raise UnsafeCodeError(
                    f"Import from {root} is not allowed."
                    f"Allowed :{sorted(ALLOWED_IMPORTS)}")
        elif isinstance(node,ast.Name) and node.id in BANNED_NAMES:
            raise UnsafeCodeError(f"Use of {node.id} is not allowed")
        elif isinstance(node,ast.Attribute):
            if node.attr in BANNED_ATTRS:
              raise UnsafeCodeError(f"Use of {node.attr} is not allowed")
            if node.attr.startswith("__"):
                raise UnsafeCodeError("Dunder attributes (like __class__) are not allowed.")
                
                
        