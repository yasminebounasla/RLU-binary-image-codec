import struct

HEADER_SIZE = 4          # largeur (2 octets) + hauteur (2 octets)
MAX_BLOCK = 32767        # 2**15 - 1 : maximum codable sur 15 bits

#function to write the header of the RLE file with width and height
def write_header(width, height):
    return struct.pack(">HH", width, height)

#function to read the header of the RLE file and return width and height
def read_header(data):
    width, height = struct.unpack(">HH", data[:HEADER_SIZE])
    return width, height


#fucntion to encode a list of pixels (0 or 255) into bytes (without header)
def encode(pixels, steps=None):
    """Compresse une liste de pixels (0 ou 255) en bytes (sans en-tete)"""
    out = bytearray()
    buffer = []              # pixels "differents" en attente
    buffer_start = 0         # position du 1er pixel du tampon
    n = len(pixels)
    i = 0

    def flush_buffer():
        if buffer:
            block = struct.pack(">H", len(buffer)) + bytes(buffer)   # bit fort 0 + taille + pixels
            out.extend(block)
            if steps is not None:
                steps.append({"type": "raw", "start": buffer_start, "count": len(buffer),
                              "pixels": list(buffer), "bytes": block})
            buffer.clear()

    while i < n:
        run = 1                                  # 1) compter la repetition
        while i + run < n and pixels[i + run] == pixels[i] and run < MAX_BLOCK:
            run += 1

        if run >= 3:                             # 2) repetition
            flush_buffer()                       #    d'abord le tampon (ordre)
            block = struct.pack(">H", 0x8000 | run) + bytes([pixels[i]])   # bit fort 1 + compteur + couleur
            out.extend(block)
            if steps is not None:
                steps.append({"type": "rep", "start": i, "count": run,
                              "color": pixels[i], "bytes": block})
            i += run
        else:                                    # 3) pixel isole ou run de 2 -> tampon
            if not buffer:
                buffer_start = i
            buffer.append(pixels[i])
            i += 1
            if len(buffer) == MAX_BLOCK:
                flush_buffer()

    flush_buffer()                               # 4) reste a la fin
    return bytes(out)


def decode(data, steps=None):
    """Decompresse des bytes RLE (sans en-tete) en liste de pixels.
    Si steps est une liste, chaque bloc lu y est ajoute."""
    out = bytearray()
    i = 0
    n = len(data)

    while i < n:
        start = i
        word = struct.unpack_from(">H", data, i)[0]   # lire le mot de 2 octets
        i += 2
        count = word & 0x7FFF                         # les 15 bits du compteur
        pixel_start = len(out)

        if word & 0x8000:                             # bit fort = 1 : repetition
            color = data[i]
            out.extend(bytes([color]) * count)
            i += 1
            if steps is not None:
                steps.append({"type": "rep", "offset": start, "length": 3, "word": word,
                              "count": count, "pixel_start": pixel_start, "color": color})
        else:                                         # bit fort = 0 : suite brute
            raw = bytes(data[i:i + count])
            out.extend(raw)
            i += count
            if steps is not None:
                steps.append({"type": "raw", "offset": start, "length": 2 + len(raw), "word": word,
                              "count": count, "pixel_start": pixel_start, "raw": raw})

    return list(out)


def save_raw(path, width, height, pixels):
    """Sauvegarde l'image non compressee : en-tete + un octet par pixel."""
    with open(path, "wb") as f:
        f.write(write_header(width, height) + bytes(pixels))
    return HEADER_SIZE + len(pixels)


def save_rle(path, width, height, pixels, steps=None):
    """Compresse les pixels et ecrit le fichier .rle. Retourne la taille du fichier."""
    if len(pixels) != width * height:
        raise ValueError("Le nombre de pixels ne correspond pas a largeur x hauteur.")
    data = write_header(width, height) + encode(pixels, steps)
    with open(path, "wb") as f:                       # wb = ecriture binaire
        f.write(data)
    return len(data)


def read_rle_file(path):
    """Lit un fichier .rle : retourne (largeur, hauteur, donnees compressees)."""
    with open(path, "rb") as f:                       # rb = lecture binaire
        data = f.read()
    if len(data) < HEADER_SIZE:
        raise ValueError("Fichier trop court : ce n'est pas un fichier .rle valide.")
    width, height = read_header(data)
    if width == 0 or height == 0:
        raise ValueError("En-tete invalide : largeur ou hauteur egale a 0.")
    return width, height, data[HEADER_SIZE:]


def from_string(s):
    """'WWWB' -> [255, 255, 255, 0]"""
    return [255 if c == "W" else 0 for c in s]


if __name__ == "__main__":
    W, B = 255, 0
    x = from_string("WWWWWBWBBBB")
    st = []
    res = encode(x, steps=st)
    print(res.hex(" "))
    assert res.hex(" ") == "80 05 ff 00 02 00 ff 80 04 00"
    for s in st:
        print(s["type"], s["start"], s["count"], s["bytes"].hex(" "))
    assert decode(res) == x

    assert encode([W]*10).hex(" ") == "80 0a ff"
    assert encode([W, W, B]).hex(" ") == "00 03 ff ff 00"
    assert len(encode([W]*40000)) == 6
    alt = [W if k % 2 else B for k in range(40000)]
    assert decode(encode(alt)) == alt
    print("Tous les tests passent.")