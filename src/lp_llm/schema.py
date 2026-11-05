import json
from typing import Any
import math 

SCHEMA = {
            "variables": list,
            "objective": dict,
            "constraints": list,
            "bounds": list
        }

def get_valid_json(json_string: str) -> tuple[bool, Any]:
    try:
        data = json.loads(json_string)
        return True, data
    except (ValueError, TypeError, RecursionError) as e:
        return False,  f"Invalid JSON: {e}"

def respect_schema(data: Any, schema: dict) -> tuple[bool,str]:
    if not isinstance(data, dict):
        return False, "Input data is not a dictionary"
    for key, value in schema.items():
        if key not in data:
            return False, f"Key '{key}' is missing from the data"

        if not isinstance(data[key], value):
            return False, f"Value for key '{key}' is not of type {value.__name__}"
    return True, "Data respects the schema."

def is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    if isinstance(value, int):
      return True

    return math.isfinite(value)


def respect_problem_perimeter(data: Any, schema: dict) -> tuple[bool,str]:
    is_valid, message = respect_schema(data, schema)
    if not is_valid:
        return False, message
    
    extra_keys = set(data) - set(schema)
    if extra_keys:
        return False, f"Unexpected keys at top level: {sorted(extra_keys)}"

    if len(data["variables"]) !=2 :
        return False, "Number of variables is not equal to 2"

    if data["variables"] != ["x1", "x2"]:
        return False, "Variables are not named 'x1' and 'x2'"
    
    if "coefficients" not in data["objective"] :
        return False, "Objective does not have the required keys 'coefficients'"

    if "sense" not in data["objective"]:
        return False, "Objective does not have the required keys 'sense'"

    if not isinstance(data["objective"]["coefficients"], list):
        return False, "Coefficients in objective is not a list"
    
    if not all(is_number(coef) for coef in data["objective"]["coefficients"]):
        return False, "Coefficients in objective are not all numbers"
    
    if len(data["objective"]["coefficients"]) != 2:
        return False, "Number of coefficients in objective is not equal to 2"
    
    extra_keys = set(data["objective"]) - {"coefficients", "sense"}
    if extra_keys:
        return False, f"Unexpected keys in objective: {sorted(extra_keys)}"

    if data["objective"]["sense"] not in ["max", "min"]:
        return False, "Objective sense is neither \"max\" nor \"min\""

    if len(data["constraints"]) >1: # on a dit qu'on voulait au moins 2 contraintes, mais pas plus de 3
        if len(data["constraints"]) >3:
            return False, "Number of constraints is greater than 3"
        
        for constraint in data["constraints"]:

            if not isinstance(constraint, dict):
                return False, "Constraint is not a dictionary"
            
            if "coefficients" not in constraint:
                return False, "Constraint does not have the required keys 'coefficients'"
            if "sense" not in constraint:
                return False, "Constraint does not have the required keys 'sense'"
            if "rhs" not in constraint:
                return False, "Constraint does not have the required keys 'rhs'"
            
            extra_keys = set(constraint) - {"coefficients", "sense", "rhs"}
            if extra_keys:
                return False, f"Unexpected keys in constraint: {sorted(extra_keys)}"

            if constraint["sense"] not in ["<=", ">=", "="]:
                return False, "Constraint sense is neither \"<=\", \">=\", nor \"=\""
            if not is_number(constraint["rhs"]):
                return False, "Constraint rhs is not a number"
            
            if not isinstance(constraint["coefficients"], list):
                return False, "Coefficients in constraint is not a list"
            if len(constraint["coefficients"]) != 2:
                return False, "Number of coefficients in constraint is not equal to 2"
            if not all(is_number(coef) for coef in constraint["coefficients"]):
                return False, "Coefficients in constraint are not all numbers"
    else:
        return False, "Number of constraints is less than 2"
    
    if len(data["bounds"]) != 2:
        return False, "Number of bounds is not equal to 2"
   

    for bound in data["bounds"]:
        if not isinstance(bound, list):
            return False, "Bound is not a list"
        if len(bound) != 2 :
            return False, "Each bound must have exactly two elements"
        if bound[0] is None or not is_number(bound[0]):
            return False, "Lower bound is not a number"

        if bound[0] < 0:
            return False, "Lower bound must be non-negative"

        if bound[1] is not None and not is_number(bound[1]):
            return False, "Upper bound is not a number"

        if bound[1] is not None and bound[1] < bound[0]:
            return False, "Lower bound is greater than upper bound"


    return True, "Data respects the problem perimeter."

def complete_check(schema, bad_json1):
    bool_result, data = get_valid_json(bad_json1)

    if bool_result:
        is_valid, message = respect_problem_perimeter(data, schema)
        if is_valid:
            print("The JSON data respects the problem perimeter.")
        else:
            print(f"The JSON data does not respect the problem perimeter: {message} ")
            
    else:
        print("The JSON data is not valid.")