import os
import struct
import tkinter as tk
from tkinter import messagebox, ttk

from rle_codec import HEADER_SIZE, decode, read_rle_file, save_raw, save_rle, write_header

BLACK, WHITE = 0, 255
MAX_DIM = 128            # taille max choisie dans l'interface
CANVAS_MAX = 320         # taille maximale d'une zone d'image, en pixels ecran

# Les fichiers sont enregistres automatiquement dans le dossier "output", a cote du programme
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
RAW_PATH = os.path.join(OUTPUT_DIR, "image.raw")                  # image non compressee
PNG_PATH = os.path.join(OUTPUT_DIR, "image.png")                  # meme image, en PNG (OpenCV)
RLE_PATH = os.path.join(OUTPUT_DIR, "image.rle")                  # image compressee
RESULT_PNG_PATH = os.path.join(OUTPUT_DIR, "image_decompressee.png")


# ---------------------------------------------------------------- mise en forme des tableaux

#function to return a symbol for a pixel value (0 or 255)
def sym(v):
    return "■" if v == 0 else "□"

# function to return a name for a pixel value (0 or 255)
def pname(v):
    return "noir" if v == 0 else "blanc"

#funtion 
def hexs(b, limit=10):
    text = " ".join(f"{x:02x}" for x in b[:limit])
    return text + (f" … (+{len(b) - limit} octets)" if len(b) > limit else "")

#fucntion to return a string representation of a range of numbers
def rng(a, b):
    return f"{a}" if a == b else f"{a}-{b}"


def compression_rows(w, h, steps):
    """Une ligne par bloc ecrit : (n, pixels, type, contenu, octets ecrits)."""
    rows = [("—", "—", "En-tête", f"largeur {w}, hauteur {h}", hexs(write_header(w, h)))]
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
    """Une ligne par bloc lu : (n, octets lus, mot, lecture du mot, pixels produits)."""
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


#function 
def photo_data(width, height, pixels):
    """Texte attendu par PhotoImage.put : une accolade par ligne, une couleur par pixel."""
    colors = {0: "#000000", 255: "#ffffff"}
    rows = []
    for l in range(height):
        row = pixels[l * width:(l + 1) * width]
        rows.append("{" + " ".join(colors.get(p, "#808080") for p in row) + "}")
    return " ".join(rows)


#function to create the table
def make_table(parent, columns):
    """columns = [(id, titre, largeur), ...]. Retourne le tableau (Treeview) avec sa barre de defilement."""
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


#function to fill the table with rows
def fill_table(tree, rows):
    tree.delete(*tree.get_children())
    for r in rows:
        tree.insert("", "end", values=r)


# ---------------------------------------------------------------- application
class DrawingApp:
    def __init__(self, root):
        self.root = root
        root.title("Codec RLE - images binaires")

        self.width = 0           # n : nombre de colonnes
        self.height = 0          # m : nombre de lignes
        self.cell = 10           # taille d'une case a l'ecran
        self.grid = []           # donnees : grid[ligne][colonne] = 0 ou 255
        self.rects = []          # affichage : identifiants des rectangles
        self.result_img = None   # garder une reference, sinon l'image disparait

        # --- barre du haut : dimensions + 4 boutons ---
        top = tk.Frame(root)
        top.pack(padx=10, pady=(10, 0))
        tk.Label(top, text="Largeur (n) :").pack(side="left")
        self.entry_w = tk.Entry(top, width=5)
        self.entry_w.insert(0, "32")
        self.entry_w.pack(side="left", padx=(2, 10))
        tk.Label(top, text="Hauteur (m) :").pack(side="left")
        self.entry_h = tk.Entry(top, width=5)
        self.entry_h.insert(0, "32")
        self.entry_h.pack(side="left", padx=(2, 12))
        tk.Button(top, text="Créer la grille", command=self.create_grid).pack(side="left", padx=3)
        tk.Button(top, text="Effacer", command=self.clear).pack(side="left", padx=3)
        tk.Button(top, text="Compresser", command=self.compress).pack(side="left", padx=(16, 3))
        tk.Button(top, text="Décompresser", command=self.decompress).pack(side="left", padx=3)

        # --- les deux images ---
        views = tk.Frame(root)
        views.pack(padx=10, pady=8)
        left = tk.Frame(views)
        left.pack(side="left", padx=12, anchor="n")
        tk.Label(left, text="Image dessinée").pack()
        self.canvas = tk.Canvas(left, bg="white")
        self.canvas.pack()
        self.canvas.bind("<Button-1>",  lambda e: self.paint(e, BLACK))
        self.canvas.bind("<B1-Motion>", lambda e: self.paint(e, BLACK))
        self.canvas.bind("<Button-3>",  lambda e: self.paint(e, WHITE))
        self.canvas.bind("<B3-Motion>", lambda e: self.paint(e, WHITE))

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

    def paint(self, event, value):
        c = event.x // self.cell
        l = event.y // self.cell
        if 0 <= c < self.width and 0 <= l < self.height:
            self.grid[l][c] = value
            self.canvas.itemconfig(self.rects[l][c], fill="black" if value == BLACK else "white")

    def get_pixels(self):
        """Aplatit la grille : ligne 1, puis ligne 2, etc."""
        return [p for row in self.grid for p in row]

    # ------------------------------------------------------------------ export PNG (OpenCV)
    def export_png(self, path, width, height, pixels):
        """Enregistre l'image en PNG avec OpenCV. Retourne False si OpenCV n'est pas installe."""
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
    def compress(self):
        """Sauvegarde l'image, la compresse et ecrit le fichier .rle (chemins automatiques)."""
        w, h = self.width, self.height
        pixels = self.get_pixels()
        steps = []
        try:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            raw_size = save_raw(RAW_PATH, w, h, pixels)
            png_ok = self.export_png(PNG_PATH, w, h, pixels)
            rle_size = save_rle(RLE_PATH, w, h, pixels, steps=steps)
        except OSError as e:
            messagebox.showerror("Erreur", f"Impossible d'écrire les fichiers : {e}")
            return

        fill_table(self.table_c, compression_rows(w, h, steps))
        self.tabs.select(0)
        gain = (1 - rle_size / raw_size) * 100
        self.stats_label.config(
            text=f"Image brute : {raw_size} octets   |   Fichier compressé : {rle_size} octets   |   "
                 f"Taux : {raw_size / rle_size:.2f} : 1   |   Gain : {gain:.1f} %")
        self.files_label.config(
            text=f"Enregistré dans le dossier « output » : image.raw, image.rle"
                 + (", image.png" if png_ok else "  (OpenCV absent : PNG non créé)"))

    def decompress(self):
        """Charge le fichier .rle, le decompresse et affiche l'image resultat."""
        if not os.path.exists(RLE_PATH):
            messagebox.showinfo("Info", "Compressez d'abord une image.")
            return
        steps = []
        try:
            w, h, payload = read_rle_file(RLE_PATH)
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
        self.files_label.config(text=f"Fichier chargé : image.rle ({w} x {h}, {HEADER_SIZE + len(payload)} octets)")

        if (w, h) == (self.width, self.height):
            if pixels == self.get_pixels():
                self.result_label.config(text="✔ Identique à l'image dessinée", fg="green")
            else:
                self.result_label.config(text="✘ Différente du dessin actuel", fg="red")
        else:
            self.result_label.config(text="", fg="black")
        self.export_png(RESULT_PNG_PATH, w, h, pixels)

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


if __name__ == "__main__":
    root = tk.Tk()
    app = DrawingApp(root)
    root.mainloop()