try:
    from sage.all import *  # type: ignore # noqa: F401,F403
    from sage.rings.polynomial.pbori import *  # type: ignore # noqa: F401,F403
except ImportError:
    # Allow pure-Python integer regression checks when Sage is unavailable.
    def declare_ring(*_args, **_kwargs):  # type: ignore
        raise ImportError("SageMath is required for declare_ring() and symbolic ANF operations.")


# Default global ring used by legacy callers.
R = None

# Ascon round constants for p[12].
ROUND_CONSTANTS = [0xF0, 0xE1, 0xD2, 0xC3, 0xB4, 0xA5, 0x96, 0x87, 0x78, 0x69, 0x5A, 0x4B]

LANE_SIZE = 64
LANE_COUNT = 5
STATE_SIZE = LANE_SIZE * LANE_COUNT
LINEAR_SHIFTS = [(19, 28), (61, 39), (1, 6), (10, 17), (7, 41)]

_INV_MATRIX_CACHE = {}


def _xor2(a, b):
    if isinstance(a, int) and isinstance(b, int):
        return a ^ b
    return a + b


def _xor_many(values):
    out = values[0]
    for v in values[1:]:
        out = _xor2(out, v)
    return out


def _zero_like(x):
    return 0 if isinstance(x, int) else x * 0


def _build_inverse_binary_matrix(size, r0, r1):
    """Build inverse matrix for y[i] = x[i] + x[i-r0] + x[i-r1] over GF(2)."""
    a = [[0 for _ in range(size)] for _ in range(size)]
    inv = [[1 if i == j else 0 for j in range(size)] for i in range(size)]

    for i in range(size):
        a[i][i] = 1
        a[i][(i - r0) % size] ^= 1
        a[i][(i - r1) % size] ^= 1

    col = 0
    for row in range(size):
        pivot = None
        for r in range(row, size):
            if a[r][col] == 1:
                pivot = r
                break
        while pivot is None and col < size - 1:
            col += 1
            for r in range(row, size):
                if a[r][col] == 1:
                    pivot = r
                    break
        if pivot is None:
            raise ValueError("Linear layer matrix is not invertible.")

        if pivot != row:
            a[row], a[pivot] = a[pivot], a[row]
            inv[row], inv[pivot] = inv[pivot], inv[row]

        for r in range(size):
            if r != row and a[r][col] == 1:
                for c in range(col, size):
                    a[r][c] ^= a[row][c]
                for c in range(size):
                    inv[r][c] ^= inv[row][c]
        col += 1
        if col >= size:
            break
    return inv


def _get_inverse_binary_matrix(r0, r1):
    key = (r0, r1)
    if key not in _INV_MATRIX_CACHE:
        _INV_MATRIX_CACHE[key] = _build_inverse_binary_matrix(LANE_SIZE, r0, r1)
    return _INV_MATRIX_CACHE[key]


def SingleMatrix(_R, X, r0, r1):
    """Apply Ascon lane linear map y = x ^ rot(x,r0) ^ rot(x,r1)."""
    y = []
    for i in range(LANE_SIZE):
        y.append(_xor_many([X[i], X[(i - r0) % LANE_SIZE], X[(i - r1) % LANE_SIZE]]))
    return y


def InvSingleMatrix(X, r0, r1):
    """Apply inverse of Ascon lane linear map."""
    inv = _get_inverse_binary_matrix(r0, r1)
    y = []
    for row in inv:
        terms = [X[j] for j, bit in enumerate(row) if bit == 1]
        y.append(_xor_many(terms))
    return y


def Matrix(X):
    """Apply Ascon linear layer to a 320-bit state."""
    out = list(X)
    for lane, (r0, r1) in enumerate(LINEAR_SHIFTS):
        base = lane * LANE_SIZE
        out[base : base + LANE_SIZE] = SingleMatrix(R, out[base : base + LANE_SIZE], r0, r1)
    return out


def InvMatrix(X):
    """Apply inverse Ascon linear layer to a 320-bit state."""
    out = list(X)
    for lane, (r0, r1) in enumerate(LINEAR_SHIFTS):
        base = lane * LANE_SIZE
        out[base : base + LANE_SIZE] = InvSingleMatrix(out[base : base + LANE_SIZE], r0, r1)
    return out


def SingleSbox(y0, y1, y2, y3, y4):
    """Apply Ascon 5-bit S-box."""
    x0 = y4 * y1 + y3 + y2 * y1 + y2 + y1 * y0 + y1 + y0
    x1 = y4 + y3 * y2 + y3 * y1 + y3 + y2 * y1 + y2 + y1 + y0
    x2 = y4 * y3 + y4 + y2 + y1 + 1
    x3 = y4 * y0 + y4 + y3 * y0 + y3 + y2 + y1 + y0
    x4 = y4 * y1 + y4 + y3 + y1 * y0 + y1
    return x0, x1, x2, x3, x4


def InvSingleSbox(y0, y1, y2, y3, y4):
    """Apply inverse Ascon 5-bit S-box."""
    x0 = y4 * y3 * y2 + y4 * y3 * y1 + y4 * y3 * y0 + y3 * y2 * y0 + y3 * y2 + y3 + y2 + y1 * y0 + y1 + 1
    x1 = y4 * y2 * y0 + y4 + y3 * y2 + y2 * y0 + y1 + y0
    x2 = y4 * y3 * y1 + y4 * y3 + y4 * y2 * y1 + y4 * y2 + y3 * y1 * y0 + y3 * y1 + y2 * y1 * y0 + y2 * y1 + y2 + 1 + x1
    x3 = y4 * y2 * y1 + y4 * y2 * y0 + y4 * y2 + y4 * y1 + y4 + y3 + y2 * y1 + y2 * y0 + y1
    x4 = y4 * y3 * y2 + y4 * y2 * y1 + y4 * y2 * y0 + y4 * y2 + y3 * y2 * y0 + y3 * y2 + y3 + y2 * y1 + y2 * y0 + y1 * y0
    return x0, x1, x2, x3, x4


def Sbox(Y):
    """Apply Ascon S-box layer to a 320-bit state."""
    z = [_zero_like(Y[0]) for _ in range(STATE_SIZE)]
    for j in range(LANE_SIZE):
        z[0 + j], z[64 + j], z[128 + j], z[192 + j], z[256 + j] = SingleSbox(
            Y[0 + j], Y[64 + j], Y[128 + j], Y[192 + j], Y[256 + j]
        )
    return z


def InvSbox(Y):
    """Apply inverse Ascon S-box layer to a 320-bit state."""
    z = [_zero_like(Y[0]) for _ in range(STATE_SIZE)]
    for j in range(LANE_SIZE):
        z[0 + j], z[64 + j], z[128 + j], z[192 + j], z[256 + j] = InvSingleSbox(
            Y[0 + j], Y[64 + j], Y[128 + j], Y[192 + j], Y[256 + j]
        )
    return z


def addConst(X, r):
    """XOR round constant to lane 2 of the state."""
    out = list(X)
    base = 64 * 2 + (64 - 8)
    rc = ROUND_CONSTANTS[r]
    for i in range(8):
        if (rc >> (7 - i)) & 1:
            out[base + i] = _xor2(out[base + i], 1)
    return out


def round(X, r):
    """Apply r forward Ascon rounds."""
    out = list(X)
    for i in range(r):
        out = addConst(out, i)
        out = Sbox(out)
        out = Matrix(out)
    return out


def Invround(X, r):
    """Apply inverse of r Ascon rounds."""
    out = list(X)
    for i in range(r - 1, -1, -1):
        out = InvMatrix(out)
        out = InvSbox(out)
        out = addConst(out, i)
    return out


def print_state(X: list, state_x=64, state_y=5) -> None:
    """Print state in binary lanes and hex lanes."""
    for y in range(state_y):
        lane_print = ""
        for x in range(state_x):
            lane_print += str(X[index_xy(x, y)]) if X[index_xy(x, y)] else "0"
        print(lane_print)
    print("------")
    for y in range(state_y):
        lane_print_0x = "0x"
        for x in range(0, state_x, 4):
            tmp = ""
            for i in range(4):
                tmp += str(X[index_xy(x + i, y)]) if X[index_xy(x + i, y)] else "0"
            lane_print_0x += hex(int(tmp, 2)).upper()[2:]
        print(lane_print_0x)
    print("------")


def index_xy(x: int, y: int) -> int:
    x, y = x % 64, y % 5
    return 64 * y + x


def hex2bin(Hex_in, Bin_len=64):
    return [(Hex_in >> (Bin_len - 1 - j)) & 0x1 for j in range(Bin_len)]


def index_z(z: int) -> int:
    return (z + 64) % 64


def bin2int(a: list) -> int:
    return int("".join(str(i) for i in a), 2)


def location2binvalue(location: list):
    bin_v = [0 for _ in range(64)]
    for i in range(64):
        if i in location:
            bin_v[i] = 1
    print(bin_v)
    return bin_v


def binvalue2location(bin_v: list):
    loc_v = []
    for i in range(64):
        if bin_v[i] == 1:
            loc_v.append(i)
    print(loc_v)
    return loc_v


def print_x(X: list, state_x=64) -> None:
    lane_print_0x = "0x"
    for x in range(0, state_x, 4):
        tmp = ""
        for i in range(4):
            tmp += str(X[x + i]) if X[x + i] else "0"
        lane_print_0x += hex(int(tmp, 2)).upper()[2:]
    return lane_print_0x


def hex_list_to_bit_list(hex_list):
    bit_list = []
    for hex_num in hex_list:
        bit_str = bin(int(hex_num, 16))[2:].zfill(64)
        bit_list.extend([int(bit) for bit in bit_str])
    return bit_list


def convert_diff_to_bit_list(Diff):
    return [hex_list_to_bit_list(hex_list) for hex_list in Diff]


if __name__ == "__main__":
    # Quick self-check in a Boolean ring.
    R = declare_ring([Block("X", 320), "u"], globals())
    sample = [R(0) for _ in range(320)]
    sample[0] = R(1)
    y = Matrix(sample)
    x = InvMatrix(y)
    print("Matrix/InvMatrix self-check:", all(x[i] == sample[i] for i in range(320)))
