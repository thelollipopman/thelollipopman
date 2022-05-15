from gmpy2 import bit_scan1
from timeit import timeit
from subprocess import Popen, PIPE
import time
import re
import heapq
import threading

# https://github.com/maksimKorzh/chess_programming/tree/master/src/bbc

MAX_PLY = 64
INFINITY = 50000
MATE_LOWERBOUND = 48000
MATE_UPPERBOUND = 49000

stockfish_path = r'/storage/emulated/0/pythonscripts/stockfish_14.1_android_armv7/stockfish_14.1_android_armv7/stockfish.android.armv7'

# stockfish_path = r"C:\Users\Cheng Yong\PycharmProject\chessgame\chessgame scripts\stockfish_14.1_win_x64_popcnt\stockfish_14.1_win_x64_popcnt.exe"

# ---------------------------------------------
# GENERAL UTILS AND STUFF
# ---------------------------------------------

WHITE, BLACK, BOTH = 0, 1, 2

SQUARES = [
    a8, b8, c8, d8, e8, f8, g8, h8,
    a7, b7, c7, d7, e7, f7, g7, h7,
    a6, b6, c6, d6, e6, f6, g6, h6,
    a5, b5, c5, d5, e5, f5, g5, h5,
    a4, b4, c4, d4, e4, f4, g4, h4,
    a3, b3, c3, d3, e3, f3, g3, h3,
    a2, b2, c2, d2, e2, f2, g2, h2,
    a1, b1, c1, d1, e1, f1, g1, h1,
] = range(64)

sq_to_coord = [
    'a8', 'b8', 'c8', 'd8', 'e8', 'f8', 'g8', 'h8',
    'a7', 'b7', 'c7', 'd7', 'e7', 'f7', 'g7', 'h7',
    'a6', 'b6', 'c6', 'd6', 'e6', 'f6', 'g6', 'h6',
    'a5', 'b5', 'c5', 'd5', 'e5', 'f5', 'g5', 'h5',
    'a4', 'b4', 'c4', 'd4', 'e4', 'f4', 'g4', 'h4',
    'a3', 'b3', 'c3', 'd3', 'e3', 'f3', 'g3', 'h3',
    'a2', 'b2', 'c2', 'd2', 'e2', 'f2', 'g2', 'h2',
    'a1', 'b1', 'c1', 'd1', 'e1', 'f1', 'g1', 'h1'
]

RECT_LOOKUP = []
RANKS = []
FILES = []
NWSE = []
NESW = []


def init_lines():
    for i in range(8):
        RANKS.append(0xff << (i * 8))
        j = 1 << i
        FILES.append(j | (j << 8) | (j << 16) | (j << 24) | (j << 32) | (j << 40) | (j << 48) | (j << 56))
    for i in range(8):
        nesw = 0
        for rank, file in zip(range(8), range(i, -1, -1)):
            nesw |= 1 << (rank * 8 + file)
        NESW.append(nesw)
    for i in range(1, 8):
        nesw = 0
        for rank, file in zip(range(7, -1, -1), range(i, 8)):
            nesw |= 1 << (rank * 8 + file)
        NESW.append(nesw)
    for i in range(7, -1, -1):
        nwse = 0
        for rank, file in zip(range(8), range(i, 8)):
            nwse |= 1 << (rank * 8 + file)
        NWSE.append(nwse)
    for i in range(6, -1, -1):
        nwse = 0
        for rank, file in zip(range(7, -1, -1), range(i, -1, -1)):
            nwse |= 1 << (rank * 8 + file)
        NWSE.append(nwse)


def init_rect_lookup():
    global RECT_LOOKUP
    RECT_LOOKUP = [[0 for i in range(64)] for j in range(64)]
    for sq1 in range(64):
        rank1 = sq1 // 8
        file1 = sq1 % 8
        nesw1 = rank1 + file1
        nwse1 = rank1 + (7 - file1)
        for sq2 in range(64):
            rank2 = sq2 // 8
            file2 = sq2 % 8
            nesw2 = rank2 + file2
            nwse2 = rank2 + (7 - file2)
            sq_between = (-1 << sq1) ^ (-1 << sq2)
            # pieces on same rank
            if rank1 == rank2:
                mask = RANKS[rank1]
            # pieces on same file
            elif file1 == file2:
                mask = FILES[file1]
            # pieces on same nwse diagonal
            elif nwse1 == nwse2:
                mask = NWSE[nwse1]
            # pieces on same nesw diagonal
            elif nesw1 == nesw2:
                mask = NESW[nesw2]
            else:
                continue
            mask &= sq_between
            mask |= (1 << sq1) | (1 << sq2)
            mask ^= (1 << sq2)
            RECT_LOOKUP[sq1][sq2] = mask


def set_bit(bb, square):
    bb |= 1 << square
    return bb


def get_bit(bb, square):
    return bb & 1 << square


def pop_bit(bb, square):
    return bb ^ (1 << square)


def flip_bit(bb):
    return bb ^ 0xFFFFFFFFFFFFFFFF


def get_set_bits_idx(bb):
    i = bit_scan1(bb)
    while i != None:
        yield i
        i = bit_scan1(bb, i + 1)


def pprint_bb(bb):
    print()
    for rank in range(8):
        print(' {:d} '.format(8 - rank), end=' ')
        for file in range(8):
            sq = rank * 8 + file
            print(1 if get_bit(bb, sq) else 0, end=' ')
        print()
    print('    a b c d e f g h')
    print('  Bitboard: {}   '.format(bb))


init_lines()
init_rect_lookup()

# ---------------------------------------------
# JUMPING PIECES
# ---------------------------------------------

pawn_attacks = [[], []]
knight_attacks = []
king_attacks = []

not_a_file = 18374403900871474942
not_h_file = 9187201950435737471
not_hg_file = 4557430888798830399
not_ab_file = 18229723555195321596
not_1_rank = 0xffffffffffffff
not_12_rank = 0xffffffffffff
not_78_rank = 0xffffffffffff0000
not_8_rank = 0xffffffffffffff00
rank_1 = 0xff00000000000000
rank_2 = 0xff000000000000
rank_3 = 0xff0000000000
rank_4 = 0xff00000000
rank_5 = 0xff000000
rank_6 = 0xff0000
rank_7 = 0xff00
rank_8 = 0xff


def mask_pawn_attacks(side, square):
    pawn = 1 << square
    attacks = 0
    if not side:
        if pawn & not_h_file:
            attacks |= pawn >> 7
        if pawn & not_a_file:
            attacks |= pawn >> 9
    else:
        if pawn & not_a_file:
            attacks |= pawn << 7
        if pawn & not_h_file:
            attacks |= pawn << 9
    return attacks


def mask_knight_attacks(square):
    knight = 1 << square
    attacks = 0
    if (knight >> 15) & not_a_file: attacks |= knight >> 15
    if (knight >> 17) & not_h_file: attacks |= knight >> 17
    if (knight >> 6) & not_ab_file: attacks |= knight >> 6
    if (knight >> 10) & not_hg_file: attacks |= knight >> 10
    if (knight << 15) & not_h_file: attacks |= knight << 15
    if (knight << 17) & not_a_file: attacks |= knight << 17
    if (knight << 6) & not_hg_file: attacks |= knight << 6
    if (knight << 10) & not_ab_file: attacks |= knight << 10
    return attacks


def mask_king_attacks(square):
    king = 1 << square
    attacks = 0
    if king & not_a_file: attacks |= (king >> 1)
    if king & not_h_file: attacks |= (king << 1)
    if king & not_1_rank: attacks |= (king << 8)
    if king & not_8_rank: attacks |= (king >> 8)
    if king & not_a_file and king & not_8_rank: attacks |= (king >> 9)
    if king & not_a_file and king & not_1_rank: attacks |= (king << 7)
    if king & not_h_file and king & not_8_rank: attacks |= (king >> 7)
    if king & not_h_file and king & not_1_rank: attacks |= (king << 9)
    return attacks


def get_pawn_attacks(side, square):
    return pawn_attacks[side][square]


def get_knight_attacks(square):
    return knight_attacks[square]


def get_king_attacks(square):
    return king_attacks[square]


def init_jumping_attacks():
    for sq in SQUARES:
        pawn_attacks[WHITE].append(mask_pawn_attacks(WHITE, sq))
        pawn_attacks[BLACK].append(mask_pawn_attacks(BLACK, sq))
        knight_attacks.append(mask_knight_attacks(sq))
        king_attacks.append(mask_king_attacks(sq))


# ---------------------------------------------
# SLIDING PIECES
# ---------------------------------------------
ROOK, BISHOP = 0, 1

bishop_bit_counts = [
    6, 5, 5, 5, 5, 5, 5, 6,
    5, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 7, 7, 7, 7, 5, 5,
    5, 5, 7, 9, 9, 7, 5, 5,
    5, 5, 7, 9, 9, 7, 5, 5,
    5, 5, 7, 7, 7, 7, 5, 5,
    5, 5, 5, 5, 5, 5, 5, 5,
    6, 5, 5, 5, 5, 5, 5, 6,
]

rook_bit_counts = [
    12, 11, 11, 11, 11, 11, 11, 12,
    11, 10, 10, 10, 10, 10, 10, 11,
    11, 10, 10, 10, 10, 10, 10, 11,
    11, 10, 10, 10, 10, 10, 10, 11,
    11, 10, 10, 10, 10, 10, 10, 11,
    11, 10, 10, 10, 10, 10, 10, 11,
    11, 10, 10, 10, 10, 10, 10, 11,
    12, 11, 11, 11, 11, 11, 11, 12,
]


def mask_bishop_attacks(square):
    rank, file = square // 8, square % 8
    attacks = 0
    for r, f in zip(range(rank + 1, 7), range(file + 1, 7)):
        attacks |= 1 << (r * 8 + f)
    for r, f in zip(range(rank - 1, 0, -1), range(file - 1, 0, -1)):
        attacks |= 1 << (r * 8 + f)
    for r, f in zip(range(rank + 1, 7), range(file - 1, 0, -1)):
        attacks |= 1 << (r * 8 + f)
    for r, f in zip(range(rank - 1, 0, -1), range(file + 1, 7)):
        attacks |= 1 << (r * 8 + f)
    return attacks


def bishop_attacks_on_the_fly(square, block):
    rank, file = square // 8, square % 8
    attacks = 0
    for r, f in zip(range(rank + 1, 8), range(file + 1, 8)):
        attacks |= 1 << (r * 8 + f)
        if block & (1 << (r * 8 + f)):
            break
    for r, f in zip(range(rank - 1, -1, -1), range(file - 1, -1, -1)):
        attacks |= 1 << (r * 8 + f)
        if block & (1 << (r * 8 + f)):
            break
    for r, f in zip(range(rank + 1, 8), range(file - 1, -1, -1)):
        attacks |= 1 << (r * 8 + f)
        if block & (1 << (r * 8 + f)):
            break
    for r, f in zip(range(rank - 1, -1, -1), range(file + 1, 8)):
        attacks |= 1 << (r * 8 + f)
        if block & (1 << (r * 8 + f)):
            break
    return attacks


def mask_rook_attacks(square):
    rank, file = square // 8, square % 8
    attacks = 0
    for r in range(rank + 1, 7):
        attacks |= 1 << (r * 8 + file)
    for r in range(rank - 1, 0, -1):
        attacks |= 1 << (r * 8 + file)
    for f in range(file + 1, 7):
        attacks |= 1 << (rank * 8 + f)
    for f in range(file - 1, 0, -1):
        attacks |= 1 << (rank * 8 + f)
    return attacks


def rook_attacks_on_the_fly(square, block):
    rank, file = square // 8, square % 8
    attacks = 0
    for r in range(rank + 1, 8):
        attacks |= 1 << (r * 8 + file)
        if block & (1 << (r * 8 + file)):
            break
    for r in range(rank - 1, -1, -1):
        attacks |= 1 << (r * 8 + file)
        if block & (1 << (r * 8 + file)):
            break
    for f in range(file + 1, 8):
        attacks |= 1 << (rank * 8 + f)
        if block & (1 << (rank * 8 + f)):
            break
    for f in range(file - 1, -1, -1):
        attacks |= 1 << (rank * 8 + f)
        if block & (1 << (rank * 8 + f)):
            break
    return attacks


# MAGIC NUMBER GENERATION

def count_bits(bb):
    return bin(bb).count('1')


def get_lsb_index(bb):
    return (bb & -bb).bit_length() - 1


def set_occupancy(index, bits_in_mask, attack_mask):
    occupancy = 0
    for i in range(bits_in_mask):
        square = get_lsb_index(attack_mask)
        attack_mask = pop_bit(attack_mask, square)
        if index & 1 << i:
            occupancy |= 1 << square
    return occupancy


state = 1804289383


def get_random_32int():
    global state
    number = state
    number ^= (number << 13) & 0xffffffff
    number ^= number >> 17
    number ^= (number << 5) & 0xffffffff
    state = number
    return number


def get_random_64int():
    n1 = get_random_32int() & 0xffff
    n2 = get_random_32int() & 0xffff
    n3 = get_random_32int() & 0xffff
    n4 = get_random_32int() & 0xffff
    return n1 | (n2 << 16) | (n3 << 32) | (n4 << 48)


def get_magic_candidate():
    return get_random_64int() & get_random_64int() & get_random_64int()


def get_magic_num(square, bit_count, piece):
    occupancies = []
    attacks = []
    attack_mask = mask_rook_attacks(square) if piece == ROOK else mask_bishop_attacks(square)
    attack_on_the_fly = rook_attacks_on_the_fly if piece == ROOK else bishop_attacks_on_the_fly
    occupancy_indices = 1 << bit_count
    for i in range(occupancy_indices):
        occupancies.append(set_occupancy(i, bit_count, attack_mask))
        attacks.append(attack_on_the_fly(square, occupancies[i]))
    for i in range(100000000):
        magic_num = get_magic_candidate()
        if count_bits((attack_mask * magic_num) & 0xff00000000000000) < 6:
            continue
        used_attacks = [0] * 4096
        fail = False
        for j in range(occupancy_indices):
            magic_index = ((occupancies[j] * magic_num) & 0xffffffffffffffff) >> (64 - bit_count)
            if used_attacks[magic_index] == 0:
                used_attacks[magic_index] = attacks[j]
            elif used_attacks[magic_index] != attacks[j]:
                fail = True
                break
        if not fail:
            return magic_num
    print('magic number fails')
    return 0


def init_magic_numbers():
    for square in range(64):
        print('0x{0:x},'.format(get_magic_num(square, bishop_bit_counts[square], BISHOP)))
    for square in range(64):
        print('0x{0:x},'.format(get_magic_num(square, rook_bit_counts[square], ROOK)))


bishop_magic_numbers = [
    0x40040822862081, 0x40810a4108000, 0x2008008400920040, 0x61050104000008, 0x8282021010016100, 0x41008210400a0001,
    0x3004202104050c0, 0x22010108410402,
    0x60400862888605, 0x6311401040228, 0x80801082000, 0x802a082080240100, 0x1860061210016800, 0x401016010a810,
    0x1000060545201005, 0x21000c2098280819,
    0x2020004242020200, 0x4102100490040101, 0x114012208001500, 0x108000682004460, 0x7809000490401000,
    0x420b001601052912, 0x408c8206100300, 0x2231001041180110,
    0x8010102008a02100, 0x204201004080084, 0x410500058008811, 0x480a040008010820, 0x2194082044002002,
    0x2008a20001004200, 0x40908041041004, 0x881002200540404,
    0x4001082002082101, 0x8110408880880, 0x8000404040080200, 0x200020082180080, 0x1184440400114100, 0xc220008020110412,
    0x4088084040090100, 0x8822104100121080,
    0x100111884008200a, 0x2844040288820200, 0x90901088003010, 0x1000a218000400, 0x1102010420204, 0x8414a3483000200,
    0x6410849901420400, 0x201080200901040,
    0x204880808050002, 0x1001008201210000, 0x16a6300a890040a, 0x8049000441108600, 0x2212002060410044, 0x100086308020020,
    0x484241408020421, 0x105084028429c085,
    0x4282480801080c, 0x81c098488088240, 0x1400000090480820, 0x4444000030208810, 0x1020142010820200, 0x2234802004018200,
    0xc2040450820a00, 0x2101021090020
]

rook_magic_numbers = [
    0xa080041440042080, 0xa840200410004001, 0xc800c1000200081, 0x100081001000420, 0x200020010080420, 0x3001c0002010008,
    0x8480008002000100, 0x2080088004402900,
    0x800098204000, 0x2024401000200040, 0x100802000801000, 0x120800800801000, 0x208808088000400, 0x2802200800400,
    0x2200800100020080, 0x801000060821100,
    0x80044006422000, 0x100808020004000, 0x12108a0010204200, 0x140848010000802, 0x481828014002800, 0x8094004002004100,
    0x4010040010010802, 0x20008806104,
    0x100400080208000, 0x2040002120081000, 0x21200680100081, 0x20100080080080, 0x2000a00200410, 0x20080800400,
    0x80088400100102, 0x80004600042881,
    0x4040008040800020, 0x440003000200801, 0x4200011004500, 0x188020010100100, 0x14800401802800, 0x2080040080800200,
    0x124080204001001, 0x200046502000484,
    0x480400080088020, 0x1000422010034000, 0x30200100110040, 0x100021010009, 0x2002080100110004, 0x202008004008002,
    0x20020004010100, 0x2048440040820001,
    0x101002200408200, 0x40802000401080, 0x4008142004410100, 0x2060820c0120200, 0x1001004080100, 0x20c020080040080,
    0x2935610830022400, 0x44440041009200,
    0x280001040802101, 0x2100190040002085, 0x80c0084100102001, 0x4024081001000421, 0x20030a0244872, 0x12001008414402,
    0x2006104900a0804, 0x1004081002402
]

bishop_masks = []
rook_masks = []

bishop_attacks = [[0] * 512 for _ in range(64)]
rook_attacks = [[0] * 4096 for _ in range(64)]


def init_sliding_attacks():
    for sq in SQUARES:
        bishop_attack_mask = mask_bishop_attacks(sq)
        bishop_masks.append(bishop_attack_mask)
        bishop_bit_count = bishop_bit_counts[sq]
        for i in range(1 << bishop_bit_count):
            occupancy = set_occupancy(i, bishop_bit_count, bishop_attack_mask)
            magic_index = ((occupancy * bishop_magic_numbers[sq]) & 0xffffffffffffffff) >> (64 - bishop_bit_count)
            bishop_attacks[sq][magic_index] = bishop_attacks_on_the_fly(sq, occupancy)
        rook_attack_mask = mask_rook_attacks(sq)
        rook_masks.append(rook_attack_mask)
        rook_bit_count = rook_bit_counts[sq]
        for i in range(1 << rook_bit_count):
            occupancy = set_occupancy(i, rook_bit_count, rook_attack_mask)
            magic_index = ((occupancy * rook_magic_numbers[sq]) & 0xffffffffffffffff) >> (64 - rook_bit_count)
            rook_attacks[sq][magic_index] = rook_attacks_on_the_fly(sq, occupancy)


def get_bishop_attacks(sq, occupancy):
    occupancy &= bishop_masks[sq]
    occupancy *= bishop_magic_numbers[sq]
    occupancy &= 0xffffffffffffffff
    occupancy >>= (64 - bishop_bit_counts[sq])
    return bishop_attacks[sq][occupancy]


def get_xray_bishop_attacks(sq, blockers, occupancy):
    attacks = get_bishop_attacks(sq, occupancy)
    blockers &= attacks
    return attacks ^ (get_bishop_attacks(sq, occupancy ^ blockers))


def get_rook_attacks(sq, occupancy):
    occupancy &= rook_masks[sq]
    occupancy *= rook_magic_numbers[sq]
    occupancy &= 0xffffffffffffffff
    occupancy >>= (64 - rook_bit_counts[sq])
    return rook_attacks[sq][occupancy]


def get_xray_rook_attacks(sq, blockers, occupancy):
    attacks = get_rook_attacks(sq, occupancy)
    blockers &= attacks
    return attacks ^ (get_rook_attacks(sq, occupancy ^ blockers))


def get_queen_attacks(sq, occupancy):
    return get_bishop_attacks(sq, occupancy) | get_rook_attacks(sq, occupancy)


# ---------------------------------------------
# DRIVER CODE
# ---------------------------------------------

def init_lookups():
    init_lines()
    init_rect_lookup()
    init_jumping_attacks()
    init_sliding_attacks()


init_lookups()

wk, wq, bk, bq = 1, 2, 4, 8
CASTLING_RIGHTS = [
    7, 15, 15, 15, 3, 15, 15, 11,
    15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15,
    13, 15, 15, 15, 12, 15, 15, 14
]
PIECES = [P, N, B, R, K, Q, p, n, b, r, k, q] = range(12)
PIECES_BY_COLOUR = [[P, N, B, R, K, Q],
                    [p, n, b, r, k, q]]

ascii_pieces = [['P', 'N', 'B', 'R', 'K', 'Q'], ['p', 'n', 'b', 'r', 'k', 'q', '.']]

unicode_pieces = [
    ['♙', '♘', '♗', '♖', '♔', '♕'],
    ['♟︎', '♞', '♝', '♜', '♚', '♛']
]
num_to_ascii = ['p', 'n', 'b', 'r', 'k', 'q']
ascii_to_num = {
    'P': 0,
    'N': 1,
    'B': 2,
    'R': 3,
    'K': 4,
    'Q': 5,
    'p': 0,
    'n': 1,
    'b': 2,
    'r': 3,
    'k': 4,
    'q': 5
}


class Board:
    def __init__(self):
        # board  states
        self.bitboards = [
            [71776119061217280, 2594073385365405696, 4755801206503243776, 9295429630892703744, 1152921504606846976,
             576460752303423488], [65280, 36, 66, 129, 16, 8]]
        self.occupancy = [0, 0, 0]
        self.side = 0
        self.enpassant = 0
        self.castle = 0
        self.piece_hash = 0
        self.board_hash = 0
        self.enpassant_states = []
        self.castle_states = []
        self.board_hash_states = []
        self.unmake_stack = []
        # search tables
        self.nodes = 0
        self.ply = 0
        self.killer_moves = [[0 for ply in range(MAX_PLY)] for idx in range(2)]
        self.history_moves = [[0 for target_sq in range(64)] for piece in range(6)]
        self.pv_length = [0 for ply in range(MAX_PLY)]
        self.pv_table = [[0 for ply in range(MAX_PLY)] for ply in range(MAX_PLY)]
        # flags
        self.follow_pv = False
        self.stopped = False
        # transposition table
        self.transposition_table = dict()

    def print_board(self):
        for rank in range(8):
            print(8 - rank, end=' ')
            for file in range(8):
                sq = rank * 8 + file
                piece = -1
                side = -1
                for new_side, bbs in enumerate(self.bitboards):
                    for p, bb in enumerate(bbs):
                        if bb & 1 << sq:
                            piece = p
                            side = new_side
                            break
                print(ascii_pieces[side][piece], end=' ')
            print()
        print('  a b c d e f g h')
        print('    Side: {}'.format('black' if self.side else 'white'))
        print('    Enpass: {}'.format(
            sq_to_coord[self.enpassant] if self.enpassant else None))
        print('    Castle: {}{}{}{}'.format('K' if self.castle & wk else '-',
                                            'Q' if self.castle & wq else '-',
                                            'k' if self.castle & bk else '-',
                                            'q' if self.castle & bq else '-'
                                            ))

    def print_moves(self, moves):
        print('move     piece     capture     double     enpass     castle')
        for m in moves:
            source, target, piece, promote, capture, double, enpass, castle = m
            move = ''.join(
                (sq_to_coord[source], sq_to_coord[target], ascii_pieces[self.side][promote] if promote else ''))
            piece = ascii_pieces[self.side][piece]
            print('{0:<9}{1:5}     {2:<7}     {3:<6}     {4:<6}     {5:<5}'.format(move, piece, capture, double, enpass,
                                                                                   castle))
        print('                    Total moves: {}                       '.format(len(moves)))

    def reset_board(self):
        self.bitboards = [
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0]
        ]
        self.occupancy = [0, 0, 0]
        self.side = 0
        self.enpassant = 0
        self.castle = 0
        self.enpassant_states = []
        self.castle_states = []
        self.moves = []
        self.unmake_stack = []

    def reset_var(self):
        self.nodes = 0
        self.ply = 0
        self.killer_moves = [[0 for ply in range(MAX_PLY)] for idx in range(2)]
        self.history_moves = [[0 for target_sq in range(64)] for piece in range(6)]
        self.pv_length = [0 for ply in range(MAX_PLY)]
        self.pv_table = [[0 for ply in range(MAX_PLY)] for ply in range(MAX_PLY)]

    def parse_fen(self, fen):
        self.reset_board()
        self.reset_var()
        position, side, castle, enpassant, whitehalfmoves, blackhalfmoves = fen.split()
        square = 0
        for char in position:
            if char in 'PNBRKQ':
                self.bitboards[0][ascii_to_num[char]] |= 1 << square
                square += 1
            elif char in 'pnbrkq':
                self.bitboards[1][ascii_to_num[char]] |= 1 << square
                square += 1
            elif char in '12345678':
                square += int(char)
        if castle != '-':
            for char in castle:
                if char == 'K':
                    self.castle |= wk
                elif char == 'Q':
                    self.castle |= wq
                elif char == 'k':
                    self.castle |= bk
                else:
                    self.castle |= bq
        if enpassant != '-':
            file = ord(enpassant[0]) - 97
            rank = 8 - int(enpassant[1])
            self.enpassant = rank * 8 + file
        if side == 'b':
            self.side = 1
        for piece in P, N, B, R, K, Q:
            self.occupancy[WHITE] |= self.bitboards[WHITE][piece]
            self.occupancy[BLACK] |= self.bitboards[BLACK][piece]
        self.occupancy[BOTH] = self.occupancy[WHITE] | self.occupancy[BLACK]
        self.castle_states.append(self.castle)
        self.enpassant_states.append(self.enpassant)
        self.piece_hash = self.generate_hash_key(pieces_only=True)
        self.board_hash = self.generate_hash_key()
        self.board_hash_states.append(self.board_hash)

    def get_fen(self):
        position = ''
        for rank in range(8):
            for file in range(8):
                sq = 8 * rank + file
                side, piece = -1, -1
                for new_side, bbs in enumerate(self.bitboards):
                    for new_piece, bb in enumerate(bbs):
                        if bb & 1 << sq:
                            side = new_side
                            piece = new_piece
                            break
                position += ascii_pieces[side][piece]
            position += '/'

        position = re.sub('\.+', lambda match: str(len(match.group())), position)[:-1]
        if self.castle == 0:
            castle = '-'
        else:
            castle = ''
            if self.castle & wk:
                castle += 'K'
            if self.castle & wq:
                castle += 'Q'
            if self.castle & bk:
                castle += 'k'
            if self.castle & bq:
                castle += 'q'
        enpassant = sq_to_coord[self.enpassant] if self.enpassant else '-'
        side = 'w' if self.side == WHITE else 'b'
        halfmoves = '0 1'
        fen = ' '.join([position, side, castle, enpassant, halfmoves])
        return fen

    def is_square_attacked(self, square):
        pawn_bb, knight_bb, bishop_bb, rook_bb, king_bb, queen_bb = self.bitboards[not self.side]
        if get_pawn_attacks(self.side, square) & pawn_bb:
            return 1
        elif get_knight_attacks(square) & knight_bb:
            return 1
        elif get_bishop_attacks(square, self.occupancy[BOTH]) & bishop_bb:
            return 1
        elif get_rook_attacks(square, self.occupancy[BOTH]) & rook_bb:
            return 1
        elif get_king_attacks(square) & king_bb:
            return 1
        elif get_queen_attacks(square, self.occupancy[BOTH]) & queen_bb:
            return 1
        return 0

    def get_non_attacked_bb(self, bb, attacking_side):
        attacks = 0
        pawn_bb, knight_bb, bishop_bb, rook_bb, king_bb, queen_bb = self.bitboards[attacking_side]
        for sq in get_set_bits_idx(pawn_bb):
            attacks |= get_pawn_attacks(attacking_side, sq)
        for sq in get_set_bits_idx(knight_bb):
            attacks |= get_knight_attacks(sq)
        for sq in get_set_bits_idx(bishop_bb | queen_bb):
            attacks |= get_bishop_attacks(sq, self.occupancy[BOTH])
        for sq in get_set_bits_idx(rook_bb | queen_bb):
            attacks |= get_bishop_attacks(sq, self.occupancy[BOTH])
        for sq in get_set_bits_idx(king_bb):
            attacks |= get_king_attacks(sq)
        return bb & (bb ^ attacks)

    def get_moves(self, separate_captures=True):
        captures = []
        quiet_moves = []
        moves = []
        # get variables for the side to move
        pawn_bb, knight_bb, bishop_bb, rook_bb, king_bb, queen_bb = self.bitboards[self.side]
        opp_pawn_bb, opp_knight_bb, opp_bishop_bb, opp_rook_bb, opp_king_bb, opp_queen_bb = self.bitboards[
            not self.side]
        opp_rookqueen_bb, opp_bishopqueen_bb = opp_rook_bb | opp_queen_bb, opp_bishop_bb | opp_queen_bb
        occupancy, opp_occupancy, both_occupancy = self.occupancy[self.side], self.occupancy[not self.side], \
                                                   self.occupancy[BOTH]

        # GENERATE CHECKMASK
        king_sq = get_lsb_index(king_bb)
        pawn_checkmask = get_pawn_attacks(self.side, king_sq) & opp_pawn_bb
        knight_checkmask = get_knight_attacks(king_sq) & opp_knight_bb
        opp_bishopqueen_attacks = get_bishop_attacks(king_sq, both_occupancy)
        bishopqueen_checker = opp_bishopqueen_attacks & opp_bishopqueen_bb
        bishopqueen_checkmask = RECT_LOOKUP[get_lsb_index(bishopqueen_checker)][king_sq] if bishopqueen_checker else 0
        opp_rookqueen_attacks = get_rook_attacks(king_sq, both_occupancy)
        rookqueen_checker = opp_rookqueen_attacks & opp_rookqueen_bb
        rookqueen_checkmask = RECT_LOOKUP[get_lsb_index(rookqueen_checker)][king_sq] if rookqueen_checker else 0
        check_count = count_bits(pawn_checkmask | knight_checkmask | bishopqueen_checker | rookqueen_checker)

        # no check
        if check_count == 0:
            checkmask = 0xFFFFFFFFFFFFFFFF

        # single check
        elif check_count == 1:
            checkmask = pawn_checkmask | knight_checkmask | bishopqueen_checkmask | rookqueen_checkmask

        # double check
        else:
            self.occupancy[BOTH] ^= king_bb
            # captures
            attacks = get_king_attacks(king_sq)
            for target_sq in get_set_bits_idx(attacks & opp_occupancy):
                if not self.is_square_attacked(target_sq):
                    captures.append((king_sq, target_sq, K, 0, self.get_captured_piece(target_sq), 0, 0, 0))
            # quiet moves
            for target_sq in get_set_bits_idx(attacks & flip_bit(both_occupancy)):
                if not self.is_square_attacked(target_sq):
                    quiet_moves.append((king_sq, target_sq, K, 0, -1, 0, 0, 0))
            self.occupancy[BOTH] ^= king_bb
            if separate_captures:
                return captures, quiet_moves
            else:
                return captures + quiet_moves

        # GENERATE PINMASK
        orthogonal_pinmask = 0
        orthogonal_blockers = opp_rookqueen_attacks & occupancy
        orthogonal_pinners = (get_rook_attacks(king_sq,
                                               both_occupancy ^ orthogonal_blockers) ^ opp_rookqueen_attacks) & opp_rookqueen_bb
        for pinner in get_set_bits_idx(orthogonal_pinners):
            pinmask = RECT_LOOKUP[pinner][king_sq]
            orthogonal_pinmask |= pinmask
        diagonal_pinmask = 0
        diagonal_blockers = opp_bishopqueen_attacks & occupancy
        diagonal_pinners = (get_bishop_attacks(king_sq,
                                               both_occupancy ^ diagonal_blockers) ^ opp_bishopqueen_attacks) & opp_bishopqueen_bb
        for pinner in get_set_bits_idx(diagonal_pinners):
            pinmask = RECT_LOOKUP[pinner][king_sq]
            diagonal_pinmask |= pinmask

        king_rank, king_file = divmod(king_sq, 8)
        pinmask = diagonal_pinmask | orthogonal_pinmask
        nesw_pinmask = NESW[king_rank + king_file] & diagonal_pinmask
        nwse_pinmask = diagonal_pinmask ^ nesw_pinmask
        horizontal_pinmask = RANKS[king_rank] & orthogonal_pinmask
        vertical_pinmask = orthogonal_pinmask ^ horizontal_pinmask

        # experirment  with more efficient silent pawn move generator

        # Criteria for pawn pushes
        # 1. Not diagonally pinned
        # 2. Not horizontally pinned (can be vertically pinned)
        # 3. No pieces blocking
        # 4. Target square in checkmask

        if self.side == WHITE:
            # Pawns can only be pushed if they're unpinned or vertically pinned
            single_push_pawn_bb = pawn_bb & flip_bit(diagonal_pinmask | horizontal_pinmask)
            # Target squares must be empty and within the confines of the checkmask
            single_push_target_bb = single_push_pawn_bb >> 8 & flip_bit(both_occupancy) & checkmask
            # single pawn pushes without promotion
            for target_sq in get_set_bits_idx(single_push_target_bb & not_8_rank):
                quiet_moves.append((target_sq + 8, target_sq, P, 0, -1, 0, 0, 0))
            # single pawn pushes with promotion
            for target_sq in get_set_bits_idx(single_push_target_bb & rank_8):
                quiet_moves.append((target_sq + 8, target_sq, P, Q, -1, 0, 0, 0))
                quiet_moves.append((target_sq + 8, target_sq, P, R, -1, 0, 0, 0))
                quiet_moves.append((target_sq + 8, target_sq, P, B, -1, 0, 0, 0))
                quiet_moves.append((target_sq + 8, target_sq, P, N, -1, 0, 0, 0))

            double_push_pawn_bb = single_push_pawn_bb & rank_2
            double_push_target_bb = (double_push_pawn_bb >> 8 & flip_bit(both_occupancy)) >> 8 & flip_bit(
                both_occupancy) & checkmask
            # double pawn pushes
            for target_sq in get_set_bits_idx(double_push_target_bb):
                quiet_moves.append((target_sq + 16, target_sq, P, 0, -1, 1, 0, 0))
            right_capture_pawn_bb = pawn_bb & not_h_file & flip_bit(orthogonal_pinmask | nwse_pinmask)
            right_capture_target_bb = right_capture_pawn_bb >> 7 & opp_occupancy & checkmask

            # Criteria for pawn captures:

            # captures to the right without promotion
            for target_sq in get_set_bits_idx(right_capture_target_bb & not_8_rank):
                captures.append((target_sq + 7, target_sq, P, 0, self.get_captured_piece(target_sq), 0, 0, 0))
            # captures to the right with promotion
            for target_sq in get_set_bits_idx(right_capture_target_bb & rank_8):
                captured_piece = self.get_captured_piece(target_sq)
                captures.append((target_sq + 7, target_sq, P, Q, captured_piece, 0, 0, 0))
                captures.append((target_sq + 7, target_sq, P, N, captured_piece, 0, 0, 0))
                captures.append((target_sq + 7, target_sq, P, B, captured_piece, 0, 0, 0))
                captures.append((target_sq + 7, target_sq, P, R, captured_piece, 0, 0, 0))
            left_capture_pawn_bb = pawn_bb & not_a_file & flip_bit(orthogonal_pinmask | nesw_pinmask)
            left_capture_target_bb = left_capture_pawn_bb >> 9 & opp_occupancy & checkmask
            # captures to the left without promotion
            for target_sq in get_set_bits_idx(left_capture_target_bb & not_8_rank):
                captures.append((target_sq + 9, target_sq, P, 0, self.get_captured_piece(target_sq), 0, 0, 0))
            # captures to the left with promotion
            for target_sq in get_set_bits_idx(left_capture_target_bb & rank_8):
                captured_piece = self.get_captured_piece(target_sq)
                captures.append((target_sq + 9, target_sq, P, Q, captured_piece, 0, 0, 0))
                captures.append((target_sq + 9, target_sq, P, N, captured_piece, 0, 0, 0))
                captures.append((target_sq + 9, target_sq, P, B, captured_piece, 0, 0, 0))
                captures.append((target_sq + 9, target_sq, P, R, captured_piece, 0, 0, 0))
            # Criteria for enpassant:
            # 1. Captured pawn in checkmask
            # 2. Own pawn not orthogonally pinned
            # 3. If diagonally pinned, own pawn can only en passant in direction of pin
            # 4. If king and opposing rook or queen are on same rank as enpassant pawns, removing both pawns musn't result in check.

            if self.enpassant:
                enpassant_source_bb = get_pawn_attacks(not self.side, self.enpassant) & pawn_bb & flip_bit(
                    orthogonal_pinmask)
                for source_sq in get_set_bits_idx(enpassant_source_bb):
                    if (1 << source_sq) & diagonal_pinmask and not 1 << self.enpassant & diagonal_pinmask:
                        continue
                    if king_bb & rank_5 and opp_rookqueen_bb & rank_5:
                        new_both_occupancy = both_occupancy ^ ((1 << source_sq) | (1 << self.enpassant + 8))
                        if get_rook_attacks(king_sq, new_both_occupancy) & opp_rookqueen_bb:
                            continue
                    captures.append((source_sq, self.enpassant, P, 0, P, 0, 1, 0))

            # CASTLING
            # kingside castle
            if self.castle & wk:
                # squares between king's rook and king are unoccupied
                if not both_occupancy & 6917529027641081856:
                    # f and g squares between king's rook and king are not under attack
                    if not self.is_square_attacked(f1) and not self.is_square_attacked(
                            g1) and not self.is_square_attacked(
                            king_sq):
                        quiet_moves.append((e1, g1, K, 0, -1, 0, 0, 1))
            # queenside castle
            if self.castle & wq:
                # squares between queen's rook and king are unoccupied
                if not both_occupancy & 1008806316530991104:
                    # squares between queen's rook and king are not under attack
                    if not self.is_square_attacked(c1) and not self.is_square_attacked(
                            d1) and not self.is_square_attacked(
                            king_sq):
                        quiet_moves.append((e1, c1, K, 0, -1, 0, 0, 1))

        # self.side == BLACK
        else:
            single_push_pawn_bb = pawn_bb & flip_bit(diagonal_pinmask | horizontal_pinmask)
            # Target squares must be empty and within the confines of the checkmask
            single_push_target_bb = single_push_pawn_bb << 8 & flip_bit(both_occupancy) & checkmask
            # single pawn pushes without promotion
            for target_sq in get_set_bits_idx(single_push_target_bb & not_1_rank):
                quiet_moves.append((target_sq - 8, target_sq, P, 0, -1, 0, 0, 0))
            # single pawn pushes with promotion
            for target_sq in get_set_bits_idx(single_push_target_bb & rank_1):
                quiet_moves.append((target_sq - 8, target_sq, P, Q, -1, 0, 0, 0))
                quiet_moves.append((target_sq - 8, target_sq, P, R, -1, 0, 0, 0))
                quiet_moves.append((target_sq - 8, target_sq, P, B, -1, 0, 0, 0))
                quiet_moves.append((target_sq - 8, target_sq, P, N, -1, 0, 0, 0))

            double_push_pawn_bb = single_push_pawn_bb & rank_7
            double_push_target_bb = (double_push_pawn_bb << 8 & flip_bit(both_occupancy)) << 8 & flip_bit(
                both_occupancy) & checkmask
            # double pawn pushes
            for target_sq in get_set_bits_idx(double_push_target_bb):
                quiet_moves.append((target_sq - 16, target_sq, P, 0, -1, 1, 0, 0))
            right_capture_pawn_bb = pawn_bb & not_a_file & flip_bit(orthogonal_pinmask | nwse_pinmask)
            right_capture_target_bb = right_capture_pawn_bb << 7 & opp_occupancy & checkmask
            # captures to the right without promotion
            for target_sq in get_set_bits_idx(right_capture_target_bb & not_1_rank):
                captures.append((target_sq - 7, target_sq, P, 0, self.get_captured_piece(target_sq), 0, 0, 0))
            # captures  to the right with promotion
            for target_sq in get_set_bits_idx(right_capture_target_bb & rank_1):
                captured_piece = self.get_captured_piece(target_sq)
                captures.append((target_sq - 7, target_sq, P, Q, captured_piece, 0, 0, 0))
                captures.append((target_sq - 7, target_sq, P, N, captured_piece, 0, 0, 0))
                captures.append((target_sq - 7, target_sq, P, B, captured_piece, 0, 0, 0))
                captures.append((target_sq - 7, target_sq, P, R, captured_piece, 0, 0, 0))
            left_capture_pawn_bb = pawn_bb & not_h_file & flip_bit(orthogonal_pinmask | nesw_pinmask)
            left_capture_target_bb = left_capture_pawn_bb << 9 & opp_occupancy & checkmask
            # captures to the left without promotion
            for target_sq in get_set_bits_idx(left_capture_target_bb & not_1_rank):
                captures.append((target_sq - 9, target_sq, P, 0, self.get_captured_piece(target_sq), 0, 0, 0))
            # captures to the left with promotion
            for target_sq in get_set_bits_idx(left_capture_target_bb & rank_1):
                captured_piece = self.get_captured_piece(target_sq)
                captures.append((target_sq - 9, target_sq, P, Q, captured_piece, 0, 0, 0))
                captures.append((target_sq - 9, target_sq, P, N, captured_piece, 0, 0, 0))
                captures.append((target_sq - 9, target_sq, P, B, captured_piece, 0, 0, 0))
                captures.append((target_sq - 9, target_sq, P, R, captured_piece, 0, 0, 0))

            # ENPASSANT
            if self.enpassant:
                enpassant_source_bb = get_pawn_attacks(not self.side, self.enpassant) & pawn_bb & flip_bit(
                    orthogonal_pinmask)
                for source_sq in get_set_bits_idx(enpassant_source_bb):
                    if (1 << source_sq) & diagonal_pinmask and not 1 << self.enpassant & diagonal_pinmask:
                        continue
                    if king_bb & rank_4 and opp_rookqueen_bb & rank_4:
                        new_both_occupancy = both_occupancy ^ ((1 << source_sq) | (1 << (self.enpassant - 8)))
                        if get_rook_attacks(king_sq, new_both_occupancy) & opp_rookqueen_bb:
                            continue
                    captures.append((source_sq, self.enpassant, P, 0, P, 0, 1, 0))

            # CASTLING
            # kingside castle
            if self.castle & bk:
                # squares between king's rook and king are unoccupied
                if not both_occupancy & 96:
                    # f and g squares between king's rook and king are not under attack
                    if not self.is_square_attacked(f8) and not self.is_square_attacked(
                            g8) and not self.is_square_attacked(
                            king_sq):
                        quiet_moves.append((e8, g8, K, 0, -1, 0, 0, 1))
            # queenside castle
            if self.castle & bq:
                # squares between queen's rook and king are unoccupied
                if not both_occupancy & 14:
                    # squares between queen's rook and king are not under attack
                    if not self.is_square_attacked(c8) and not self.is_square_attacked(
                            d8) and not self.is_square_attacked(
                            king_sq):
                        quiet_moves.append((e8, c8, K, 0, -1, 0, 0, 1))

        # PIECE MOVES

        # KNIGHT MOVES
        for source_sq in get_set_bits_idx(knight_bb & flip_bit(pinmask)):
            attacks = get_knight_attacks(source_sq) & checkmask
            # captures
            for target_sq in get_set_bits_idx(attacks & opp_occupancy):
                captures.append((source_sq, target_sq, N, 0, self.get_captured_piece(target_sq), 0, 0, 0))
            # quiet moves
            for target_sq in get_set_bits_idx(attacks & flip_bit(both_occupancy)):
                quiet_moves.append((source_sq, target_sq, N, 0, -1, 0, 0, 0))

        # BISHOP MOVES
        for source_sq in get_set_bits_idx(bishop_bb & flip_bit(orthogonal_pinmask)):
            attacks = get_bishop_attacks(source_sq, both_occupancy) & checkmask
            if 1 << source_sq & diagonal_pinmask:
                attacks &= diagonal_pinmask
            # captures
            for target_sq in get_set_bits_idx(attacks & opp_occupancy):
                captures.append((source_sq, target_sq, B, 0, self.get_captured_piece(target_sq), 0, 0, 0))
            # quiet  moves
            for target_sq in get_set_bits_idx(attacks & flip_bit(both_occupancy)):
                quiet_moves.append((source_sq, target_sq, B, 0, -1, 0, 0, 0))

        # ROOK MOVES
        for source_sq in get_set_bits_idx(rook_bb & flip_bit(diagonal_pinmask)):
            attacks = get_rook_attacks(source_sq, both_occupancy) & checkmask
            if 1 << source_sq & orthogonal_pinmask:
                attacks &= orthogonal_pinmask
            # captures
            for target_sq in get_set_bits_idx(attacks & opp_occupancy):
                captures.append((source_sq, target_sq, R, 0, self.get_captured_piece(target_sq), 0, 0, 0))
            # quiet moves
            for target_sq in get_set_bits_idx(attacks & flip_bit(both_occupancy)):
                quiet_moves.append((source_sq, target_sq, R, 0, -1, 0, 0, 0))

        # QUEEN MOVES
        for source_sq in get_set_bits_idx(queen_bb):
            attacks = get_queen_attacks(source_sq, both_occupancy) & checkmask
            source_bb = 1 << source_sq
            if source_bb & pinmask:
                if source_bb & horizontal_pinmask:
                    attacks &= horizontal_pinmask
                elif source_bb & vertical_pinmask:
                    attacks &= vertical_pinmask
                elif source_bb & nesw_pinmask:
                    attacks &= nesw_pinmask
                else:
                    attacks &= nwse_pinmask
            # captures
            for target_sq in get_set_bits_idx(attacks & opp_occupancy):
                captures.append((source_sq, target_sq, Q, 0, self.get_captured_piece(target_sq), 0, 0, 0))
            # quiet moves
            for target_sq in get_set_bits_idx(attacks & flip_bit(both_occupancy)):
                quiet_moves.append((source_sq, target_sq, Q, 0, -1, 0, 0, 0))

        # KING MOVES
        self.occupancy[BOTH] ^= king_bb
        # captures
        attacks = get_king_attacks(king_sq)
        for target_sq in get_set_bits_idx(attacks & opp_occupancy):
            if not self.is_square_attacked(target_sq):
                captures.append((king_sq, target_sq, K, 0, self.get_captured_piece(target_sq), 0, 0, 0))
        # quiet moves
        for target_sq in get_set_bits_idx(attacks & flip_bit(both_occupancy)):
            if not self.is_square_attacked(target_sq):
                quiet_moves.append((king_sq, target_sq, K, 0, -1, 0, 0, 0))
        self.occupancy[BOTH] ^= king_bb
        if separate_captures:
            return captures, quiet_moves
        else:
            return captures + quiet_moves

    def get_captured_piece(self, sq):
        for piece, bb in enumerate(self.bitboards[not self.side]):
            if bb & 1 << sq:
                return piece

    def get_captures(self):
        moves = []
        # get variables for the side to move
        pawn_bb, knight_bb, bishop_bb, rook_bb, king_bb, queen_bb = self.bitboards[self.side]
        opp_pawn_bb, opp_knight_bb, opp_bishop_bb, opp_rook_bb, opp_king_bb, opp_queen_bb = self.bitboards[
            not self.side]
        opp_rookqueen_bb, opp_bishopqueen_bb = opp_rook_bb | opp_queen_bb, opp_bishop_bb | opp_queen_bb
        occupancy, opp_occupancy, both_occupancy = self.occupancy[self.side], self.occupancy[not self.side], \
                                                   self.occupancy[
                                                       BOTH]

        # GENERATE CHECKMASK
        king_sq = get_lsb_index(king_bb)
        pawn_checkmask = get_pawn_attacks(self.side, king_sq) & opp_pawn_bb
        knight_checkmask = get_knight_attacks(king_sq) & opp_knight_bb
        opp_bishopqueen_attacks = get_bishop_attacks(king_sq, both_occupancy)
        bishopqueen_checkmask = opp_bishopqueen_attacks & opp_bishopqueen_bb
        opp_rookqueen_attacks = get_rook_attacks(king_sq, both_occupancy)
        rookqueen_checkmask = opp_rookqueen_attacks & opp_rookqueen_bb
        checkmask = pawn_checkmask | knight_checkmask | bishopqueen_checkmask | rookqueen_checkmask
        check_count = count_bits(checkmask)

        # no check
        if check_count == 0:
            checkmask = 0xFFFFFFFFFFFFFFFF

        # double check
        elif check_count == 2:
            self.occupancy[BOTH] ^= king_bb
            # captures
            attacks = get_king_attacks(king_sq)
            for target_sq in get_set_bits_idx(attacks & opp_occupancy):
                if not self.is_square_attacked(target_sq):
                    moves.append((king_sq, target_sq, K, 0, self.get_captured_piece(target_sq), 0, 0, 0))
            self.occupancy[BOTH] ^= king_bb
            return moves

        # GENERATE PINMASK
        orthogonal_pinmask = 0
        orthogonal_blockers = opp_rookqueen_attacks & occupancy
        orthogonal_pinners = (get_rook_attacks(king_sq,
                                               both_occupancy ^ orthogonal_blockers) ^ opp_rookqueen_attacks) & opp_rookqueen_bb
        for pinner in get_set_bits_idx(orthogonal_pinners):
            pinmask = RECT_LOOKUP[pinner][king_sq]
            orthogonal_pinmask |= pinmask
        diagonal_pinmask = 0
        diagonal_blockers = opp_bishopqueen_attacks & occupancy
        diagonal_pinners = (get_bishop_attacks(king_sq,
                                               both_occupancy ^ diagonal_blockers) ^ opp_bishopqueen_attacks) & opp_bishopqueen_bb
        for pinner in get_set_bits_idx(diagonal_pinners):
            pinmask = RECT_LOOKUP[pinner][king_sq]
            diagonal_pinmask |= pinmask

        king_rank, king_file = divmod(king_sq, 8)
        pinmask = diagonal_pinmask | orthogonal_pinmask
        nesw_pinmask = NESW[king_rank + king_file] & diagonal_pinmask
        nwse_pinmask = diagonal_pinmask ^ nesw_pinmask
        horizontal_pinmask = RANKS[king_rank] & orthogonal_pinmask
        vertical_pinmask = orthogonal_pinmask ^ horizontal_pinmask

        # experirment  with more efficient silent pawn move generator

        # Criteria for pawn pushes
        # 1. Not diagonally pinned
        # 2. Not horizontally pinned (can be vertically pinned)
        # 3. No pieces blocking
        # 4. Target square in checkmask

        if self.side == WHITE:
            right_capture_pawn_bb = pawn_bb & not_h_file & flip_bit(orthogonal_pinmask | nwse_pinmask)
            right_capture_target_bb = right_capture_pawn_bb >> 7 & opp_occupancy & checkmask
            # captures to the right without promotion
            for target_sq in get_set_bits_idx(right_capture_target_bb & not_8_rank):
                moves.append((target_sq + 7, target_sq, P, 0, self.get_captured_piece(target_sq), 0, 0, 0))
            # captures to the right with promotion
            for target_sq in get_set_bits_idx(right_capture_target_bb & rank_8):
                captured_piece = self.get_captured_piece(target_sq)
                moves.append((target_sq + 7, target_sq, P, Q, captured_piece, 0, 0, 0))
                moves.append((target_sq + 7, target_sq, P, N, captured_piece, 0, 0, 0))
                moves.append((target_sq + 7, target_sq, P, B, captured_piece, 0, 0, 0))
                moves.append((target_sq + 7, target_sq, P, R, captured_piece, 0, 0, 0))
            left_capture_pawn_bb = pawn_bb & not_a_file & flip_bit(orthogonal_pinmask | nesw_pinmask)
            left_capture_target_bb = left_capture_pawn_bb >> 9 & opp_occupancy & checkmask
            # captures to the left without promotion
            for target_sq in get_set_bits_idx(left_capture_target_bb & not_8_rank):
                moves.append((target_sq + 9, target_sq, P, 0, self.get_captured_piece(target_sq), 0, 0, 0))
            # captures to the left with promotion
            for target_sq in get_set_bits_idx(left_capture_target_bb & rank_8):
                captured_piece = self.get_captured_piece(target_sq)
                moves.append((target_sq + 9, target_sq, P, Q, captured_piece, 0, 0, 0))
                moves.append((target_sq + 9, target_sq, P, N, captured_piece, 0, 0, 0))
                moves.append((target_sq + 9, target_sq, P, B, captured_piece, 0, 0, 0))
                moves.append((target_sq + 9, target_sq, P, R, captured_piece, 0, 0, 0))
            # Criteria for enpassant:
            # 1. Captured pawn in checkmask
            # 2. Own pawn not orthogonally pinned
            # 3. If diagonally pinned, own pawn can only en passant in direction of pin
            # 4. If king and opposing rook or queen are on same rank as enpassant pawns, removing both pawns musn't result in check.

            if self.enpassant:
                enpassant_source_bb = get_pawn_attacks(not self.side, self.enpassant) & pawn_bb & flip_bit(
                    orthogonal_pinmask)
                for source_sq in get_set_bits_idx(enpassant_source_bb):
                    if (1 << source_sq) & diagonal_pinmask and not 1 << self.enpassant & diagonal_pinmask:
                        continue
                    if king_bb & rank_5 and opp_rookqueen_bb & rank_5:
                        new_both_occupancy = both_occupancy ^ ((1 << source_sq) | (1 << self.enpassant + 8))
                        if get_rook_attacks(king_sq, new_both_occupancy) & opp_rookqueen_bb:
                            continue
                    moves.append((source_sq, self.enpassant, P, 0, P, 0, 1, 0))
        # self.side == BLACK
        else:
            right_capture_pawn_bb = pawn_bb & not_a_file & flip_bit(orthogonal_pinmask | nwse_pinmask)
            right_capture_target_bb = right_capture_pawn_bb << 7 & opp_occupancy & checkmask
            # captures to the right without promotion
            for target_sq in get_set_bits_idx(right_capture_target_bb & not_1_rank):
                moves.append((target_sq - 7, target_sq, P, 0, self.get_captured_piece(target_sq), 0, 0, 0))
            # captures  to the right with promotion
            for target_sq in get_set_bits_idx(right_capture_target_bb & rank_1):
                captured_piece = self.get_captured_piece(target_sq)
                moves.append((target_sq - 7, target_sq, P, Q, captured_piece, 0, 0, 0))
                moves.append((target_sq - 7, target_sq, P, N, captured_piece, 0, 0, 0))
                moves.append((target_sq - 7, target_sq, P, B, captured_piece, 0, 0, 0))
                moves.append((target_sq - 7, target_sq, P, R, captured_piece, 0, 0, 0))
            left_capture_pawn_bb = pawn_bb & not_h_file & flip_bit(orthogonal_pinmask | nesw_pinmask)
            left_capture_target_bb = left_capture_pawn_bb << 9 & opp_occupancy & checkmask
            # captures to the left without promotion
            for target_sq in get_set_bits_idx(left_capture_target_bb & not_1_rank):
                moves.append((target_sq - 9, target_sq, P, 0, self.get_captured_piece(target_sq), 0, 0, 0))
            # captures to the left with promotion
            for target_sq in get_set_bits_idx(left_capture_target_bb & rank_1):
                captured_piece = self.get_captured_piece(target_sq)
                moves.append((target_sq - 9, target_sq, P, Q, captured_piece, 0, 0, 0))
                moves.append((target_sq - 9, target_sq, P, N, captured_piece, 0, 0, 0))
                moves.append((target_sq - 9, target_sq, P, B, captured_piece, 0, 0, 0))
                moves.append((target_sq - 9, target_sq, P, R, captured_piece, 0, 0, 0))

            # ENPASSANT
            if self.enpassant:
                enpassant_source_bb = get_pawn_attacks(not self.side, self.enpassant) & pawn_bb & flip_bit(
                    orthogonal_pinmask)
                for source_sq in get_set_bits_idx(enpassant_source_bb):
                    if (1 << source_sq) & diagonal_pinmask and not 1 << self.enpassant & diagonal_pinmask:
                        continue
                    if king_bb & rank_4 and opp_rookqueen_bb & rank_4:
                        new_both_occupancy = both_occupancy ^ ((1 << source_sq) | (1 << (self.enpassant - 8)))
                        if get_rook_attacks(king_sq, new_both_occupancy) & opp_rookqueen_bb:
                            continue
                    moves.append((source_sq, self.enpassant, P, 0, P, 0, 1, 0))
        # KNIGHT CAPTURES
        for source_sq in get_set_bits_idx(knight_bb & flip_bit(pinmask)):
            attacks = get_knight_attacks(source_sq) & checkmask & opp_occupancy
            for target_sq in get_set_bits_idx(attacks):
                moves.append((source_sq, target_sq, N, 0, self.get_captured_piece(target_sq), 0, 0, 0))

        # BISHOP CAPTURES
        for source_sq in get_set_bits_idx(bishop_bb & flip_bit(orthogonal_pinmask)):
            attacks = get_bishop_attacks(source_sq, both_occupancy) & checkmask & opp_occupancy
            if 1 << source_sq & diagonal_pinmask:
                attacks &= diagonal_pinmask
            for target_sq in get_set_bits_idx(attacks):
                moves.append((source_sq, target_sq, B, 0, self.get_captured_piece(target_sq), 0, 0, 0))
        # ROOK CAPTURES
        for source_sq in get_set_bits_idx(rook_bb & flip_bit(diagonal_pinmask)):
            attacks = get_rook_attacks(source_sq, both_occupancy) & checkmask & opp_occupancy
            if 1 << source_sq & orthogonal_pinmask:
                attacks &= orthogonal_pinmask
            for target_sq in get_set_bits_idx(attacks):
                moves.append((source_sq, target_sq, R, 0, self.get_captured_piece(target_sq), 0, 0, 0))

        # QUEEN CAPTURES
        for source_sq in get_set_bits_idx(queen_bb):
            attacks = get_queen_attacks(source_sq, both_occupancy) & checkmask & opp_occupancy
            source_bb = 1 << source_sq
            if source_bb & pinmask:
                if source_bb & horizontal_pinmask:
                    attacks &= horizontal_pinmask
                elif source_bb & vertical_pinmask:
                    attacks &= vertical_pinmask
                elif source_bb & nesw_pinmask:
                    attacks &= nesw_pinmask
                else:
                    attacks &= nwse_pinmask
            for target_sq in get_set_bits_idx(attacks):
                moves.append((source_sq, target_sq, Q, 0, self.get_captured_piece(target_sq), 0, 0, 0))

        # KING CAPTURES
        self.occupancy[BOTH] ^= king_bb
        attacks = get_king_attacks(king_sq) & opp_occupancy
        for target_sq in get_set_bits_idx(attacks):
            if not self.is_square_attacked(target_sq):
                moves.append((king_sq, target_sq, K, 0, self.get_captured_piece(target_sq), 0, 0, 0))
        self.occupancy[BOTH] ^= king_bb
        return moves

    def perft(self, max_depth, print_flag=True):
        self.reset_var()
        start = time.time()
        self.perft_driver(max_depth)
        end = time.time()
        nodes, timing = self.nodes, end - start
        if print_flag:
            print(f'Nodes: {nodes}')
            print(f'Time: {timing}')
        return nodes, timing

    def perft_driver(self, depth):
        if depth == 0:
            self.nodes += 1
            return
        for move in self.get_moves(separate_captures=False):
            self.make_move(move)
            correct_hash = self.generate_hash_key()
            if correct_hash != self.board_hash:
                self.print_board()
                print(f'correct hash {correct_hash} \nwrong hash {self.board_hash}')
                input()
            self.perft_driver(depth - 1)
            self.unmake_move()

    def perft_divide(self, max_depth, print_flag=True):
        perft_divide = {}
        for move in self.get_moves(separate_captures=False):
            self.make_move(move)
            correct_hash = self.generate_hash_key()
            if correct_hash != self.board_hash:
                self.print_board()
                print(f'correct hash {correct_hash} \nwrong hash {self.board_hash}')
                input()
            perft_divide[move] = self.perft(max_depth - 1, print_flag=False)[0]
            self.unmake_move()
        if print_flag:
            total_count = 0
            for move, count in perft_divide.items():
                print(f'{to_uci(move)}: {count}')
                total_count += count
            print(f'Nodes: {total_count}')
        return perft_divide

    def make_move(self, move):
        source_sq, target_sq, piece, promote, capture, double, enpass, castle = move
        source_bb, target_bb = 1 << source_sq, 1 << target_sq
        move_bb = source_bb | target_bb
        bbs, opp_bbs = self.bitboards[self.side], self.bitboards[not self.side]
        pawn_dir = 8 if self.side else -8
        # Store previous board states
        self.enpassant_states.append(self.enpassant)
        self.castle_states.append(self.castle)
        self.board_hash_states.append(self.board_hash)
        # XOR away old enpassant and castling states from zobrist hash
        if self.enpassant:
            self.board_hash ^= ENPASSANT_KEYS[self.enpassant]
        self.board_hash ^= CASTLE_KEYS[self.castle]
        unmake = []
        if promote:
            bbs[P] ^= source_bb
            bbs[promote] ^= target_bb
            self.board_hash ^= PIECE_KEYS[self.side][P][source_sq] ^ PIECE_KEYS[self.side][promote][target_sq]
            unmake.append((self.side, P, source_bb))
            unmake.append((self.side, promote, target_bb))
        else:
            bbs[piece] ^= move_bb
            self.board_hash ^= PIECE_KEYS[self.side][piece][source_sq] ^ PIECE_KEYS[self.side][piece][target_sq]
            unmake.append((self.side, piece, move_bb))
        self.occupancy[self.side] ^= move_bb
        if capture != -1:
            if enpass:
                ep_target_sq = target_sq - pawn_dir
                ep_target_bb = 1 << ep_target_sq
                opp_bbs[P] ^= ep_target_bb
                self.occupancy[not self.side] ^= ep_target_bb
                self.board_hash ^= PIECE_KEYS[not self.side][capture][ep_target_sq]
                unmake.append((not self.side, P, ep_target_bb))
            else:
                opp_bbs[capture] ^= target_bb
                self.occupancy[not self.side] ^= target_bb
                self.board_hash ^= PIECE_KEYS[not self.side][capture][target_sq]
                unmake.append((not self.side, capture, target_bb))
        '''if promote:
            bbs[P] ^= target_bb
            bbs[promote] ^= target_bb
            unmake.append((self.side, P, target_bb))
            unmake.append((self.side, promote, target_bb))
            self.piece_hash ^= PIECE_KEYS[self.side][P][target_sq]
            self.piece_hash ^= PIECE_KEYS[self.side][promote][target_sq]
        if enpass:
            ep_target_bb = (1 << target_sq | 1 << (target_sq - pawn_dir))
            opp_bbs[P] ^= ep_target_bb
            self.occupancy[not self.side] ^= ep_target_bb
            unmake.append((not self.side, P, ep_target_bb))'''
        # En passant square is always empty unless previous move was a double pawn push
        if double:
            self.enpassant = target_sq - pawn_dir
        else:
            self.enpassant = 0
        # In addition to the king bitboard, update rook bitboards when castling
        if castle:
            if self.side == WHITE:
                if target_sq == g1:
                    rook_source_sq, rook_target_sq = h1, f1
                else:
                    rook_source_sq, rook_target_sq = a1, d1
            else:
                if target_sq == g8:
                    rook_source_sq, rook_target_sq = h8, f8
                else:
                    rook_source_sq, rook_target_sq = a8, d8
            rook_move_bb = (1 << rook_source_sq | 1 << rook_target_sq)
            bbs[R] ^= rook_move_bb
            self.occupancy[self.side] ^= rook_move_bb
            self.board_hash ^= PIECE_KEYS[self.side][R][rook_source_sq] ^ PIECE_KEYS[self.side][R][rook_target_sq]
            unmake.append((self.side, R, rook_move_bb))
        # Update castling rights
        self.castle &= CASTLING_RIGHTS[target_sq] & CASTLING_RIGHTS[source_sq]
        self.occupancy[BOTH] = self.occupancy[WHITE] | self.occupancy[BLACK]
        self.unmake_stack.append(unmake)
        self.side = not self.side
        # XOR new enpassant and castle states, as well as side key
        if self.enpassant:
            self.board_hash ^= ENPASSANT_KEYS[self.enpassant]
        self.board_hash ^= CASTLE_KEYS[self.castle] ^ SIDE_KEY


    def unmake_move(self):
        for side, piece, move_bb in self.unmake_stack.pop():
            self.bitboards[side][piece] ^= move_bb
            self.occupancy[side] ^= move_bb
        self.occupancy[BOTH] = self.occupancy[BLACK] | self.occupancy[WHITE]
        self.enpassant = self.enpassant_states.pop()
        self.castle = self.castle_states.pop()
        self.side = not self.side
        self.board_hash = self.board_hash_states.pop()

    def parse_movestr(self, move_str):
        for move in self.get_moves():
            if move_str == to_uci(move):
                return move

    def evaluate(self):
        score = 0
        for piece, bb in enumerate(self.bitboards[WHITE]):
            for sq in get_set_bits_idx(bb):
                score += PIECE_VALUES[piece] + WHITE_PSQ[piece][sq]
        for piece, bb in enumerate(self.bitboards[BLACK]):
            for sq in get_set_bits_idx(bb):
                score -= PIECE_VALUES[piece] + BLACK_PSQ[piece][sq]
        score = score if self.side == WHITE else -score
        return score

    def timeout(self, secs):
        def timeout_driver():
            time.sleep(secs)
            self.stopped = True
        t = threading.Thread(target=timeout_driver)
        t.start()

    def iterative_deepening_search(self, depth, print_flag=True, timeout=None):
        self.reset_var()
        self.stopped = False
        if timeout:
            self.timeout(timeout)
        infos = []
        alpha, beta = -INFINITY, INFINITY
        for current_depth in range(1, depth + 1):
            if self.stopped == True:
                break
            self.follow_pv = True
            info = self.negamax_search(current_depth, alpha, beta, print_flag=print_flag)
            score = info.get('score cp', info.get('score mate'))
            if not alpha < score < beta:
                alpha = -INFINITY
                beta = INFINITY
                continue
            alpha = score - 50
            beta = score + 50
            infos.append(info)
        bestmove = infos[-1]['pv'][:4]
        meta_info = {
            'infos': infos,
            'bestmove': bestmove
        }
        if print_flag == True:
            print('bestmove {}'.format(bestmove))
        return meta_info

    def negamax_search(self, depth, alpha=-INFINITY, beta=INFINITY, print_flag=True):
        # Reset ply, nodes counter
        self.ply, self.nodes = 0, 0
        start_time = time.time()
        score = self.negamax_driver2(alpha, beta, depth)
        end_time = time.time()
        pv = self.pv_table[0][:self.pv_length[0]]
        pv = [to_uci(move) for move in pv]
        if - MATE_UPPERBOUND < score <  - MATE_LOWERBOUND:
             print('mate found')
             score = - (score  +  MATE_UPPERBOUND) // 2 - 1
             score_type = 'score mate'
        elif MATE_LOWERBOUND <  score <  MATE_UPPERBOUND:
            print('mate found')
            score = (MATE_UPPERBOUND - score) // 2 + 1
            score_type = 'score mate'
        else:
            score_type = 'score cp'
        info = {
            score_type: score,
            'depth': depth,
            'nodes': self.nodes,
            'pv': ' '.join(pv),
            'time': end_time - start_time
        }
        if print_flag == True:
            Board.print_info(info)
        return info
    
    @staticmethod
    def print_info(info):
        info_str = 'info '
        for key, val in info.items():
            info_str += f'{key} {val} '
        print(info_str)

    def negamax_driver(self, alpha, beta, depth):
        self.pv_length[self.ply] = self.ply
        if depth == 0:
            return self.q_search(alpha, beta)
        self.nodes += 1
        # Increase search depth if king is in check
        in_check = self.is_square_attacked(get_lsb_index(self.bitboards[self.side][K]))
        if in_check:
            depth += 1
        best_so_far = float('-inf')
        moves = self.get_moves()
        for move in self.native_sort_moves(moves):
            # Searching into deeper ply
            self.ply += 1
            self.make_move(move)
            # Recurse
            value = -self.negamax_driver(-beta, -alpha, depth - 1)
            # Returning to original ply
            self.ply -= 1
            self.unmake_move()
            if value > best_so_far:
                best_so_far = value
            # cutnode
            if best_so_far > beta:
                if move[4] == -1:  # move is not a capture
                    self.killer_moves[1][self.ply] = self.killer_moves[0][self.ply]
                    self.killer_moves[0][self.ply] = move
                return best_so_far
            # pv node
            if best_so_far > alpha:
                if move[4] == -1:  # move is not a capture
                    self.history_moves[move[2]][move[1]] += depth
                next_ply = self.ply + 1
                last_ply = self.pv_length[next_ply]
                self.pv_table[self.ply][self.ply] = move
                self.pv_table[self.ply][next_ply: last_ply] = self.pv_table[next_ply][next_ply: last_ply]
                self.pv_length[self.ply] = self.pv_length[next_ply]
                # update alpha
                alpha = best_so_far
        if len(moves) == 0:
            if in_check:
                return -49000 + self.ply
            else:
                return 0
        return best_so_far

    def q_search(self, alpha, beta):
        self.nodes += 1
        eval = self.evaluate()
        if eval > beta:
            return eval
        best_so_far = eval
        for move in self.native_sort_moves(self.get_captures()):
            self.ply += 1
            self.make_move(move)
            value = -self.q_search(-beta, -alpha)
            self.ply -= 1
            self.unmake_move()
            if value > best_so_far:
                best_so_far = value
            if best_so_far > beta:
                return best_so_far
            alpha = max(alpha, best_so_far)
        return best_so_far

    def negamax_driver2(self, alpha, beta, depth):
        hash_flag = ALPHA_FLAG
        is_pv_node = (beta - alpha) > 1
        if self.ply >  0 and is_pv_node ==  False:
            hash_value = self.read_hash_entry(alpha, beta, depth)
            if hash_value != None:
                if hash_value <  - MATE_LOWERBOUND:
                    print('mate found')
                elif MATE_LOWERBOUND <  hash_value:
                    print('mate found')
                return hash_value
        self.pv_length[self.ply] = self.ply
        if depth == 0:
            return self.q_search2(alpha, beta)
        self.nodes += 1
        # Increase search depth if king is in check
        in_check = self.is_square_attacked(get_lsb_index(self.bitboards[self.side][K]))
        if in_check:
            depth += 1
        # Criteria for Null Move Pruning
        if depth >= 3 and in_check == False and self.ply > 0:
            # Increment ply
            self.ply += 1
            # Switch sides
            self.side = not self.side
            self.board_hash ^= SIDE_KEY
            # Disable enpassant
            if self.enpassant:
                self.board_hash ^= ENPASSANT_KEYS[self.enpassant]
            prev_enpassant = self.enpassant
            self.enpassant = 0
            value = - self.negamax_driver2(-beta, -beta + 1, depth - 1 - 2)
            #Decrement ply
            self.ply -= 1
            # Restore side
            self.side = not self.side
            self.board_hash ^= SIDE_KEY
            # Restore enpassant
            self.enpassant = prev_enpassant
            if self.enpassant:
                self.board_hash ^= ENPASSANT_KEYS[self.enpassant]
            if self.stopped == True:
                return 0
            if value >= beta:
                return beta
        move_count = 0
        moves = self.get_moves()
        for move in self.sort_moves(*moves):
            target_sq, piece, promote, capture = move[1:5]
            # Searching into deeper ply
            self.ply += 1
            self.make_move(move)
            # First move must be searched at full depth
            if move_count == 0:
                value = -self.negamax_driver2(-beta, -alpha, depth - 1)
            else:
                # Criteria for late move reduction
                if move_count >= FULL_DEPTH_MOVES and depth >= REDUCTION_LIMIT and in_check == False and capture == -1 and promote == 0:
                    value = - self.negamax_driver2(-alpha - 1, -alpha, depth - 2)
                else:
                    value = alpha + 1
                # Principal variation search
                if value > alpha:
                    value = - self.negamax_driver2(-alpha - 1, -alpha, depth - 1)
                    if alpha < value < beta:
                        value = - self.negamax_driver2(-beta, -alpha, depth - 1)
            # Returning to original ply
            self.ply -= 1
            self.unmake_move()
            move_count += 1
            if self.stopped == True:
                return 0
            # pv node
            if value > alpha:
                if capture == -1:  # move is not a capture
                    self.history_moves[piece][target_sq] += depth
                # update alpha
                alpha = value
                hash_flag = EXACT_FLAG
                # update pv_table
                next_ply = self.ply + 1
                last_ply = self.pv_length[next_ply]
                self.pv_table[self.ply][self.ply] = move
                self.pv_table[self.ply][next_ply: last_ply] = self.pv_table[next_ply][next_ply: last_ply]
                self.pv_length[self.ply] = self.pv_length[next_ply]
                #cutnode
                if value >= beta:
                # Add move to list of killer moves if not a capture
                    if capture == -1:
                        self.killer_moves[1][self.ply] = self.killer_moves[0][self.ply]
                        self.killer_moves[0][self.ply] = move
                    self.write_hash_entry(beta, depth, BETA_FLAG)
                    return beta
        if len(moves) == 0:
            # checkmate
            if in_check:
                return -MATE_UPPERBOUND + self.ply
            # stalemate
            else:
                return 0
        self.write_hash_entry(alpha, depth, hash_flag)
        return alpha

    def q_search2(self, alpha, beta):
        self.nodes += 1
        eval = self.evaluate()
        if eval >= beta:
            return beta
        if eval > alpha:
            alpha = eval
        for move in self.sort_moves(self.get_captures()):
            self.ply += 1
            self.make_move(move)
            value = -self.q_search2(-beta, -alpha)
            self.ply -= 1
            self.unmake_move()
            if self.stopped == True:
                return 0
            if value > alpha:
                alpha = value
                if value >= beta:
                    return beta
        return alpha

    def score_move(self, move):
        _, target_sq, piece, _, captured_piece = move[:5]
        if captured_piece != -1:
            return MVV_LVA[piece][captured_piece] + 10000
        elif self.killer_moves[0][self.ply] == move:
            return 9000
        elif self.killer_moves[1][self.ply] == move:
            return 8000
        else:
            return self.history_moves[piece][target_sq]

    def heapq_sort_moves(self, moves):
        sorted_moves = [(-self.score_move(move), move) for move in moves]
        heapq.heapify(sorted_moves)
        for i in range(len(moves)):
            yield sorted_moves.heappop()[1]

    def native_sort_moves(self, moves):
        return sorted(moves, key=self.score_move, reverse=True)

    @staticmethod
    def score_capture(capture):
        piece, captured_piece = capture[2], capture[4]
        if piece == None or captured_piece == None:
            print(capture)
        return MVV_LVA[piece][captured_piece]

    def score_quiet_move(self, quiet_move):
        piece, target_sq = quiet_move[2], quiet_move[1]
        return self.history_moves[piece][target_sq]

    def sort_moves(self, captures, quiet_moves=[]):
        # Move Ordering:
        # 1. PV node
        # 2. Captures sorted by MVV LVA
        # 3. Non-capture killer moves
        # 4. Non-capture history moves
        if self.follow_pv:
            pv_move = self.pv_table[0][self.ply]
            if pv_move:
                # pv move is a capture
                if pv_move in captures:
                    yield pv_move
                    captures.remove(pv_move)
                # pv move is a quiet move
                elif pv_move in quiet_moves:
                    yield pv_move
                    quiet_moves.remove(pv_move)
            else:
                self.follow_pv = False
        # Sort captures using MVV LVA
        for capture in sorted(captures, key=Board.score_capture, reverse=True):
            yield capture
        killer_move1, killer_move2 = self.killer_moves[0][self.ply], self.killer_moves[1][self.ply]
        if killer_move1 in quiet_moves:
            yield killer_move1
            quiet_moves.remove(killer_move1)
        if killer_move2 in quiet_moves:
            yield killer_move2
            quiet_moves.remove(killer_move2)
        for move in sorted(quiet_moves, key=self.score_quiet_move, reverse=True):
            yield move

    def generate_hash_key(self, pieces_only=False):
        hash_key = 0
        for side, bbs in enumerate(self.bitboards):
            for piece, bb in enumerate(bbs):
                for sq in get_set_bits_idx(bb):
                    hash_key ^= PIECE_KEYS[side][piece][sq]
        if pieces_only == True:
            return hash_key
        if self.enpassant:
            hash_key ^= ENPASSANT_KEYS[self.enpassant]
        hash_key ^= CASTLE_KEYS[self.castle] ^ (self.side * SIDE_KEY)
        return hash_key

    def read_hash_entry(self, alpha, beta, current_depth):
        score, depth, flag = self.transposition_table.get(self.board_hash, (0, -1, 0))
        if depth >= current_depth:
            if score > MATE_LOWERBOUND:
                #print('mate found')
                score -= self.ply
            elif score < -MATE_LOWERBOUND:
                #print('mate found')
                score += self.ply
            if flag == EXACT_FLAG:
                return score
            elif flag == ALPHA_FLAG:
                if score <= alpha:
                    return alpha
            else:
                if score >= beta:
                    return beta
    def write_hash_entry(self, score, depth, flag):
        if score > MATE_LOWERBOUND:
            score += self.ply
        elif score < - MATE_LOWERBOUND:
            score -= self.ply
        self.transposition_table[self.board_hash] = (score, depth, flag)



def encode_move(source, target, piece, promoted, capture, double, enpassant, castling):
    return (source) | (target << 6) | (piece << 12) | (promoted << 16) | (capture << 20) | (double << 21) | (
            enpassant << 22) | (castling << 23)


def decode_source(move): return move & 0x3f


def decode_target(move): return (move & 0xfc0) >> 6


def decode_piece(move): return (move & 0xf000) >> 12


def decode_promoted(move): return (move & 0xf0000) >> 16


def decode_capture(move): return move & 0x100000


def decode_double(move): return move & 0x200000


def decode_enpassant(move): return move & 0x400000


def decode_castling(move): return move & 0x800000


def to_uci(move):
    source = sq_to_coord[move[0]]
    target = sq_to_coord[move[1]]
    promotion = move[3]
    promotion = num_to_ascii[promotion] if promotion else ''
    return source + target + promotion


# move, piece capture double enpassant castling


tricky_pos = 'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1'
start_pos = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

test_pos = 'r3k2r/p11pqpb1/bn2pnp1/2pPN3/1p2P3/2N2Q1p/PPPBqPPP/R3K2R w KQkq - 0 1'

queen_pinned = '3k4/8/b5q1/1Q6/4N3/3K4/8/8 w - - 0 1'

enpassant_pinned = 'k7/8/8/2qpPK2/8/8/8/8 w - d6 0 1'

knight_pinned = '1k6/8/6b1/8/4N3/3K2r1/8/8 w - - 0 1'

mate_pos = '8/2Q5/5k2/8/3K4/8/8/8 w - - 0 1'


def sf_perft_divide(fen, depth):
    process = Popen('pythonscripts/stockfish_14.1_android_armv7/stockfish_14.1_android_armv7/stockfish.android.armv7',
                    stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True)
    command = f'position fen {fen}\ngo perft {depth}'
    out, error = process.communicate(input=command)
    perft_divide_dict = {}
    perft_divide = out.split('\n')[1:-4]
    for divide in perft_divide:
        move, count = divide.split(': ')
        perft_divide_dict[move] = count
    return perft_divide_dict


def debug_perft(fen, depth):
    board = Board()
    board.parse_fen(fen)
    board_pdiv = board.perft_divide(depth)
    sf_pdiv = sf_perft_divide(fen, depth)
    while board_pdiv != sf_pdiv:
        if board_pdiv.keys() != sf_pdiv.keys():
            print(f'Bug at fen {fen}')
            return fen
        for idx, (move, move_count) in enumerate(board_pdiv.items()):
            if sf_pdiv[move] != move_count:
                move = board.get_moves()[idx]
                board.make_move(move)
                fen = board.get_fen()
                depth -= 1
                board_pdiv = board.perft_divide(depth)
                sf_pdiv = sf_perft_divide(fen, depth)
                break
    print('No bugs')


depth_re = re.compile('(?<=depth )[0-9]+')
perft_re = re.compile('(?<=perft )[0-9]+')
inc_re = re.compile('(?<=(winc |binc ))[0-9]+')
time_re = re.compile('(?<=(wtime |btime ))[0-9]+')
movetime_re = re.compile('(?<=movetime )[0-9]+')
movestogo_re = re.compile('(?<=movestogo )[0-9]+')


def get_arg(regex, strng):
    match = regex.search(strng)
    if match:
        return int(regex.search(strng).group())
    else:
        return None


def uci_loop():
    board = Board()
    print('id name IdiotSandwich')
    print('id author Cheng Yong')
    print('uciok')
    while True:
        cmds = input()
        board.stopped = True
        cmds = cmds.strip(' ').split(' ')
        cmd, args = cmds[0], cmds[1:]
        if cmd == 'go':
            movestogo = 30
            depth = 64
            perft = 0
            inc, time, movetime = 0, 0, 0
            for i, arg in enumerate(args):
                if arg == 'depth':
                    depth = int(args[i + 1])
                elif arg == 'perft':
                    perft = int(args[i + 1])
                elif arg == 'binc' or arg == 'winc':
                    inc = int(args[i + 1])
                elif arg == 'wtime' or arg == 'btime':
                    time = int(args[i + 1])
                elif arg == 'movetime':
                    movetime = int(args[i + 1])
                    time = movetime
                    movestogo = 1
                elif arg == 'movestogo':
                    movestogo = int(args[i + 1])
            if perft:
                board.perft_divide(perft)
            else:
                if time:
                    time /= movestogo
                    time -= 50
                    time += inc
                    time /= 1000
                search_thread = threading.Thread(target=board.iterative_deepening_search, args=[depth, True, time])
                search_thread.start()
        elif cmd == 'position':
            if args[0] == 'startpos':
                board.parse_fen(start_pos)
            elif args[0] == 'fen':
                fen = ' '.join(args[1:])
                board.parse_fen(fen)
        elif cmd == 'ucinewgame':
            board.parse_fen(start_pos)
        elif cmd == 'uci':
            print('uciok')
        elif cmd == 'isready':
            print('readyok')
        elif cmd == 'quit':
            break
        elif cmd == 'd':
            board.print_board()


# debug_perft(start_pos, 4)
# error_pos = 'r31rk1/p1ppPpb1/bn2pnp1/4N3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R b KQkq - 0 1'
# board = Board()
# board.parse_fen(tricky_pos)


# ---------------------------------------------
# EVALUATION FUNCTION
# ---------------------------------------------
PIECE_VALUES = {
    P: 100,
    N: 300,
    B: 350,
    R: 500,
    Q: 1000,
    K: 10000
}
PIECE_VALUES = [100, 300, 350, 500, 10000, 1000]

P_psq = [
    90, 90, 90, 90, 90, 90, 90, 90,
    30, 30, 30, 40, 40, 30, 30, 30,
    20, 20, 20, 30, 30, 30, 20, 20,
    10, 10, 10, 20, 20, 10, 10, 10,
    5, 5, 10, 20, 20, 5, 5, 5,
    0, 0, 0, 5, 5, 0, 0, 0,
    0, 0, 0, -10, -10, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0
]

N_psq = [
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 10, 10, 0, 0, -5,
    -5, 5, 20, 20, 20, 20, 5, -5,
    -5, 10, 20, 30, 30, 20, 10, -5,
    -5, 10, 20, 30, 30, 20, 10, -5,
    -5, 5, 20, 10, 10, 20, 5, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, -10, 0, 0, 0, 0, -10, -5,
]

B_psq = [
    0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 10, 10, 0, 0, 0,
    0, 0, 10, 20, 20, 10, 0, 0,
    0, 0, 10, 20, 20, 10, 0, 0,
    0, 10, 0, 0, 0, 0, 10, 0,
    0, 30, 0, 0, 0, 0, 30, 0,
    0, 0, -10, 0, 0, -10, 0, 0
]

R_psq = [
    50, 50, 50, 50, 50, 50, 50, 50,
    50, 50, 50, 50, 50, 50, 50, 50,
    0, 0, 10, 20, 20, 10, 0, 0,
    0, 0, 10, 20, 20, 10, 0, 0,
    0, 0, 10, 20, 20, 10, 0, 0,
    0, 0, 10, 20, 20, 10, 0, 0,
    0, 0, 10, 20, 20, 10, 0, 0,
    0, 0, 0, 20, 20, 0, 0, 0
]

K_psq = [
    0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 5, 5, 5, 5, 0, 0,
    0, 5, 5, 10, 10, 5, 5, 0,
    0, 5, 10, 20, 20, 10, 5, 0,
    0, 5, 10, 20, 20, 10, 5, 0,
    0, 0, 5, 10, 10, 5, 0, 0,
    0, 5, 5, -5, -5, 0, 5, 0,
    0, 0, 5, 0, -15, 0, 10, 0
]

Q_psq = [0] * 64

MVV_LVA = [
    [105, 205, 305, 405, 505, 605],
    [104, 204, 304, 404, 504, 604],
    [103, 203, 303, 403, 503, 603],
    [102, 202, 302, 402, 502, 602],
    [101, 201, 301, 401, 501, 601],
    [100, 200, 300, 400, 500, 600]
]


def horizontal_flip(psq):
    new_psq = []
    for i in range(56, -1, -8):
        new_psq.extend(psq[i: i + 8])
    return new_psq


WHITE_PSQ = [P_psq, N_psq, B_psq, R_psq, K_psq, Q_psq]
BLACK_PSQ = [p_psq, n_psq, b_psq, r_psq, k_psq, q_psq] = [horizontal_flip(psq) for psq in WHITE_PSQ]

FULL_DEPTH_MOVES = 4
REDUCTION_LIMIT = 3
NMP_REDUCTION = 2

ROOK_MOVES = {
    g1: (1 << h1 | 1 << f1),
    c1: (1 << a1 | 1 << d1),
    g8: (1 << h8 | 1 << f8),
    c8: (1 << a8 | 1 << d8)
}

PIECE_KEYS = [[[0 for sq in range(64)] for piece in range(6)] for side in range(2)]
ENPASSANT_KEYS = [0 for sq in range(64)]
SIDE_KEY = 0
CASTLE_KEYS = [0 for i in range(16)]

def init_zobrist_keys():
    global SIDE_KEY
    for side in range(2):
        for piece in range(6):
            for sq in range(64):
                PIECE_KEYS[side][piece][sq] = get_random_64int()
    for sq in range(64):
        ENPASSANT_KEYS[sq] = get_random_64int()
    for i in range(16):
        CASTLE_KEYS[i] = get_random_64int()
    SIDE_KEY = get_random_64int()

EXACT_FLAG, ALPHA_FLAG, BETA_FLAG = range(3)

debug_pos = 'r3k1r1/p1ppNp2/1n3b2/3p4/1p2P3/2N5/PPPB1P1P/R4BK1 b q - 0 1'
debug_pos2 = 'r3k1r1/p1ppNp2/1n3b2/3p4/1p2P3/2N5/PPPB1P1P/R4B1K w q - 0 1'
if __name__ == '__main__':
    init_zobrist_keys()
    uci_loop()


''' bugs:
    - Searches more nodes than needed: mvvlva, count moves wrongly,
'''
