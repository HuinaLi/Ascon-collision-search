
import argparse


"""read solution from solution file"""
def read_sol_ls(sol_path: str, ROUNDS: int, solution_sign="s SATISFIABLE", line_split="v", state_x=64, state_y=5, state=320,rate=64) -> list:
    # var number of A,B,NK
    var_num = state
    # extract the solution from cnf solution file
    with open(sol_path, "r") as f:
        contents = f.read()
    # find solution_sign "s SATISFIABLE"
    i = contents.find(solution_sign)
    if i < 0:
        return None
    i += len(solution_sign) + 1
    # get the contents after "s SATISFIABLE"
    lines = contents[i:].split(line_split)
    sol = []
    # get the solution of A,B,D,M0,M1
    for line in lines:
        vars = line.split()
        for var in vars:
            if int(var) == 0:
                continue
            v = 0 if int(var) < 0 else 1
            sol.append(v)
        if len(sol) >= var_num:
            break
    sol = sol[:var_num]
    # print(f"sol:\n{sol}")
    
    return sol

"""add ban solution list to cnf"""
def add_ban2cnf(ROUNDS: int, cnf_path: str, ban_list: list, state=320) -> None:
    
    ban_cnf = ""
    # add each solution
    for i in range(len(ban_list)):
        v = ban_list[i]
        if v:
            ban_cnf += "-" + str(i+1) + " "
        else:
            ban_cnf += str(i+1) + " "
            
    ban_cnf += "0\n"

    # read previous cnf
    with open(cnf_path, "r") as f:
        cnf_info = f.readline().split(" ")
        # get previous cnf infomation
        var_num, clause_num = int(cnf_info[2]), int(cnf_info[3])
        pre_cnf = f.read()
        # modify content
        clause_num += 1
        new_cnf = pre_cnf + ban_cnf
    
    # write ban to cnf
    with open(cnf_path, "w") as f:
        f.write(f"p cnf {var_num} {clause_num}\n")
        f.write(new_cnf)


if __name__ == "__main__":
    parse = argparse.ArgumentParser(description="add banned solutions to cnf")
    parse.add_argument("-c", "--cnf", type=str, help="cnf file")
    parse.add_argument("-s", "--solution", type=str, help="solution file")
    parse.add_argument("-r", "--rounds", type=int, help="rounds of the solution")
    args = parse.parse_args()

    a = read_sol_ls(args.solution, args.rounds)

    if not a:
        raise ValueError("solution not found")
    add_ban2cnf(args.rounds, args.cnf, a)