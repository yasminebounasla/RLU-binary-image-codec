import struct

HEADER_SIZE = 4          # largeur (2 octets) + hauteur (2 octets)
MAX_BLOCK = 32767        # 2**15 - 1 : maximum codable sur 15 bits (1 octet pour le bit de fort)


# fonctions pour lire et écrire l'en-tête (4 octets) d'une image RLE
def write_header(width, height):
    return struct.pack(">HH", width, height)

def read_header(data):
    width, height = struct.unpack(">HH", data[:4])
    return width, height


# fonctions pour compresser et décompresser les pixels d'une image RLE
def encode(pixels):
    """Compresse une liste de pixels (0 ou 255) en bytes (sans en-tête)."""
    out = bytearray()    # le résultat compressé
    buffer = []          # pixels "différents" en attente d'être écrits
    n = len(pixels)
    i = 0

    def flush_buffer():
        """Écrit la suite de pixels différents (mot bit fort = 0 + pixels)."""
        if buffer:                                        # s'il y a des pixels en attente
            out.extend(struct.pack(">H", len(buffer)))    # 1) écrire leur nombre (2 octets)
            out.extend(buffer)                            # 2) écrire les pixels eux-mêmes
            buffer.clear()                                # 3) vider le tampon

    while i < n:
        # 1) compter combien de fois le pixel courant se répète
        run = 1
        while i + run < n and pixels[i + run] == pixels[i] and run < MAX_BLOCK:
            run += 1

        if run >= 3:
            # 2) répétition : on écrit d'abord ce qui attend dans le tampon
            flush_buffer()
            out.extend(struct.pack(">H", 0x8000 | run))  # bit fort à 1 + compteur
            out.append(pixels[i])                        # la couleur répétée
            i += run
        else:
            # 3) pixel isolé (ou run de 2) : il va dans le tampon
            buffer.append(pixels[i])
            i += 1
            if len(buffer) == MAX_BLOCK:                 # tampon plein : on l'écrit
                flush_buffer()

    flush_buffer()       # 4) ne pas oublier ce qui reste à la fin
    return bytes(out)


def decode(data):
    """Décompresse des bytes RLE (sans en-tête) en liste de pixels."""
    out = bytearray()
    i = 0                      # position de lecture dans data
    n = len(data)

    while i < n:
        word = struct.unpack_from(">H", data, i)[0]   # lire le mot de 2 octets
        i += 2
        count = word & 0x7FFF                         # les 15 bits du compteur

        if word & 0x8000:                             # bit fort = 1 : répétition
            out.extend(bytes([data[i]]) * count)      # répéter la couleur count fois
            i += 1
        else:                                         # bit fort = 0 : suite brute
            out.extend(data[i:i + count])             # copier count octets tels quels
            i += count

    return list(out)

def from_string(s):
    """'WWWB' -> [255, 255, 255, 0]"""
    return [255 if c == "W" else 0 for c in s]


def save_rle(path, width, height, pixels):
    with open(path, "wb") as f:                       # wb = write binary
        f.write(write_header(width, height) + encode(pixels))


def load_rle(path):
    with open(path, "rb") as f:                       # rb = read binary
        data = f.read()
    width, height = read_header(data)                 # 4 premiers octets
    pixels = decode(data[HEADER_SIZE:])               # le reste
    return width, height, pixels



if __name__ == "__main__":
    W, B = 255, 0
    res = encode([W]*5 + [B, W] + [B]*4)  # W W W W W B W B B B B
    print(res.hex(" "))
    assert res.hex(" ") == "80 05 ff 00 02 00 ff 80 04 00"

    # tout blanc : un seul run
    assert encode([W]*10).hex(" ") == "80 0a ff"

    # run de 2 seulement : reste dans la suite "différents"
    assert encode([W, W, B]).hex(" ") == "00 03 ff ff 00"

    # run très long (> 32767) : doit être coupé en 2 blocs
    assert len(encode([W]*40000)) == 6    # 2 blocs de 3 octets chacun

    x = from_string("WWWWBWBBBB")
    assert decode(encode(x)) == x
    assert decode(encode([W, W, B])) == [W, W, B]
    assert decode(encode([W]*40000)) == [W]*40000
    assert decode(bytes.fromhex("80 04 ff 00 02 00 ff")) == from_string("WWWWBW")