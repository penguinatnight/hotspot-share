"""
Zero-dependency, pure-Python ISO/IEC 18004 QR Code Generator.
Outputs directly to Terminal (Unicode blocks) or SVG.
"""

def generate_qr_matrix(text, version=None, ec_level='L'):
    # Table format: (data_codewords, ec_codewords_per_block, num_blocks, align_coords)
    TABLE_L = {
        1: (19, 7, 1, []),
        2: (34, 10, 1, [6, 18]),
        3: (55, 15, 1, [6, 22]),
        4: (80, 20, 1, [6, 26]),
        5: (108, 26, 1, [6, 30]),
        6: (136, 18, 2, [6, 34]),
    }
    TABLE_M = {
        1: (16, 10, 1, []),
        2: (28, 16, 1, [6, 18]),
        3: (44, 26, 1, [6, 22]),
        4: (64, 18, 2, [6, 26]),
        5: (86, 24, 2, [6, 30]),
        6: (108, 16, 4, [6, 34]),
    }

    raw_data = text.encode('utf-8')
    data_len = len(raw_data)

    eff_ec = ec_level.upper()
    TABLE = TABLE_M if eff_ec == 'M' else TABLE_L

    if version is None:
        # Check if it fits in chosen level
        for v in range(1, 7):
            data_codewords, _, _, _ = TABLE[v]
            cap = data_codewords - 3  # 4-bit mode + 8-bit length + terminator
            if data_len <= cap:
                version = v
                break
        
        # If it doesn't fit in M, fallback to L which has ~30% higher capacity
        if version is None and eff_ec == 'M':
            eff_ec = 'L'
            TABLE = TABLE_L
            for v in range(1, 7):
                data_codewords, _, _, _ = TABLE[v]
                cap = data_codewords - 3
                if data_len <= cap:
                    version = v
                    break

        if version is None:
            version = 6

    data_cap, ec_bytes, num_blocks, align_coords = TABLE[version]

    # 1. Encode Data
    bits = []
    def add_bits(val, count):
        for i in range(count - 1, -1, -1):
            bits.append((val >> i) & 1)

    add_bits(0b0100, 4)  # 8-bit byte mode
    add_bits(data_len, 8 if version < 10 else 16)
    for b in raw_data:
        add_bits(b, 8)

    rem_space = (data_cap * 8) - len(bits)
    for _ in range(min(4, max(0, rem_space))):
        bits.append(0)

    while len(bits) % 8 != 0:
        bits.append(0)

    data_bytes = bytearray()
    for i in range(0, len(bits), 8):
        byte_val = 0
        for bit in bits[i:i+8]:
            byte_val = (byte_val << 1) | bit
        data_bytes.append(byte_val)

    pad_patterns = [0xEC, 0x11]
    p_idx = 0
    while len(data_bytes) < data_cap:
        data_bytes.append(pad_patterns[p_idx % 2])
        p_idx += 1

    # Truncate to capacity if text exceeds version 6 limit
    if len(data_bytes) > data_cap:
        data_bytes = data_bytes[:data_cap]

    # 2. Error Correction (Reed-Solomon over GF(256))
    exp = [0] * 512
    log = [0] * 256
    x = 1
    for i in range(255):
        exp[i] = x
        exp[i + 255] = x
        log[x] = i
        x = (x << 1) ^ (0x11d if (x & 0x80) else 0)
    log[0] = 0

    def gmult(a, b):
        return 0 if (a == 0 or b == 0) else exp[(log[a] + log[b]) % 255]

    def rs_poly(nsym):
        # Generates (x - a^0)(x - a^1)...(x - a^(nsym-1)) in highest-degree first order
        g = [1]
        for i in range(nsym):
            ng = [0] * (len(g) + 1)
            f = exp[i]
            for j, c in enumerate(g):
                ng[j] ^= c
                ng[j + 1] ^= gmult(c, f)
            g = ng
        return g

    def rs_encode(block_data, nsym):
        poly = rs_poly(nsym)
        out = [0] * (len(block_data) + nsym)
        out[:len(block_data)] = block_data
        for i in range(len(block_data)):
            coef = out[i]
            if coef != 0:
                for j in range(1, len(poly)):
                    out[i + j] ^= gmult(poly[j], coef)
        return out[len(block_data):]

    block_data_len = len(data_bytes) // num_blocks
    blocks_data = []
    blocks_ec = []
    for i in range(num_blocks):
        bd = data_bytes[i * block_data_len : (i + 1) * block_data_len]
        blocks_data.append(bd)
        blocks_ec.append(rs_encode(bd, ec_bytes))

    interleaved = bytearray()
    for i in range(block_data_len):
        for b in blocks_data:
            interleaved.append(b[i])
    for i in range(ec_bytes):
        for b in blocks_ec:
            interleaved.append(b[i])

    size = 17 + 4 * version
    grid = [[None] * size for _ in range(size)]

    def set_res(r, c, v):
        grid[r][c] = (1 if v else 0, True)

    def add_finder(start_r, start_c):
        for r in range(7):
            for c in range(7):
                v = (r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4))
                set_res(start_r + r, start_c + c, v)
        for r in range(-1, 8):
            for c in range(-1, 8):
                if 0 <= start_r + r < size and 0 <= start_c + c < size:
                    if grid[start_r + r][start_c + c] is None:
                        set_res(start_r + r, start_c + c, False)

    add_finder(0, 0)
    add_finder(0, size - 7)
    add_finder(size - 7, 0)

    for i in range(8, size - 8):
        if grid[6][i] is None: set_res(6, i, (i % 2 == 0))
        if grid[i][6] is None: set_res(i, 6, (i % 2 == 0))

    set_res(4 * version + 9, 8, True)

    if align_coords:
        for r in align_coords:
            for c in align_coords:
                if grid[r][c] is not None: continue
                for ar in range(-2, 3):
                    for ac in range(-2, 3):
                        v = (abs(ar) == 2 or abs(ac) == 2 or (ar == 0 and ac == 0))
                        set_res(r + ar, c + ac, v)

    for r in range(9):
        if grid[r][8] is None: set_res(r, 8, False)
        if grid[8][r] is None: set_res(8, r, False)
    for c in range(size - 8, size):
        if grid[8][c] is None: set_res(8, c, False)
    for r in range(size - 7, size):
        if grid[r][8] is None: set_res(r, 8, False)

    # Place data bits with zig-zag pattern
    all_bits = []
    for b in interleaved:
        for i in range(7, -1, -1):
            all_bits.append((b >> i) & 1)

    bit_idx = 0
    bit_len = len(all_bits)
    direction = -1
    c = size - 1
    while c > 0:
        if c == 6: c -= 1
        rows = range(size - 1, -1, -1) if direction == -1 else range(size)
        for r in rows:
            for col in (c, c - 1):
                if grid[r][col] is None:
                    val = all_bits[bit_idx] if bit_idx < bit_len else 0
                    mask = ((r + col) % 2 == 0)
                    grid[r][col] = (val ^ (1 if mask else 0), False)
                    bit_idx += 1
        direction = -direction
        c -= 2

    # Format info (Mask 000: EC Level L is 0x77C4, Level M is 0x5412)
    fmt_bits = 0x5412 if eff_ec == 'M' else 0x77C4
    for i in range(15):
        bit = (fmt_bits >> (14 - i)) & 1
        if i < 6: grid[8][i] = (bit, True)
        elif i == 6: grid[8][7] = (bit, True)
        elif i < 9: grid[8][8 + (i - 7)] = (bit, True)
        else: grid[8 - (i - 8) if i != 8 else 7][8] = (bit, True)

        if i < 7: grid[size - 1 - i][8] = (bit, True)
        else: grid[8][size - 15 + i] = (bit, True)

    return [[grid[r][c][0] for c in range(size)] for r in range(size)]

def get_terminal_qr(text, indent=4, ec_level='M'):
    matrix = generate_qr_matrix(text, ec_level=ec_level)
    size = len(matrix)
    pad = 2
    full_size = size + pad * 2
    full_grid = [[0] * full_size for _ in range(full_size)]
    for r in range(size):
        for c in range(size):
            full_grid[r + pad][c + pad] = matrix[r][c]

    out = []
    prefix = " " * indent
    for r in range(0, full_size, 2):
        line = [prefix]
        for c in range(full_size):
            top = full_grid[r][c]
            bottom = full_grid[r + 1][c] if r + 1 < full_size else 0
            if top == 1 and bottom == 1:
                line.append("\033[30;47m█\033[0m")
            elif top == 1 and bottom == 0:
                line.append("\033[37;40m▀\033[0m")
            elif top == 0 and bottom == 1:
                line.append("\033[37;40m▄\033[0m")
            else:
                line.append("\033[30;47m \033[0m")
        out.append("".join(line))
    return "\n".join(out)

def get_svg_qr(text, ec_level='M'):
    matrix = generate_qr_matrix(text, ec_level=ec_level)
    size = len(matrix)
    pad = 2
    total = size + pad * 2
    paths = []
    for r in range(size):
        for c in range(size):
            if matrix[r][c] == 1:
                paths.append(f"M{c + pad},{r + pad}h1v1h-1z")
    path_d = "".join(paths)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total} {total}" width="108" height="108" style="width:108px;height:108px;display:block;" shape-rendering="crispEdges" class="qr-svg"><rect x="0" y="0" width="{total}" height="{total}" fill="#ffffff"/><path d="{path_d}" fill="#000000"/></svg>'

def escape_wifi_str(s: str) -> str:
    """Escapes special characters in Wi-Fi SSID and password according to ZXing standard."""
    s = str(s or '').replace('\\', '\\\\')
    for ch in [';', ':', ',', '"']:
        s = s.replace(ch, f'\\{ch}')
    return s

def get_wifi_qr_text(ssid: str, password: str = "", security: str = "WPA") -> str:
    """Returns standard Wi-Fi configuration string for QR scanning."""
    sec = security.upper()
    esc_ssid = escape_wifi_str(ssid)
    if not password or sec == "NOPASS":
        return f"WIFI:T:nopass;S:{esc_ssid};;;"
    esc_pass = escape_wifi_str(password)
    return f"WIFI:T:{sec};S:{esc_ssid};P:{esc_pass};;"

