import tkinter as tk

N, M = 32, 32            # largeur (colonnes), hauteur (lignes) de l'image
CELL = 14                # taille d'une case a l'ecran, en pixels

BLACK, WHITE = 0, 255    # valeurs des pixels (comme dans le codec)

root = tk.Tk()
root.title("Codec RLE - dessin")

canvas = tk.Canvas(root, width=N * CELL, height=M * CELL, bg="white")
canvas.pack(padx=10, pady=10)

# 1) les DONNEES : grid[ligne][colonne], tout blanc au depart
grid = [[WHITE] * N for _ in range(M)]

# 2) l'AFFICHAGE : un rectangle par case, on garde son identifiant dans rects
rects = [[canvas.create_rectangle(c * CELL, l * CELL, (c + 1) * CELL, (l + 1) * CELL,
                                  fill="white", outline="lightgray")
          for c in range(N)] for l in range(M)]


def paint(event, value):
    c = event.x // CELL              # colonne de la case cliquee
    l = event.y // CELL              # ligne de la case cliquee
    if 0 <= c < N and 0 <= l < M:    # ignorer si la souris sort de la grille
        grid[l][c] = value                                    # met a jour les donnees
        canvas.itemconfig(rects[l][c],
                          fill="black" if value == BLACK else "white")  # et l'affichage


canvas.bind("<Button-1>",  lambda e: paint(e, BLACK))   # clic gauche
canvas.bind("<B1-Motion>", lambda e: paint(e, BLACK))   # clic gauche maintenu + deplacement
canvas.bind("<Button-3>",  lambda e: paint(e, WHITE))   # clic droit
canvas.bind("<B3-Motion>", lambda e: paint(e, WHITE))   # clic droit maintenu + deplacement

if __name__ == "__main__":
    root.mainloop()