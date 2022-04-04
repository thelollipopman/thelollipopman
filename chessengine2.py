from gmpy2 import bit_scan1




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
        nwse = 0
        for rank, file in zip(range(8), range(i, -1, -1)):
            nwse |= 1 << (rank * 8 + file)
        NWSE.append(nwse)
    for i in range(1, 8):
        nwse = 0
        for rank, file in zip(range(7, -1, -1), range(i, 8)):
            nwse |= 1 << (rank * 8 + file)
        NWSE.append(nwse)
    for i in range(7, -1, -1):
        nesw = 0
        for rank, file in zip(range(8), range(i, 8)):
            nesw |= 1 << (rank * 8 + file)
        NESW.append(nesw)
    for i in range(6, -1, -1):
        nesw = 0
        for rank, file in zip(range(7, -1, -1), range(i, -1, -1)):
            nesw |= 1 << (rank * 8 + file)
        NESW.append(nesw)

def init_rect_lookup():
    global RECT_LOOKUP
    RECT_LOOKUP = [[0 for i in range(64)] for j in range(64)]
    for sq1 in range(64):
        rank1 = sq1 // 8
        file1 = sq1 % 8
        nwse1 = rank1 + file1
        nesw1 = rank1 + (8 - file1)
        for sq2 in range(64):
            rank2 = sq2 // 8
            file2 = sq2 % 8
            nwse2 = rank2 + file2
            nesw2 = rank2 + (8 - file2)
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
            mask |= sq1
            mask ^= sq2 if sq2 > sq1 else 0
            mask &= sq_between
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
    while i:
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
not_rank1 = 0xffffffffffffff
not_rank8 = 0xffffffffffffff00

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
    if (king >> 7) & not_a_file: attacks |= king >> 7
    if (king >> 9) & not_h_file: attacks |= king >> 9
    if (king >> 1) & not_h_file: attacks |= king >> 1
    if (king << 7) & not_a_file: attacks |= king << 7
    if (king << 9) & not_h_file: attacks |= king << 9
    if (king << 1) & not_a_file: attacks |= king << 1
    if (king >> 8): attacks |= king >> 8
    if (king << 8): attacks |= king << 8
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
0x40040822862081, 0x40810a4108000, 0x2008008400920040, 0x61050104000008, 0x8282021010016100, 0x41008210400a0001, 0x3004202104050c0, 0x22010108410402,
0x60400862888605, 0x6311401040228, 0x80801082000, 0x802a082080240100, 0x1860061210016800, 0x401016010a810, 0x1000060545201005, 0x21000c2098280819,
0x2020004242020200, 0x4102100490040101, 0x114012208001500, 0x108000682004460, 0x7809000490401000, 0x420b001601052912, 0x408c8206100300, 0x2231001041180110,
0x8010102008a02100, 0x204201004080084, 0x410500058008811, 0x480a040008010820, 0x2194082044002002, 0x2008a20001004200, 0x40908041041004, 0x881002200540404,
0x4001082002082101, 0x8110408880880, 0x8000404040080200, 0x200020082180080, 0x1184440400114100, 0xc220008020110412, 0x4088084040090100, 0x8822104100121080,
0x100111884008200a, 0x2844040288820200, 0x90901088003010, 0x1000a218000400, 0x1102010420204, 0x8414a3483000200, 0x6410849901420400, 0x201080200901040,
0x204880808050002, 0x1001008201210000, 0x16a6300a890040a, 0x8049000441108600, 0x2212002060410044, 0x100086308020020, 0x484241408020421, 0x105084028429c085,
0x4282480801080c, 0x81c098488088240, 0x1400000090480820, 0x4444000030208810, 0x1020142010820200, 0x2234802004018200, 0xc2040450820a00, 0x2101021090020
]

rook_magic_numbers = [
0xa080041440042080, 0xa840200410004001, 0xc800c1000200081, 0x100081001000420, 0x200020010080420, 0x3001c0002010008, 0x8480008002000100, 0x2080088004402900,
0x800098204000, 0x2024401000200040, 0x100802000801000, 0x120800800801000, 0x208808088000400, 0x2802200800400, 0x2200800100020080, 0x801000060821100,
0x80044006422000, 0x100808020004000, 0x12108a0010204200, 0x140848010000802, 0x481828014002800, 0x8094004002004100, 0x4010040010010802, 0x20008806104,
0x100400080208000, 0x2040002120081000, 0x21200680100081, 0x20100080080080, 0x2000a00200410, 0x20080800400, 0x80088400100102, 0x80004600042881,
0x4040008040800020, 0x440003000200801, 0x4200011004500, 0x188020010100100, 0x14800401802800, 0x2080040080800200, 0x124080204001001, 0x200046502000484,
0x480400080088020, 0x1000422010034000, 0x30200100110040, 0x100021010009, 0x2002080100110004, 0x202008004008002, 0x20020004010100, 0x2048440040820001,
0x101002200408200, 0x40802000401080, 0x4008142004410100, 0x2060820c0120200, 0x1001004080100, 0x20c020080040080, 0x2935610830022400, 0x44440041009200,
0x280001040802101, 0x2100190040002085, 0x80c0084100102001, 0x4024081001000421, 0x20030a0244872, 0x12001008414402, 0x2006104900a0804, 0x1004081002402
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
    return attacks ^ (get_bishop_attacks(occupancy ^ blockers, sq))

def get_rook_attacks(sq, occupancy):
    occupancy &= rook_masks[sq]
    occupancy *= rook_magic_numbers[sq]
    occupancy &= 0xffffffffffffffff
    occupancy >>= (64 - rook_bit_counts[sq])
    return rook_attacks[sq][occupancy]

def get_xray_rook_attacks(sq, blockers, occupancy):
    attacks = get_rook_attacks(sq, occupancy)
    blockers &= attacks
    return attacks ^ (get_rook_attacks(occupancy ^ blockers, sq))

def get_queen_attacks(sq, occupancy):
    return get_bishop_attacks(sq, occupancy) | get_rook_attacks(sq, occupancy)


# ---------------------------------------------
               # DRIVER CODE
# ---------------------------------------------

def init_attacks():
    init_jumping_attacks()
    init_sliding_attacks()



wk, wq, bk, bq = 1, 2, 4, 8
CASTLING_RIGHTS =[
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

ascii_pieces = [
    ['P', 'N', 'B', 'R', 'K', 'Q'],
    ['p', 'n', 'b', 'r', 'k', 'q', '']
    ]
unicode_pieces = [
    ['♙', '♘', '♗', '♖', '♔', '♕'],
    ['♟︎', '♞', '♝', '♜', '♚', '♛']
    ]
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
        self.bitboards = [
            [71776119061217280, 2594073385365405696, 4755801206503243776, 9295429630892703744, 1152921504606846976, 576460752303423488],
            [65280, 36, 66, 129, 16, 8]
        ]
        self.occupancy = [0, 0, 0]
        self.side = 0
        self.enpassant_states = []
        self.castle_states = []
        self.moves = []

    def print_board(self):
        for rank in range(8):
            print(8 - rank, end=' ')
            for file in range(8):
                sq = rank * 8 + file
                piece = -1
                side = -1
                for side, bbs in enumerate(self.bitboards):
                    for p, bb in enumerate(bbs):
                        if bb & 1 << sq:
                            piece = p
                            side = side
                            break
                print('.' if piece == -1 else ascii_pieces[side][piece], end=' ')
            print()
        print('  a b c d e f g h')
        print('    Side: {}'.format('black' if self.side else 'white'))
        print('    Enpass: {}'.format(sq_to_coord[self.enpassant_states[-1]] if self.enpassant_states[-1] != -1 else None))
        print('    Castle: {}{}{}{}'.format('K' if self.castle & wk else '-',
                                            'Q' if self.castle & wq else '-',
                                            'k' if self.castle & bk else '-',
                                            'q' if self.castle & bq else '-'
                                            ))

    def print_moves(self):
        print('move     piece     capture     double     enpass     castle')
        for m in self.moves:
            source, target, piece, promote, capture, double, enpass, castle = m
            move = ''.join((sq_to_coord[source], sq_to_coord[target], ascii_pieces[self.side][promote] if promote else ''))
            piece = ascii_pieces[self.side][piece]
            print('{0:<9}{1:5}     {2:<7}     {3:<6}     {4:<6}     {5:<5}'.format(move, piece, capture, double, enpass, castle))
        print('                    Total moves: {}                       '.format(len(self.moves)))
    def clear(self):
        self.bitboards = [
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0]
        ]
        self.occupancy = [0, 0, 0]
        self.side = 0
        self.enpassant_states = []
        self.castle_states = []

    def parse_fen(self, fen):
        self.clear()
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
        castle_bb = 0
        if castle != '-':
            for char in castle:
                if char == 'K':
                    castle_bb |= wk
                elif char == 'Q':
                    castle_bb |= wq
                elif char == 'k':
                    castle_bb |= bk
                else:
                    castle_bb |= bq
        self.castle_states.append(castle_bb)
        if enpassant != '-':
            file = ord(enpassant[0]) - 97
            rank = 8 - int(enpassant[1])
            self.enpassant_states.append(rank * 8 + file)
        else:
            self.enpassant_states.append(0)
        if side == 'b':
            self.side = 1
        for piece in P, N, B, R, K, Q:
            self.occupancy[WHITE] |= self.bitboards[piece]
        for piece in p, n, b, r, k, q:
            self.occupancy[BLACK] |= self.bitboards[piece]
        self.occupancy[BOTH] = self.occupancy[WHITE] | self.occupancy[BLACK]

    def is_square_attacked(self, square, attacking_side):
        pawn_bb, knight_bb, bishop_bb, rook_bb, king_bb, queen_bb = self.bitboards[attacking_side]
        if get_pawn_attacks(not attacking_side, square) & pawn_bb: return 1
        elif get_knight_attacks(square) & knight_bb: return 1
        elif get_bishop_attacks(square, self.occupancy[BOTH]) & bishop_bb: return 1
        elif get_rook_attacks(square, self.occupancy[BOTH]) & rook_bb: return 1
        elif get_king_attacks(square) & king_bb: return 1
        elif get_queen_attacks(square, self.occupancy[BOTH]) & queen_bb: return 1
        return 0

    def get_non_attacked_bb(self, bb, attacking_side):
        attacks = 0
        pawn_bb, knight_bb, bishop_bb, rook_bb, king_bb, queen_bb = self.bitboards[attacking_side]
        for sq in get_set_bits_idx(pawn_bb):
            attacks |= get_pawn_attacks(attacking_side, sq)
        for sq in get_set_bits_idx(knight_bb):
            attacks |= get_knight_attacks(sq)
        for sq in get_set_bits_idx(bishop_bb|queen_bb):
            attacks |= get_bishop_attacks(sq, self.occupancy[BOTH])
        for sq in get_set_bits_idx(rook_bb|queen_bb):
            attacks |= get_bishop_attacks(sq, self.occupancy[BOTH])
        for sq in get_set_bits_idx(king_bb):
            attacks |= get_king_attacks(sq)
        return bb & (bb ^ attacks)

    def print_attacked_squares(self, side):
        for rank in range(8):
            print(8 - rank, end=' ')
            for file in range(8):
                sq = rank * 8 + file
                print(1 if self.is_square_attacked(sq, side) else '.', end=' ')
            print()
        print('  a b c d e f g h')

    def get_captured_piece(self, sq):
        bb = 1 << sq
        for piece, piece_bb in enumerate(self.bitboards[not self.side]):
            if piece_bb & bb:
                return piece


    def get_moves(self):
        # get variables for the side to move
        pawn_bb, knight_bb, bishop_bb, rook_bb, king_bb, queen_bb = self.bitboards[self.side]
        opp_pawn_bb, opp_knight_bb, opp_bishop_bb, opp_rook_bb, opp_king_bb, opp_queen_bb = self.bitboards[not self.side]
        occupancy, opp_occupancy, both_occupancy = self.occupancy[self.side], self.occupancy[not self.side], self.occupancy[BOTH]
        enpassant = self.enpassant_states[-1]
        if self.side:
            pawn_dir = 8
            min_promo_sq, max_promo_sq = a2, h2
            min_double_sq, max_double_sq = a7, h7
            kingside_castle_sqs, queenside_castle_sqs = 96, 28
            kingside_castle_flag, queenside_castle_flag = 4, 8
            castle_b_sq, castle_c_sq, castle_d_sq, castle_f_sq, castle_g_sq = b8, c8, d8, f8, g8
        else:
            pawn_dir = -8
            min_promo_sq, max_promo_sq = a7, h7
            min_double_sq, max_double_sq = a2, h2
            kingside_castle_sqs, queenside_castle_sqs = 6917529027641081856, 2017612633061982208
            kingside_castle_flag, queenside_castle_flag = 1, 2
            castle_b_sq, castle_c_sq, castle_d_sq, castle_f_sq, castle_g_sq = b1, c1, d1, f1, g1

        # generate check mask
        king_sq = count_bits(king_bb)
        pawn_checkmask = get_pawn_attacks(self.side, king_sq) & opp_pawn_bb
        knight_checkmask = get_knight_attacks(king_sq) & opp_knight_bb
        bishop_checkmask = get_bishop_attacks(king_sq, both_occupancy) & (opp_bishop_bb | opp_queen_bb)
        rook_checkmask = get_rook_attacks(king_sq, both_occupancy) & (opp_rook_bb | opp_queen_bb)
        if rook_checkmask:
            if bishop_checkmask or knight_checkmask:
                for target_sq in get_set_bits_idx(self.get_non_attacked_bb(get_king_attacks(king_sq) & flip_bit(occupancy), not self.side)):
                    if 1 << target_sq & opp_occupancy:
                        capture = self.get_captured_piece(target_sq)
                        self.moves.append((king_sq, target_sq, K, -1, capture, 0, 0, 0))
                    else:
                        self.moves.append((king_sq, target_sq, K, -1, -1, 0, 0, 0))
                return
        elif bishop_checkmask:
            if rook_checkmask or knight_checkmask:
                for target_sq in get_set_bits_idx(self.get_non_attacked_bb(get_king_attacks(king_sq) & flip_bit(occupancy), not self.side)):
                    if 1 << target_sq & opp_occupancy:
                        capture = self.get_captured_piece(target_sq)
                        self.moves.append((king_sq, target_sq, K, -1, capture, 0, 0, 0))
                    else:
                        self.moves.append((king_sq, target_sq, K, -1, -1, 0, 0, 0))
                return
        checkmask = pawn_checkmask | knight_checkmask | rook_checkmask | bishop_checkmask

        # generate pin mask
        horizontal_pinmask = 0
        horizontal_pinner = get_xray_rook_attacks(king_sq, occupancy, both_occupancy) & (opp_rook_bb|opp_queen_bb)
        for pinner in get_set_bits_idx(horizontal_pinner):
            pinmask = RECT_LOOKUP[pinner][king_sq]
            if pinmask & occupancy:
                horizontal_pinmask |= pinmask
        diagonal_pinmask = 0
        diagonal_pinner = get_xray_bishop_attacks(king_sq, occupancy, both_occupancy) & (opp_bishop_bb|opp_queen_bb)
        for pinner in get_set_bits_idx(diagonal_pinner):
            pinmask = RECT_LOOKUP[pinner][king_sq]
            if pinmask & occupancy:
                diagonal_pinmask |= pinmask

        # GENERATE PAWN MOVES
        for source_sq in get_set_bits_idx(pawn_bb):
            target_sq = source_sq + pawn_dir
            # CHECK FOR PIECES BLOCKING PAWN
            if not both_occupancy & (1 << target_sq):
                # PROMOTION PAWN PUSHES
                if min_promo_sq <= source_sq <= max_promo_sq:
                    self.moves.append((source_sq, target_sq, P, Q, -1, 0, 0, 0))
                    self.moves.append((source_sq, target_sq, P, R, -1, 0, 0, 0))
                    self.moves.append((source_sq, target_sq, P, B, -1, 0, 0, 0))
                    self.moves.append((source_sq, target_sq, P, N, -1, 0, 0, 0))
                else:
                    # SINGLE PAWN PUSHES
                    self.moves.append((source_sq, target_sq, P, -1, -1, 0, 0, 0))
                    # DOUBLE PAWN PUSHES
                    if min_double_sq <= source_sq <= max_double_sq and (1 << (target_sq + pawn_dir)) & both_occupancy:
                        self.moves.append((source_sq, target_sq + pawn_dir, P, -1, -1, 1, 0, 0))
            attacks = get_pawn_attacks(self.side, source_sq) & opp_occupancy
            for target_sq in get_set_bits_idx(attacks):
                captured_piece = self.get_captured_piece(target_sq)
                # CAPTURE PROMOTIONS
                if min_promo_sq <= source_sq <= max_promo_sq:
                    self.moves.append((source_sq, target_sq, P, Q, captured_piece, 0, 0, 0))
                    self.moves.append((source_sq, target_sq, P, R, captured_piece, 0, 0, 0))
                    self.moves.append((source_sq, target_sq, P, B, captured_piece, 0, 0, 0))
                    self.moves.append((source_sq, target_sq, P, N, captured_piece, 0, 0, 0))
                # NORMAL CAPTURES
                else:
                    self.moves.append((source_sq, target_sq, P, -1, captured_piece, 0, 0, 0))
        # EN PASSANT
        enpassant_source_sq = get_pawn_attacks(not self.side, enpassant) & pawn_bb
        for source_sq in get_set_bits_idx(enpassant_source_sq):
            self.moves.append((source_sq, target_sq, P, -1, P, 0, 0, 0))


        # CASTLING MOVES

        # kingside castling
        if self.castle & kingside_castle_flag:
            # squares between king's rook and king are unoccupied
            if not kingside_castle_sqs & both_occupancy:
                # f and g squares between king's rook and king are not under attack
                if not self.is_square_attacked(castle_f_sq, not self.side) and not self.is_square_attacked(castle_g_sq, not self.side) and not self.is_square_attacked(king_sq, not self.side):
                    self.moves.append((e1, g1, K, -1, -1, 0, 0, kingside_castle_flag))
        # queenside castle
        if self.castle & queenside_castle_flag:
            # squares between queen's rook and king are unoccupied
            if not queenside_castle_sqs & both_occupancy:
                # squares between queen's rook and king are not under attack
                if not self.is_square_attacked(castle_b_sq, not self.side) and not self.is_square_attacked(castle_c_sq,not self.side) and not self.is_square_attacked(castle_d_sq, not self.side) and not self.is_square_attacked(king_sq, not self.side):
                    self.moves.append((e1, c1, K, -1, -1, 0, 0, queenside_castle_flag))


        # PIECE MOVES

        # KNIGHT MOVES
        for source_sq in get_set_bits_idx(knight_bb & flip_bit(horizontal_pinmask | diagonal_pinmask)):
            attacks = get_knight_attacks(source_sq) & checkmask & flip_bit(occupancy)
            for target_sq in get_set_bits_idx(attacks):
                # CAPTURES
                if 1 << target_sq & opp_occupancy:
                    self.moves.append(source_sq, target_sq, N, -1, self.get_captured_piece(target_sq), 0, 0, 0)
                # QUIET MOVES
                else:
                    self.moves.append(source_sq, target_sq, N, -1, -1, 0, 0, 0)

        # BISHOP MOVES
        for source_sq in get_set_bits_idx(bishop_bb & flip_bit(horizontal_pinmask)):
            attacks = get_bishop_attacks(source_sq, both_occupancy) & checkmask & flip_bit(occupancy)
            if source_sq & diagonal_pinmask:
                attacks &= diagonal_pinmask
            for target_sq in get_set_bits_idx(attacks):
                # CAPTURES
                if 1 << target_sq & opp_occupancy:
                    self.moves.append(source_sq, target_sq, B, -1, self.get_captured_piece(target_sq), 0, 0, 0)
                # QUIET MOVES
                else:
                    self.moves.append(source_sq, target_sq, B, -1, -1, 0, 0, 0)

        # ROOK MOVES
        for source_sq in get_set_bits_idx(rook_bb & flip_bit(diagonal_pinmask)):
            attacks = get_rook_attacks(source_sq, both_occupancy) & checkmask & flip_bit(occupancy)
            if source_sq & horizontal_pinmask:
                attacks &= horizontal_pinmask
            for target_sq in get_set_bits_idx(attacks):
                # CAPTURES
                if 1 << target_sq & opp_occupancy:
                    self.moves.append(source_sq, target_sq, R, -1, self.get_captured_piece(target_sq), 0, 0, 0)
                # QUIET MOVES
                else:
                    self.moves.append(source_sq, target_sq, R, -1, -1, 0, 0, 0)

        # QUEEN MOVES
        for source_sq in get_set_bits_idx(queen_bb):
            attacks = get_queen_attacks(source_sq, both_occupancy) & checkmask & flip_bit(occupancy)
            if source_sq & horizontal_pinmask:
                attacks &= horizontal_pinmask
            elif source_sq & diagonal_pinmask:
                attacks &= diagonal_pinmask
            for target_sq in get_set_bits_idx(attacks):
                # CAPTURES
                if 1 << target_sq & opp_occupancy:
                    self.moves.append(source_sq, target_sq, Q, -1, self.get_captured_piece(target_sq), 0, 0, 0)
                # QUIET MOVES
                else:
                    self.moves.append(source_sq, target_sq, Q, -1, -1, 0, 0, 0)

        # KING MOVES
        for target_sq in get_set_bits_idx(get_king_attacks(king_sq) & flip_bit(occupancy)):
            if not self.is_square_attacked(target_sq, not self.side):
                if target_sq & opp_occupancy:
                    self.moves.append((king_sq, target_sq, K, -1, self.get_captured_piece(target_sq), 0, 0, 0))
                else:
                    self.moves.append((king_sq, target_sq, K, -1, -1, 0, 0, 0))
        for source_sq in get_set_bits_idx(king_bb):
            for target_sq in get_set_bits_idx(get_king_attacks(source_sq)):
                # CAPTURES
                if 1 << target_sq & opp_occupancy:
                    self.moves.append(source_sq, target_sq, K, -1, self.get_captured_piece(target_sq), 0, 0, 0)
                # QUIET MOVES
                else:
                    self.moves.append(source_sq, target_sq, K, -1, -1, 0, 0, 0)

                # QUIET MOVE



        '''if self.side == WHITE:
            bb = self.bitboards[P]
            while bb:
                source_sq = get_lsb_index(bb)
                target_sq = source_sq - 8
                if target_sq >= a8 and not get_bit(self.occupancy[BOTH], target_sq):
                    # promotion
                    if a7 <= source_sq <= h7:
                        self.moves.append((source_sq, target_sq, P, Q, -1, 0, 0, 0))
                        self.moves.append((source_sq, target_sq, P, R, -1, 0, 0, 0))
                        self.moves.append((source_sq, target_sq, P, B, -1, 0, 0, 0))
                        self.moves.append((source_sq, target_sq, P, N, -1, 0, 0, 0))
                    else:
                        # pawn push
                        self.moves.append((source_sq, target_sq, P, None, None, None, None, None))
                        # double pawn push
                        if a2 <= source_sq <= h2 and not get_bit(self.occupancy[BOTH], target_sq - 8):
                            self.moves.append((source_sq, target_sq - 8, P, None, None, 1, None, None))
                attacks = get_pawn_attacks(self.side, source_sq) & self.occupancy[BLACK]
                while attacks:
                    target_sq = get_lsb_index(attacks)
                    captured_piece = self.get_captured_piece(target_sq)
                    # capture promotions
                    if a7 <= source_sq <= h7:
                        self.moves.append((source_sq, target_sq, P, Q, captured_piece, None, None, None))
                        self.moves.append((source_sq, target_sq, P, B, captured_piece, None, None, None))
                        self.moves.append((source_sq, target_sq, P, R, captured_piece, None, None, None))
                        self.moves.append((source_sq, target_sq, P, N, captured_piece, None, None, None))
                    # normal captures
                    else:
                        self.moves.append((source_sq, target_sq, P, None, captured_piece, None, None, None))
                    attacks = pop_bit(attacks, target_sq)
                if self.enpassant:
                    attack = get_pawn_attacks(self.side, source_sq) & (1 << self.enpassant)
                    if attack:
                        self.moves.append((source_sq, target_sq, P, None, p, None, 1, None))
                bb = pop_bit(bb, source_sq)
            # Catling moves
            # kingside castle
            if self.castle & wk:
                # squares between king's rook and king are unoccupied
                if not get_bit(self.occupancy[BOTH], f1) and not get_bit(self.occupancy[BOTH], g1):
                    # squares between king's rook and king are not under attack
                    if not self.is_square_attacked(e1, BLACK) and not self.is_square_attacked(f1, BLACK):
                        self.moves.append((e1, g1, K, None, None, None, None, wk))
            # queenside castle
            if self.castle & wq:
                # squares between queen's rook and king are unoccupied
                if not get_bit(self.occupancy[BOTH], b1) and not get_bit(self.occupancy[BOTH], c1) and not get_bit(self.occupancy[BOTH], d1):
                    # squares between queen's rook and king are not under attack
                    if not self.is_square_attacked(b1, BLACK) and not self.is_square_attacked(d1, BLACK) and not self.is_square_attacked(e1, BLACK):
                        self.moves.append((e1, c1, K, None, None, None, None, wq))

        else:
            bb = self.bitboards[p]
            while bb:
                source_sq = get_lsb_index(bb)
                target_sq = source_sq + 8
                if target_sq <= h1 and not get_bit(self.occupancy[BOTH], target_sq):
                    # promotion
                    if a2 <= source_sq <= h2:
                        self.moves.append((source_sq, target_sq, p, q, None, None, None, None))
                        self.moves.append((source_sq, target_sq, p, b, None, None, None, None))
                        self.moves.append((source_sq, target_sq, p, r, None, None, None, None))
                        self.moves.append((source_sq, target_sq, p, n, None, None, None, None))
                    else:
                        # pawn push
                        self.moves.append((source_sq, target_sq, p, None, None, None, None, None))
                        if a7 <= source_sq <= h7 and not get_bit(self.occupancy[BOTH], target_sq + 8):
                            self.moves.append((source_sq, target_sq + 8, p, None, None, 1, None, None))
                attacks = get_pawn_attacks(self.side, source_sq) & self.occupancy[WHITE]
                while attacks:
                    target_sq = get_lsb_index(attacks)
                    captured_piece = self.get_captured_piece(target_sq)
                    if a2 <= source_sq <= h2:
                        self.moves.append((source_sq, target_sq, p, q, captured_piece, None, None, None))
                        self.moves.append((source_sq, target_sq, p, b, captured_piece, None, None, None))
                        self.moves.append((source_sq, target_sq, p, r, captured_piece, None, None, None))
                        self.moves.append((source_sq, target_sq, p, n, captured_piece, None, None, None))
                    else:
                        self.moves.append((source_sq, target_sq, p, None, captured_piece, None, None, None))
                    attacks = pop_bit(attacks, target_sq)
                if self.enpassant:
                    attack = get_pawn_attacks(self.side, source_sq) & (1 << self.enpassant)
                    if attack:
                        self.moves.append((source_sq, target_sq, p, None, P, None, 1, None))
                bb = pop_bit(bb, source_sq)
            # castling moves
            # kingside castle
            if self.castle & bk:
                # squares between king's rook and king are unoccupied
                if not get_bit(self.occupancy[BOTH], f8) and not get_bit(self.occupancy[BOTH], g8):
                    # squares between king's rook and king are not under attack
                    if not self.is_square_attacked(e8, WHITE) and not self.is_square_attacked(f8, WHITE):
                        self.moves.append((e8, g8, k, None, None, None, None, bk))
            # queenside castle
            if self.castle & bq:
                # squares between queen's rook and king are unoccupied
                if not get_bit(self.occupancy[BOTH], b8) and not get_bit(self.occupancy[BOTH], c8) and not get_bit(self.occupancy[BOTH], d8):
                    # squares between queen's rook and king are not under attack
                    if not self.is_square_attacked(b8, WHITE) and not self.is_square_attacked(d8, WHITE) and not self.is_square_attacked(e8, WHITE):
                        self.moves.append((e8, c8, k, None, None, None, None, bq))
        attack_pieces = PIECES_BY_COLOUR[self.side][1:]
        attack_funcs = get_knight_attacks, get_bishop_attacks, get_rook_attacks, get_king_attacks, get_queen_attacks
        for piece, func in zip(attack_pieces, attack_funcs):
            bb = self.bitboards[piece]
            while bb:
                source_sq = get_lsb_index(bb)
                if func == get_knight_attacks or func == get_king_attacks:
                    attacks = func(source_sq) & flip_bit(self.occupancy[self.side])
                else:
                    attacks = func(source_sq, self.occupancy[BOTH]) & flip_bit(self.occupancy[self.side])
                while attacks:
                    target_sq = get_lsb_index(attacks)
                    # Captures
                    if get_bit(self.occupancy[not self.side], target_sq):
                        self.moves.append((source_sq, target_sq, piece, None, self.get_captured_piece(target_sq), None, None, None))
                    # Quiet moves
                    else:
                        self.moves.append((source_sq, target_sq, piece, None, None, None, None, None))
                    attacks = pop_bit(attacks, target_sq)
                bb = pop_bit(bb, source_sq)'''

    def make_move(self, move, all_moves=True):
        source_sq, target_sq, piece, promote, capture, double, enpass, castle = move
        bbs = self.bitboards[self.side], opp_bbs = self.bitboards[not self.side]
        if all_moves:
            bbs[piece] ^= (1 << source_sq | 1 << target_sq)
            if capture != -1:
                opp_bbs[capture] ^= 1 << target_sq
            if promote:
                bbs[piece] ^= 1 << target_sq
                bbs[promote] ^= 1 << target_sq
            if enpass:
                pawn_dir = 8 if self.side else -8
                opp_bbs[P] ^= 1 << (target_sq - pawn_dir)
            if double:
                pawn_dir = 8 if self.side else -8
                self.enpassant_states.append(target_sq - pawn_dir)




        if all_moves:
            # remove source square, set target square for relevant piece
            self.bitboards[piece] ^= (1 << source_sq | 1 << target_sq)
            # remove any captured pieces on target square
            if capture != None:
                self.bitboards[capture] = pop_bit(self.bitboards[capture], target_sq)
            if promote:
                self.bitboards[piece] = pop_bit(self.bitboards[piece], target_sq)
                self.bitboards[promote] = set_bit(self.bitboards[promote], target_sq)
            if enpass:
                if self.side == WHITE:
                    self.bitboards[p] = pop_bit(self.bitboards[p], target_sq + 8)
                else:
                    self.bitboards[P] = pop_bit(self.bitboards[P], target_sq - 8)
            self.enpassant = None
            if double:
                if self.side == WHITE:
                    self.enpassant = target_sq + 8
                else:
                    self.enpassant = target_sq - 8
            if castle:
                if self.side == WHITE:
                    if target_sq == g1:
                        self.bitboards[R] = pop_bit(self.bitboards[R], h1)
                        self.bitboards[R] = set_bit(self.bitboards[R], f1)
                    else:
                        self.bitboards[R] = pop_bit(self.bitboards[R], a1)
                        self.bitboards[R] = set_bit(self.bitboards[R], d1)
                else:
                    if target_sq == g8:
                        self.bitboards[r] = pop_bit(self.bitboards[r], h8)
                        self.bitboards[r] = set_bit(self.bitboards[r], f8)
                    else:
                        self.bitboards[r] = pop_bit(self.bitboards[r], a8)
                        self.bitboards[r] = set_bit(self.bitboards[r], d8)
            self.castle &= CASTLING_RIGHTS[source_sq]
            self.castle &= CASTLING_RIGHTS[target_sq]
            #update occupancies
            self.occupancy = [0, 0, 0]
            for piece in range(6):
                self.occupancy[WHITE] |= self.bitboards[WHITE][piece]
                self.occupancy[BLACK] |= self.bitboards[BLACK][piece]
            self.occupancy[BOTH] = self.occupancy[WHITE] | self.occupancy[BLACK]

            # change side to move
            self.side = not self.side

            # if move results in own king being in check, its illegal
            if self.is_square_attacked(get_lsb_index(self.bitboards[k if self.side == WHITE else K]), self.side):
                if piece == K and target == e2:
                    print('how did we get here')
                self.prev_move()
                return 0
            else:
                return 1


    def prev_move(self):
        self.bitboards = self.prev_bitboards.copy()
        self.occupancy = self.prev_occupancy.copy()
        self.side = not self.side
        self.enpassant = self.prev_enpassant
        self.castle = self.prev_castle
    def save_move(self):
        self.prev_bitboards = self.bitboards.copy()
        self.prev_occupancy = self.occupancy.copy()
        self.prev_enpassant = self.enpassant
        self.prev_castle = self.castle




def encode_move(source, target, piece, promoted, capture, double, enpassant, castling):
    return (source) | (target << 6) | (piece << 12) | (promoted << 16) | (capture << 20) | (double << 21) | (enpassant << 22) | (castling << 23)

def decode_source(move): return move & 0x3f
def decode_target(move): return (move & 0xfc0) >> 6
def decode_piece(move): return (move & 0xf000) >> 12
def decode_promoted(move): return (move & 0xf0000) >> 16
def decode_capture(move): return move & 0x100000
def decode_double(move): return move & 0x200000
def decode_enpassant(move): return move & 0x400000
def decode_castling(move): return move & 0x800000


# move, piece capture double enpassant castling



tricky_pos = 'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1'
start_pos = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

test_pos = 'r3k2r/p11pqpb1/bn2pnp1/2pPN3/1p2P3/2N2Q1p/PPPBqPPP/R3K2R w KQkq - 0 1'
init_attacks()
test = Board()
test.parse_fen(test_pos)
test.get_moves()
#test.print_moves()
'''for move in test.moves:
    test.make_move(*move)
    test.print_board()
    input()
    test.prev_move()
    test.print_board()
    input()'''
#test.print_board()

'''for move in test.moves:
    if not test.make_move(*move):
        continue
    print('no check!')
    test.print_board()
    input()
    test.prev_move()
    test.print_board()
    input()

def get_setbits(bb):
    while bb:
        i = get_lsb_index(bb)
        bb = pop_bit(bb, i)
        yield i'''

init_lines()
init_rect_lookup()
test = [
    [0, 63],
    [48, 53],
    [53, 39],
    [17, 33]
]
for i in RANKS, FILES, NWSE, NESW:
    for j in i:
        pprint_bb(j)
for sq1, sq2 in test:
    pprint_bb(RECT_LOOKUP[sq1][sq2])