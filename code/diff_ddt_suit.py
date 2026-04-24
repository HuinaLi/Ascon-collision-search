####################################################################################
# Function: This is a template for generating all the basic properties in differential analysis
# DDT in binlist, intlist
# Author: Huina
# Aug 29th, 2024
####################################################################################
import sys

AsconSbox = [4, 11, 31, 20, 26, 21, 9, 2, 27, 5, 8, 18, 29, 3, 6, 28, 30, 19, 7, 14, 0, 13, 17, 24, 16, 12, 1, 25, 22, 10, 15, 23]

def int2bin(a: int, n: int) -> str:
    """Convert an integer to a zero-padded binary string.

    Args:
        a (int): Input integer.
        n (int): Target bit length.

    Returns:
        str: Binary string.
    """
    return "{0:b}".format(a).rjust(n,"0")

def reverseSBox(S_box):
    res = [0] * len(S_box)
    for i in range(len(S_box)):
        res[S_box[i]] = i
    return res

def generatePairsWithDifference(diff, len_of_Sbox):
    result = []
    for x in range(len_of_Sbox):
        for y in range(len_of_Sbox):
            if x ^ y == diff:
               result.append((x, y))
               break 
    return result

def getDDTForSBox(S_box):
    n = len(S_box)
    DDT = [[0]*n for _ in range(n)]
    DDT[0][0] = n
    differentialUniformity = 0
    for a in range(n):
        for b in range(n):
            if a == 0 and b == 0:
                continue
            for x in range(n):
                if S_box[x ^ a] ^ S_box[x] == b:
                    DDT[a][b] += 1
            differentialUniformity = max(differentialUniformity, DDT[a][b])
    print(f"\nDifferential Uniformity of SBox: {differentialUniformity}")
    return DDT

def printDDT(DDT):
    if len(DDT) == 16:
        print("\t|0\t1\t2\t3\t4\t5\t6\t7\t8\t9\tA\tB\tC\tD\tE\tF")
    if len(DDT) == 32:
        print("\t|0\t1\t2\t3\t4\t5\t6\t7\t8\t9\tA\tB\tC\tD\tE\tF\t10\t11\t12\t13\t14\t15\t16\t17\t18\t19\t1A\t1B\t1C\t1D\t1E\t1F")
    print("----------------------------------------------------------------------------------------------------------------------------------")
    
    for k in range(len(DDT)):
        s = str(k) + "\t|"
        for i in DDT[k]:
            s = s + str(i) + "\t"
        print(s)

def VaildDiffInOutWithWeight(S_box):
    ddt = getDDTForSBox(S_box)
    result = []
    for diff_in in range(len(S_box)):
        for diff_out in range(len(S_box)):
            if ddt[diff_in][diff_out]:
                result.append([diff_in, diff_out, ddt[diff_in][diff_out]])
    # for l in result:
    #     print(f"alpha: {l[0]}, beta: {l[1]}, omiga: {l[2]}")
    return result

def VaildDiffInOut(S_box):
    ddt = getDDTForSBox(S_box)
    result = []
    for diff_in in range(len(S_box)):
        for diff_out in range(len(S_box)):
            if ddt[diff_in][diff_out]:
                if diff_in == 0:
                    result.append([diff_in, diff_out, 0])
                else:
                    result.append([diff_in, diff_out, 1])
    return result


def weight2bin(weight:int, S_box_size:int=32, min_weight:int=2) -> list:
    length = len(bin(S_box_size//min_weight)) - 3
    num_zero = len(bin(weight//min_weight)) - 3
    num_one = length - num_zero
    return [0]*num_zero + [1]*num_one

#[diff_in, diff_out, weight]
def intlist2binlistWithWeight(inlist:list, S_box_size:int=32, min_weight:int=2) -> list:
    binlist = []
    for l in inlist:
        diff_in = [int(x) for x in int2bin(l[0], 5)]
        diff_out = [int(x) for x in int2bin(l[1], 5)]
        weight = weight2bin(l[2])
        tmp = diff_in + diff_out + weight
        binlist.append(tmp)
    return binlist

#[diff_in, diff_out, activeSbox]
def intlist2binlistWithAs(inlist:list, S_box_size:int=32) -> list:
    binlist = []
    for l in inlist:
        diff_in = [int(x) for x in int2bin(l[0], 5)]
        diff_out = [int(x) for x in int2bin(l[1], 5)]
        asbox = [int(x) for x in int2bin(l[2], 1) ]
        tmp = diff_in + diff_out + asbox
        binlist.append(tmp)
    return binlist

#special [diff_in, diff_out, activeSbox]
def S_intlist2binlistWithAs(inlist:list, S_box_size:int=32) -> list:
    binlist = []
    for l in inlist:
        diff_in = [int(x) for x in int2bin(l[0], 5)]
        diff_out = [int(x) for x in int2bin(l[1], 5)]
        asbox = [int(x) for x in int2bin(l[2], 1) ]
        if (diff_in[2] == 0) and (diff_in not in [[0,1,0,0,1],[0,1,0,1,1],[1,0,0,1,0],[1,1,0,0,0],[1,1,0,1,1]] ):
            tmp = diff_in + diff_out + asbox
        else:
            continue
        binlist.append(tmp)
    return binlist

#special [diff_in, w4] weight4
def w4_intlist2binlistWithAs( S_box_size:int=32) -> list:
    binlist = []
    for l in range(32):
        diff_in = [int(x) for x in int2bin(l, 5)]
        if diff_in  in [[0,0,1,1,0],[0,1,0,0,1],[0,1,0,1,0],[0,1,0,1,1],[0,1,1,0,1],[1,0,0,1,0],[1,0,1,1,0],[1,1,0,0,0],[1,1,0,1,0],[1,1,0,1,1],[1,1,1,1,0]]:
            tmp = diff_in + [1]
        else:
            tmp = diff_in + [0] 
        binlist.append(tmp)
    return binlist
if __name__ == '__main__':
    
    inlist = VaildDiffInOut(AsconSbox )
    out = S_intlist2binlistWithAs(inlist)
    print(len(out),out)
    
    # mydic = {}
    # for i in range(32):
    #     tmp = tuple([int(x) for x in int2bin(i,5)])
    #     mydic[tmp] = 0
    
    # for o in out:
    #     if tuple(o[5:-1]) in mydic:
    #         mydic[tuple(o[5:-1])] += 1
    #     else: 
    #         continue
    
    # res = dict(sorted(mydic.items(), key=lambda v:v[1], reverse=True))
    # sumc = sum(mydic.values())
    # print(res)
    # print(len(mydic.values()),sumc)
    # print(mydic)
    


        

    
