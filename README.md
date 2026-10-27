# surfer-mcp

Serveur [MCP](https://modelcontextprotocol.io) local qui connecte **Claude** (Claude Desktop ou Claude Code) à **Golden Software Surfer 13+** sous Windows.

Il permet à Claude de piloter Surfer : interpoler des données XYZ en grille, produire des cartes structurales, tracer des **coupes géologiques**, générer des vues 3D et exporter les résultats en PNG, JPG, PDF, TIF, SVG ou EMF.

> Testé avec Surfer **13.06.618** et Python 3.14 sous Windows 10/11.

## Fonctionnalités

- **Grille** : interpolation de points XYZ (kriging, IDW, courbure minimale, plus proche voisin, triangulation…)
- **Carte structurale** : raster coloré + lignes de contours superposées
- **Coupe géologique** : profil le long d'une ligne A–A′, avec carte de localisation, axes, titre et exagération verticale
- **Vue 3D** : surface à partir d'une grille
- **Exports** : PNG, JPG, PDF vectoriel, TIF, SVG, EMF, et fichiers de projet `.srf`
- **Gestion des documents** : liste, export, sauvegarde et fermeture des documents ouverts dans Surfer

## Prérequis

- Windows 10 ou 11
- Golden Software **Surfer 13 ou plus récent**, installé et licencié (l'interface COM `Surfer.Application` doit être disponible)
- **Python 3.10+** (64 bits)

## Installation

```powershell
git clone https://github.com/VOTRE_COMPTE/surfer-mcp.git
cd surfer-mcp

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

Vérification rapide :

```powershell
python -c "import surfer_mcp; print('ok')"
```

## Configuration de Claude Desktop

1. Ouvrez (ou créez) le fichier `%APPDATA%\Claude\claude_desktop_config.json`.
2. Ajoutez le serveur en adaptant les chemins :

```json
{
  "mcpServers": {
    "surfer": {
      "command": "C:\\Users\\VOTRE_NOM\\surfer-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "surfer_mcp"],
      "env": {
        "SURFER_MCP_WORKSPACE": "C:\\Users\\VOTRE_NOM\\Documents\\SurferMCP",
        "SURFER_MCP_VISIBLE": "1"
      }
    }
  }
}
```

3. Redémarrez Claude Desktop. Le serveur `surfer` doit apparaître dans la liste des outils (icône MCP).

Un modèle est fourni : [`claude_desktop_config.example.json`](claude_desktop_config.example.json).

## Configuration de Claude Code

```powershell
claude mcp add surfer -e SURFER_MCP_WORKSPACE="C:\Users\VOTRE_NOM\Documents\SurferMCP" -- "C:\Users\VOTRE_NOM\surfer-mcp\.venv\Scripts\python.exe" -m surfer_mcp
```

Puis vérifiez avec `/mcp` dans Claude Code.

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `SURFER_MCP_WORKSPACE` | `%USERPROFILE%\Documents\SurferMCP` (ou `~/SurferMCP`) | Dossier de travail : les chemins relatifs des outils y sont résolus. |
| `SURFER_MCP_VISIBLE` | `1` | `1` affiche Surfer, `0` le lance en arrière-plan. |

Surfer est démarré automatiquement au premier appel d'outil. Le serveur ne ferme **jamais** une instance de Surfer qu'il n'a pas lancée.

## Démarrage rapide

Le dépôt contient un jeu de données synthétique : [`examples/sample_points.csv`](examples/sample_points.csv) (X 0–5000 m, Y 0–4000 m, Z en mètres, séparé par virgules avec en-tête).

Exemples de demandes à Claude :

> Crée une grille par kriging (300 × 300) à partir de `examples/sample_points.csv`, puis une carte colorée intitulée « Carte structurale » et exporte-la dans `output/carte.png`.

> Trace la coupe A–A′ de (500, 500) à (4500, 3200) sur `grids/sample_points.grd`, avec une exagération verticale de 2.5. Exporte l'image dans `output/coupe.png` et les données dans `output/coupe.dat`.

> Fais une vue 3D de la grille et exporte `output/surface.png`.

> Liste les documents ouverts, exporte le premier en PDF, puis ferme-le.

Après exécution, les fichiers générés se trouvent dans `%USERPROFILE%\Documents\SurferMCP` (ou dans le dossier défini par `SURFER_MCP_WORKSPACE`).

## Outils MCP

| Outil | Description |
|---|---|
| `surfer_status` | Version de Surfer, état, visibilité, dossier de travail, nombre de documents. |
| `list_documents` | Liste des documents ouverts (index, nom, chemin, état de sauvegarde). |
| `set_surfer_visible` | Affiche ou masque la fenêtre Surfer. |
| `create_grid` | Interpole un fichier XYZ en grille `.grd`. |
| `create_contour_map` | Crée une carte (colorée, contours seuls ou contours remplis). |
| `create_cross_section` | Crée une coupe géologique le long d'une ligne droite. |
| `create_surface_map` | Crée une vue 3D de la grille. |
| `export_document` | Exporte un document ouvert (format déduit de l'extension). |
| `save_plot` | Enregistre un document en `.srf`. |
| `close_document` | Ferme un document, avec sauvegarde optionnelle. |

### Paramètres utiles

- **Colonnes** : indices **à partir de 1** (`x_col=1`, `y_col=2`, `z_col=3`).
- **Algorithmes de grille** : `kriging` (défaut), `idw`, `min_curvature`, `shepards`, `natural_neighbor`, `nearest_neighbor`, `regression`, `radial_basis`, `triangulation`, `moving_average`, `data_metrics`, `local_polynomial`.
- **Styles de carte** :
  - `color` (recommandé) : raster coloré + lignes de contours ;
  - `lines` : contours noirs uniquement ;
  - `filled` : contours remplis — Surfer 13 les rend en niveaux de gris.
- **Formats d'export** : `.png`, `.jpg`, `.pdf`, `.tif`, `.svg`, `.emf`.

## Format des données

- Fichiers `.csv`, `.txt`, `.tsv`, `.dat`, `.xyz`.
- Séparateur détecté automatiquement : virgule, point-virgule, tabulation ou espace.
- Ligne d'en-tête facultative, lignes non numériques ignorées, commentaires `#` ignorés.
- Au moins **4 points** numériques.
- Les coordonnées sont exprimées dans les **unités cartographiques** de votre projet ; les libellés d'axes par défaut sont `Distance (m)` et `Elevation (m)`.

## Chemins de fichiers

- Les chemins relatifs sont résolus dans `SURFER_MCP_WORKSPACE`.
- Les chemins absolus sont acceptés.
- Les dossiers de sortie sont créés automatiquement **à l'intérieur** du dossier de travail ; hors de ce dossier, le dossier parent doit déjà exister.

## Dépannage

| Symptôme | Cause probable / solution |
|---|---|
| `pywin32 is required…` | `pip install pywin32` dans l'environnement virtuel. |
| `ActiveX component can't create object` | Surfer n'est pas installé, non licencié, ou son interface COM n'est pas enregistrée. Lancez Surfer une fois manuellement. |
| `Insufficient data in worksheet` | Moins de 4 lignes numériques, mauvais séparateur ou colonnes mal indiquées. |
| Carte remplie en gris | Comportement de Surfer 13 pour `style="filled"` ; utilisez `style="color"`. |
| Accès refusé à l'écriture | Choisissez un dossier accessible dans `SURFER_MCP_WORKSPACE`. |
| Le serveur ne démarre pas dans Claude | Vérifiez le chemin de `python.exe` dans la configuration et redémarrez Claude Desktop. |

## Limites connues

- Windows uniquement (automatisation COM).
- Coupes le long d'une **ligne droite** uniquement dans cette version.
- Une seule opération Surfer à la fois (les appels sont sérialisés).
- Après `SaveAs`, Surfer renomme le document : les outils renvoient le nom final.
- Le serveur ne ferme pas les documents que vous avez ouverts vous-même.

## Développement et tests

```powershell
pip install -e ".[dev]"
pytest -q

# Tests d'intégration réels (lance Surfer)
$env:SURFER_MCP_TEST_COM = "1"
pytest -q
```

Structure :

```
src/surfer_mcp/surfer.py   # session COM, grille, cartes, coupes, exports
src/surfer_mcp/server.py   # outils MCP
tests/                     # tests unitaires et d'intégration (Surfer + stdio MCP)
examples/                  # jeu de données de démonstration
```

## Licence

MIT — voir [LICENSE](LICENSE).
