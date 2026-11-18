from pydantic import BaseModel, Field

from typing import Literal

class TransformSpec(BaseModel):
    kind: Literal["transform", "analyze"] = Field(
        description="'analyze' if the user only asks a question about the data, 'transform' if they want the data changed"
    )
    explanation : str = Field(description = "Plain-english summary of what the code does ")
    code :str = Field(description = "Python code that defines the def transform(df)and returns a dataframe")
    table_name :str =Field(description = "snake_case name MySQL table name, e.g. sales_clean")

    