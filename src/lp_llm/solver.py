from scipy.optimize import linprog

from lp_llm.schema import SCHEMA, get_valid_json,  respect_problem_perimeter

#https://docs.scipy.org/doc/scipy/reference/optimize.linprog-highs.html#optimize-linprog-highs

def get_status(status:int) -> str:
    if status == 0:
        return "optimal"
    elif status == 1:
        return "unsolved"
    elif status == 2:
        return "infeasible"
    elif status == 3:
        return "unbounded"
    else:
        return "invalid"
    
def solve_lp_problem(json_string: str) -> dict:
    bok, problem_lp = get_valid_json(json_string)
    if not bok:
        return {"status": "invalid", "message": problem_lp}
    
    bok, msg = respect_problem_perimeter(problem_lp, SCHEMA)

    if not bok:
        return {"status": "invalid", "message": msg}

    # Extracting the problem data

    c = problem_lp["objective"]["coefficients"]
    if problem_lp["objective"]["sense"] == "max":
        c = [-coeff for coeff in c]  # Convert maximization to minimization

    A_ub = []
    b_ub = []
    A_eq = []
    b_eq = []

    for constraint in problem_lp["constraints"]:
        if constraint["sense"] == "<=":
            A_ub.append(constraint["coefficients"])
            b_ub.append(constraint["rhs"])
        elif constraint["sense"] == ">=":
            A_ub.append([-coeff for coeff in constraint["coefficients"]]) #convert greater-than-or-equal to less-than-or-equal
            b_ub.append(-constraint["rhs"])
        elif constraint["sense"] == "=":
            A_eq.append(constraint["coefficients"])
            b_eq.append(constraint["rhs"])

    bounds = [tuple(bound) for bound in problem_lp["bounds"]]


    result = linprog(
        c, 
        A_ub=A_ub if A_ub else None, 
        b_ub=b_ub if b_ub else None,    
        A_eq=A_eq if A_eq else None, 
        b_eq=b_eq if b_eq else None,
        bounds=bounds,
        method='highs')

    if result.success:
        return {
            "status": get_status(result.status),
            "message": "Optimal solution found.",
            "solution": result.x.tolist(),
            "objective_value": -result.fun if problem_lp["objective"]["sense"] == "max" else result.fun
        }
    else:
        return {
            "status": get_status(result.status),
            "message": result.message
        }