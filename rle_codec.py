import struct

HEADER_SIZE = 4          # largeur (2 octets) + hauteur (2 octets)
MAX_BLOCK = 32767        # 2**15 - 1 : maximum codable sur 15 bits ( the biggest number possible with 15 bits )


#function to write the header of the RLE file with width and height
def write_header(width, height):
    return struct.pack(">HH", width, height)  # .pack -> transfome the numbers into bytes


#function to read the header of the RLE file and return width and height
def read_header(data):
    width, height = struct.unpack(">HH", data[:HEADER_SIZE]) 
    return width, height


#fucntion to encode a list of pixels (0 or 255) into bytes (without header)
def encode(pixels, steps=None):
    out = bytearray()        # bytearray ( liste of bytes ) for the output
    buffer = []              # buffer for the raw pixels (run < 3)
    buffer_start = 0         # position of the first pixel in the buffer
    n = len(pixels)          # the number of pixels in the input list
    i = 0

    # helper function to flush the buffer and write it to the output
    def flush_buffer():
        if buffer:
            block = struct.pack(">H", len(buffer)) + bytes(buffer)   #create the block of output = bit fort 0 + taille + pixels
            out.extend(block) # add the block to the final output
            if steps is not None: 
                steps.append({"type": "raw", "start": buffer_start, "count": len(buffer),
                              "pixels": list(buffer), "bytes": block})
            buffer.clear() # clear the buffer

    # the main loop to process the input pixels
    while i < n:
        run = 1                                  # 1) count the run length of the current pixel
        while i + run < n and pixels[i + run] == pixels[i] and run < MAX_BLOCK:
            run += 1  # a run of identical pixels is found, increment the run length

        if run >= 3:                             # 2) repetition
            flush_buffer()                       #  first flush the buffer if there are any raw pixels
            block = struct.pack(">H", 0x8000 | run) + bytes([pixels[i]])   # bit fort 1 + compteur + couleur
            out.extend(block)
            if steps is not None:
                steps.append({"type": "rep", "start": i, "count": run,
                              "color": pixels[i], "bytes": block})
            i += run
        else:                                    # 3) no repetition, add the pixel to the buffer
            if not buffer:
                buffer_start = i
            buffer.append(pixels[i])
            i += 1
            if len(buffer) == MAX_BLOCK:         # flush the buffer if it reaches the maximum block size
                flush_buffer()

    flush_buffer()                               # 4) reste a la fin
    return bytes(out)


# fucntion to decode bytes (without header) into a list of pixels (0 or 255)
def decode(data, steps=None):
    out = bytearray()        # output buffer for the decoded pixels
    i = 0                      
    n = len(data)            # the number of bytes in the input data

    while i < n:
        start = i
        word = struct.unpack_from(">H", data, i)[0]   # read the next 2 bytes
        i += 2                                        # increment the index by 2 to move to the next word
        count = word & 0x7FFF                         # the next 15 bits represent the count of pixels
        pixel_start = len(out)                        # how many pixels have been decoded so far

        if word & 0x8000:                             # bit fort = 1 : repetition
            color = data[i]                           # read the color of the pixel to repeat
            out.extend(bytes([color]) * count)        # extend the output buffer with the repeated pixel
            i += 1
            if steps is not None:
                steps.append({"type": "rep", "offset": start, "length": 3, "word": word,
                              "count": count, "pixel_start": pixel_start, "color": color})
                
        else:                                         # bit fort = 0 : suite brute
            raw = bytes(data[i:i + count])            # read the next 'count' bytes as raw pixels
            out.extend(raw)                           # add the raw pixels to the output buffer
            i += count                                # increment the index by 'count' to move to the next word
            if steps is not None:
                steps.append({"type": "raw", "offset": start, "length": 2 + len(raw), "word": word,
                              "count": count, "pixel_start": pixel_start, "raw": raw})

    return list(out)


# save the uncompressed image: header + one byte per pixel
def save_raw(path, width, height, pixels):
    with open(path, "wb") as f:
        f.write(write_header(width, height) + bytes(pixels))
    return HEADER_SIZE + len(pixels)


# save the compressed image: header + RLE data
def save_rle(path, width, height, pixels, steps=None):
    if len(pixels) != width * height:
        raise ValueError("Le nombre de pixels ne correspond pas a largeur x hauteur.")
    data = write_header(width, height) + encode(pixels, steps)  # write header + RLE data
    with open(path, "wb") as f:                       # wb = ecriture binaire
        f.write(data)
    return len(data)



# read the compressed image: header + RLE data
def read_rle_file(path):
    with open(path, "rb") as f:                       # rb = lecture binaire
        data = f.read()
    if len(data) < HEADER_SIZE:
        raise ValueError("Fichier trop court : ce n'est pas un fichier .rle valide.")
    width, height = read_header(data)
    if width == 0 or height == 0:
        raise ValueError("En-tete invalide : largeur ou hauteur egale a 0.")
    return width, height, data[HEADER_SIZE:]




#-------------------------------------test----------------------------------------------------

# helper function to convert a string of 'W' and 'B' characters into a list of pixel values (255 for 'W', 0 for 'B')
def from_string(s):
    """'WWWB' -> [255, 255, 255, 0]"""
    return [255 if c == "W" else 0 for c in s]

# main function for testing the RLE codec
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