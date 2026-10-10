import os
import struct
import tkinter as tk
from tkinter import messagebox, ttk

from rle_codec import HEADER_SIZE, decode, read_rle_file, save_raw, save_rle, write_header

BLACK, WHITE = 0, 255
MAX_DIM = 128            # taille max choisie dans l'interface
CANVAS_MAX = 320         # taille maximale d'une zone d'image, en pixels ecran


# programme folders , 4 steps
chemin_fichier = __file__                            # ex. app.py
chemin_complet = os.path.abspath(chemin_fichier)     # ex. C:\projet\app.py
BASE_DIR = os.path.dirname(chemin_complet)           # ex. C:\projet
OUTPUT_DIR = os.path.join(BASE_DIR, "output")        # ex. C:\projet\output


# every compression create a new folder : output/image_001, output/image_002, ...
RAW_NAME = "image.raw"                              
PNG_NAME = "image.png"                               
RLE_NAME = "image.rle"                               
RESULT_PNG_NAME = "image_decompressee.png"           


# 
def run_numbers():
    if not os.path.isdir(OUTPUT_DIR):   # verify if the output directory exists
        return []         
    numbers = []   # create a list to store the numbers of the folders
    for name in os.listdir(OUTPUT_DIR):  # listdir : give the names of the files and folders in the output directory
        if name.startswith("image_") and name[6:].isdigit():   # check if the name starts with "image_" and the rest is a number
            numbers.append(int(name[6:]))
    return sorted(numbers)  # return the sorted list of numbers


# transforme a number to an adress :  run_dir(7)  →  ".../output/image_007"
def run_dir(number):
    return os.path.join(OUTPUT_DIR, f"image_{number:03d}") 


# ---------------------------------------------------------------- mise en forme des tableaux
def sym(v):
    return "■" if v == 0 else "□"


def pname(v):
    return "noir" if v == 0 else "blanc"



# \x80\x04\xff --> 80 04 ff
def hexs(b, limit=10):
    text = " ".join(f"{x:02x}" for x in b[:limit])
    return text + (f" … (+{len(b) - limit} octets)" if len(b) > limit else "")

# rng(0, 3) --> '0-3'       rng(5, 5) --> '5'
def rng(a, b):
    return f"{a}" if a == b else f"{a}-{b}"



# create the table of the compression and decompression steps

def compression_rows(w, h, steps):
    rows = [("—", "—", "En-tête", f"largeur {w}, hauteur {h}", hexs(write_header(w, h)))]  # entete line 
    for k, ev in enumerate(steps, 1):
        pos = rng(ev["start"], ev["start"] + ev["count"] - 1)
        if ev["type"] == "rep":
            rows.append((k, pos, "Répétition (bit fort = 1)",
                         f"{sym(ev['color'])} × {ev['count']}  ({pname(ev['color'])})", hexs(ev["bytes"])))
        else:
            shown = " ".join(sym(p) for p in ev["pixels"][:16]) + (" …" if ev["count"] > 16 else "")
            rows.append((k, pos, "Suite de pixels différents (bit fort = 0)", shown, hexs(ev["bytes"])))
    return rows


def decompression_rows(w, h, steps):
    rows = [("—", rng(0, HEADER_SIZE - 1), hexs(write_header(w, h)),
             f"En-tête : largeur {w}, hauteur {h}", "—")]
    for k, ev in enumerate(steps, 1):
        off = HEADER_SIZE + ev["offset"]
        lus = rng(off, off + ev["length"] - 1)
        mot = f"{ev['word'] >> 8:02x} {ev['word'] & 255:02x}"
        ps, pe = ev["pixel_start"], ev["pixel_start"] + ev["count"] - 1
        if ev["type"] == "rep":
            rows.append((k, lus, mot, f"bit fort = 1 → répétition de {ev['count']}, couleur {ev['color']:02x}",
                         f"{ev['count']} × {sym(ev['color'])}  (pixels {rng(ps, pe)})"))
        else:
            shown = " ".join(sym(p) for p in ev["raw"][:16]) + (" …" if ev["count"] > 16 else "")
            rows.append((k, lus, mot, f"bit fort = 0 → suite de {ev['count']} pixels",
                         f"{shown}  (pixels {rng(ps, pe)})"))
    return rows


def photo_data(width, height, pixels):
    colors = {0: "#000000", 255: "#ffffff"}
    rows = []
    for l in range(height):
        row = pixels[l * width:(l + 1) * width]
        rows.append("{" + " ".join(colors.get(p, "#808080") for p in row) + "}")
    return " ".join(rows)


def make_table(parent, columns):
    frame = tk.Frame(parent)
    frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", height=6)
    for cid, title, width in columns:
        tree.heading(cid, text=title)
        tree.column(cid, width=width, anchor="w")
    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return tree


def fill_table(tree, rows):
    tree.delete(*tree.get_children())
    for r in rows:
        tree.insert("", "end", values=r)


# ---------------------------------------------------------------- application
class DrawingApp:
    def __init__(self, root):
        self.root = root         # the main window
        root.title("Codec RLE - images binaires")  #the windeow title

        self.width = 0           # n : number of columns
        self.height = 0          # m : number of rows
        self.cell = 10           # size of a cell in pixels on the screen
        self.grid = []           # donnees : grid[ligne][colonne] = 0 or 255
        self.rects = []          # rects[ligne][colonne] = rectangle object on the canvas
        self.result_img = None   # stock a reference, otherwise the image is garbage collected and disappears from the canvas

        # --- top bar : dimensions + 4 buttons ---

        top = tk.Frame(root)             # create a frame for the top bar
        top.pack(padx=10, pady=(10, 0))  # pack the frame with padding


        tk.Label(top, text="Largeur (n) :").pack(side="left")   # create a label for the width
        self.entry_w = tk.Entry(top, width=5)                   # create an entry for the width
        self.entry_w.insert(0, "32")                            # insert the default value 32
        self.entry_w.pack(side="left", padx=(2, 10))            # pack the entry with padding

        tk.Label(top, text="Hauteur (m) :").pack(side="left")   # create a label for the height
        self.entry_h = tk.Entry(top, width=5)                   # create an entry for the height
        self.entry_h.insert(0, "32")                            # insert the default value 32
        self.entry_h.pack(side="left", padx=(2, 12))            # pack the entry with padding

        # --- buttons ---
        tk.Button(top, text="Créer la grille", command=self.create_grid).pack(side="left", padx=3)
        tk.Button(top, text="Effacer", command=self.clear).pack(side="left", padx=3)
        tk.Button(top, text="Compresser", command=self.compress).pack(side="left", padx=(16, 3))
        tk.Button(top, text="Décompresser", command=self.decompress).pack(side="left", padx=3)

        # --- both images --
        views = tk.Frame(root)         # pack the frame with padding
        views.pack(padx=10, pady=8)    
        left = tk.Frame(views)          # left frame for the drawn image
        left.pack(side="left", padx=12, anchor="n")   # pack the left frame with padding and anchor to the north
        tk.Label(left, text="Image dessinée").pack()  # create a label for the drawn image

        self.canvas = tk.Canvas(left, bg="white")     # create a canvas for the drawn image
        self.canvas.pack()                            # pack the canvas
        self.canvas.bind("<Button-1>",  lambda e: self.paint(e, BLACK))  # bind the left mouse button to paint black
        self.canvas.bind("<B1-Motion>", lambda e: self.paint(e, BLACK))  # bind the left mouse button motion to paint black
        self.canvas.bind("<Button-3>",  lambda e: self.paint(e, WHITE))  # bind the right mouse button to paint white
        self.canvas.bind("<B3-Motion>", lambda e: self.paint(e, WHITE))  # bind the right mouse button motion to paint white

        right = tk.Frame(views)
        right.pack(side="left", padx=12, anchor="n")
        tk.Label(right, text="Image décompressée").pack()
        self.result_canvas = tk.Canvas(right, bg="#eeeeee", width=150, height=150)
        self.result_canvas.pack()
        self.result_label = tk.Label(right, text="")
        self.result_label.pack()

        # --- infos ---
        self.stats_label = tk.Label(root, text="", font=("Helvetica", 10, "bold"))
        self.stats_label.pack()
        self.files_label = tk.Label(root, text="", fg="gray")
        self.files_label.pack(pady=(0, 6))

        # --- etapes detaillees : un tableau par operation ---
        tabs = ttk.Notebook(root)
        tabs.pack(padx=10, pady=(0, 10), fill="both", expand=True)
        tab_c, tab_d = tk.Frame(tabs), tk.Frame(tabs)
        tabs.add(tab_c, text="Étapes de la compression")
        tabs.add(tab_d, text="Étapes de la décompression")
        self.table_c = make_table(tab_c, [("n", "N°", 40), ("pixels", "Pixels", 90),
                                          ("type", "Type de bloc", 250), ("contenu", "Contenu", 230),
                                          ("octets", "Octets écrits", 230)])
        self.table_d = make_table(tab_d, [("n", "N°", 40), ("lus", "Octets lus", 80), ("mot", "Mot", 110),
                                          ("sens", "Lecture du mot", 300), ("prod", "Pixels produits", 270)])
        self.tabs = tabs

        self.create_grid()

    # ------------------------------------------------------------------ dessin
    def create_grid(self):
        """Lit n et m dans les champs, verifie, puis (re)construit la grille."""
        try:
            w = int(self.entry_w.get())
            h = int(self.entry_h.get())
        except ValueError:
            messagebox.showerror("Erreur", "La largeur et la hauteur doivent être des nombres entiers.")
            return
        if not (1 <= w <= MAX_DIM and 1 <= h <= MAX_DIM):
            messagebox.showerror("Erreur", f"La largeur et la hauteur doivent être entre 1 et {MAX_DIM}.")
            return

        self.width, self.height = w, h
        self.cell = max(2, min(20, CANVAS_MAX // max(w, h)))
        self.canvas.delete("all")
        self.canvas.config(width=w * self.cell, height=h * self.cell)
        self.grid = [[WHITE] * w for _ in range(h)]
        self.rects = [[self.canvas.create_rectangle(c * self.cell, l * self.cell,
                                                    (c + 1) * self.cell, (l + 1) * self.cell,
                                                    fill="white", outline="lightgray")
                       for c in range(w)] for l in range(h)]


    def clear(self):
        for l in range(self.height):
            for c in range(self.width):
                self.grid[l][c] = WHITE
                self.canvas.itemconfig(self.rects[l][c], fill="white")

        # on efface aussi l'image décompressée affichée à droite
        self.result_canvas.delete("all")                       # enlève l'image du canvas
        self.result_canvas.config(width=150, height=150)       # taille de départ
        self.result_img = None                                 # libère l'image en mémoire
        self.result_label.config(text="", fg="black")          # enlève le message ✔ / ✘

        # on efface aussi les infos et les tableaux d'étapes
        self.stats_label.config(text="")                       # taille, taux, gain
        self.files_label.config(text="")                       # dossier / fichier chargé
        fill_table(self.table_c, [])                           # tableau de compression vide
        fill_table(self.table_d, [])                           # tableau de décompression vide


    def paint(self, event, value):
        c = event.x // self.cell
        l = event.y // self.cell
        if 0 <= c < self.width and 0 <= l < self.height:
            self.grid[l][c] = value
            self.canvas.itemconfig(self.rects[l][c], fill="black" if value == BLACK else "white")


    # aplatit la grille : ligne 1, puis ligne 2, etc.
    def get_pixels(self):
        return [p for row in self.grid for p in row]

    # ------------------------------------------------------------------ export PNG (OpenCV)

    #save the image as a PNG file using OpenCV.
    def export_png(self, path, width, height, pixels):
        try:
            import cv2
            import numpy as np
        except ImportError:
            return False
        img = np.array(pixels, dtype=np.uint8).reshape(height, width)
        ok, buf = cv2.imencode(".png", img)
        if ok:
            buf.tofile(path)
        return ok

    

    # ------------------------------------------------------------------ actions

    # save the image, compress it and write the .rle file (automatic paths).
    def compress(self):
        w, h = self.width, self.height
        pixels = self.get_pixels()
        steps = []
        numbers = run_numbers()                        #ex. [1, 2]               
        number = (numbers[-1] if numbers else 0) + 1   # numbers[-1] = 2 → 2 + 1 = 3   
        folder = run_dir(number)                       # ".../output/image_003" (only texte)
        try:
            os.makedirs(folder)                           # create output/ and image_00N if needed
            raw_size = save_raw(os.path.join(folder, RAW_NAME), w, h, pixels)
            png_ok = self.export_png(os.path.join(folder, PNG_NAME), w, h, pixels)
            rle_size = save_rle(os.path.join(folder, RLE_NAME), w, h, pixels, steps=steps)
        except OSError as e:
            messagebox.showerror("Erreur", f"Impossible d'écrire les fichiers : {e}")
            return

        fill_table(self.table_c, compression_rows(w, h, steps))
        self.tabs.select(0)
        taux = 1 - rle_size / raw_size     # taux de compression (cours) : 1 - final / initial
        gain = taux * 100                  # gain = le même taux, en pourcentage
        self.stats_label.config(
            text=f"Image brute : {raw_size} octets   |   Fichier compressé : {rle_size} octets   |   "
                 f"Taux : {taux:.2f}   |   Gain : {gain:.1f} %")
        self.files_label.config(
            text=f"Enregistré dans output/image_{number:03d} : image.raw, image.rle"
                 + (", image.png" if png_ok else "  (OpenCV absent : PNG non créé)"))


    # decompress the RLE file and display the resulting image
    def decompress(self):
        numbers = run_numbers()               # ex. [1, 2, 3]
        if not numbers:
            messagebox.showinfo("Info", "Compressez d'abord une image.")
            return
        folder = run_dir(numbers[-1])                     # the last folder created : ".../output/image_003"
        rle_path = os.path.join(folder, RLE_NAME)         # the path of the RLE file : ".../output/image_003/image.rle"
        if not os.path.exists(rle_path):
            messagebox.showinfo("Info", "Compressez d'abord une image.")
            return
        steps = []
        try:
            w, h, payload = read_rle_file(rle_path)
            pixels = decode(payload, steps=steps)
            if len(pixels) != w * h:
                raise ValueError(f"{len(pixels)} pixels obtenus, {w} x {h} = {w * h} attendus")
        except (struct.error, IndexError):
            messagebox.showerror("Erreur", "Fichier corrompu : les données compressées sont tronquées.")
            return
        except (OSError, ValueError) as e:
            messagebox.showerror("Erreur", f"Fichier invalide : {e}")
            return

        fill_table(self.table_d, decompression_rows(w, h, steps))
        self.tabs.select(1)
        self.show_image(w, h, pixels)
        self.files_label.config(text=f"Fichier chargé : image_{numbers[-1]:03d}/image.rle ({w} x {h}, {HEADER_SIZE + len(payload)} octets)")

        if (w, h) == (self.width, self.height):
            if pixels == self.get_pixels():
                self.result_label.config(text="✔ Identique à l'image dessinée", fg="green")
            else:
                self.result_label.config(text="✘ Différente du dessin actuel", fg="red")
        else:
            self.result_label.config(text="", fg="black")
        self.export_png(os.path.join(folder, RESULT_PNG_NAME), w, h, pixels)



    def show_image(self, w, h, pixels):
        img = tk.PhotoImage(master=self.root, width=w, height=h)
        img.put(photo_data(w, h, pixels))
        biggest = max(w, h)
        if biggest > CANVAS_MAX:
            s = -(-biggest // CANVAS_MAX)                  # arrondi au-dessus : affichage reduit
            img = img.subsample(s, s)
        else:
            z = max(1, min(20, CANVAS_MAX // biggest))
            if z > 1:
                img = img.zoom(z, z)
        self.result_img = img
        self.result_canvas.delete("all")
        self.result_canvas.config(width=img.width(), height=img.height())
        self.result_canvas.create_image(0, 0, image=img, anchor="nw")


# main loop : create the window and run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = DrawingApp(root)
    root.mainloop()