"""Educational text and local HTML guide for LiDAR Cave Scan."""

from __future__ import annotations

import html
from pathlib import Path

SCIENCE_SECTIONS = [
    {
        "title": "Ce que fait l'outil",
        "body": (
            "LiDAR Cave Scan lit un MNT, c'est-a-dire un modele numerique du terrain nu. "
            "Il cherche les cuvettes fermees visibles en surface, les mesure, puis les classe "
            "pour t'aider a choisir quoi verifier dans QGIS, Geoportail ou sur le terrain."
        ),
    },
    {
        "title": "Ce que l'outil ne fait pas",
        "body": (
            "Il ne detecte pas directement une grotte, ne voit pas sous terre et ne donne pas "
            "une probabilite geologique. Une depression peut etre une doline, une mare, une "
            "ancienne carriere, un terrassement, une erreur du MNT ou un simple effet de bord."
        ),
    },
    {
        "title": "LiDAR",
        "body": (
            "Le LiDAR mesure des distances avec un laser depuis un avion, un drone ou un scanner. "
            "Apres traitement, on peut obtenir un MNT qui represente le sol. C'est tres utile pour "
            "voir des formes de surface meme sous vegetation clairsemee."
        ),
    },
    {
        "title": "MNT",
        "body": (
            "Un MNT est une grille d'altitudes. Chaque pixel contient une hauteur. L'outil compare "
            "la forme locale du terrain avec une surface 'remplie' pour estimer profondeur, surface "
            "et volume des cuvettes."
        ),
    },
    {
        "title": "Score et classes",
        "body": (
            "Le score combine profondeur, surface, volume et compacite. A signifie 'a regarder en "
            "premier', B 'interessant', C 'controle rapide', D 'faible signal'. Ce n'est pas une "
            "probabilite de grotte."
        ),
    },
    {
        "title": "Singularites terrain",
        "body": (
            "Une singularite est une forme locale qui s'ecarte de la tendance du terrain autour "
            "d'elle: petit creux, bosse, rupture, texture rugueuse ou artefact. L'outil calcule un "
            "residu local et un score z robuste pour remonter ces zones. C'est volontairement plus "
            "audacieux que la detection de cuvettes fermees, donc il faut s'attendre a plus de faux "
            "positifs."
        ),
    },
    {
        "title": "Carte interactive",
        "body": (
            "interactive_map.html est la carte a utiliser pour se situer. Elle permet de zoomer, "
            "cliquer sur les candidats, lire latitude/longitude et ouvrir le point dans Google Maps "
            "ou OpenStreetMap."
        ),
    },
    {
        "title": "SAR",
        "body": (
            "Le SAR est un radar imageur satellitaire ou aerien. Il envoie des ondes radio et mesure "
            "le signal retourne. Il peut servir a suivre des deformations de surface, mais les images "
            "publiques standards ne sont pas une camera a cavites."
        ),
    },
    {
        "title": "Doppler et micro-Doppler",
        "body": (
            "L'effet Doppler est le changement apparent de frequence quand une cible bouge par rapport "
            "au capteur. Le micro-Doppler cherche de petites vibrations dans un signal radar coherent. "
            "Dans ce projet, le module micro-Doppler est un banc d'essai experimental sur donnees "
            "preparees ou synthetiques."
        ),
    },
    {
        "title": "Etudes citees",
        "body": (
            "Des travaux recents montrent que des methodes SAR avancees peuvent mesurer certaines "
            "vibrations de structures visibles en surface, comme ponts, batiments ou infrastructures, "
            "dans des conditions controlees et avec des donnees adaptees. Cela ne valide pas une "
            "detection automatique de cavites souterraines."
        ),
    },
]

STUDIES = [
    {
        "label": "Costantini et al., 2026 - Advanced Micro-Doppler SAR",
        "url": "https://doi.org/10.1016/j.prostr.2026.06.110",
        "note": "Article Procedia Structural Integrity sur le suivi de vibrations de batiments et infrastructures par analyse micro-Doppler SAR avancee.",
    },
    {
        "label": "Lotti et al., 2025/2026 - Bridge vibrations via spaceborne SAR micro-Doppler",
        "url": "https://strathprints.strath.ac.uk/",
        "note": "Travail sur la mesure de vibrations de ponts par SAR spatial, avec resolution frequentielle annoncee autour de 0,06 Hz sur une acquisition courte.",
    },
    {
        "label": "Vattulainen et al., 2026 - metrologie SAR micro-motion",
        "url": "https://doi.org/10.1109/ACCESS.2026.3652346",
        "note": "Evaluation metrologique de mesures de micro-mouvement SAR sur cibles controlees.",
    },
    {
        "label": "ESA EO4Society - Listening to motion from space",
        "url": "https://eo4society.esa.int/2026/02/09/listening-to-motion-from-space/",
        "note": "Article de vulgarisation ESA sur l'idee d'ecouter des mouvements/vibrations depuis l'espace avec le SAR.",
    },
]


def write_science_guide(out: Path) -> None:
    section_html = "\n".join(
        f"<section><h2>{html.escape(item['title'])}</h2><p>{html.escape(item['body'])}</p></section>"
        for item in SCIENCE_SECTIONS
    )
    studies_html = "\n".join(
        "<li>"
        f"<a href=\"{html.escape(study['url'])}\">{html.escape(study['label'])}</a>"
        f"<p>{html.escape(study['note'])}</p>"
        "</li>"
        for study in STUDIES
    )
    guide = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Comprendre LiDAR Cave Scan</title>
  <style>
    body {{ margin: 0; font-family: Segoe UI, Arial, sans-serif; color: #1b241f; background: #f4f1ea; }}
    header {{ background: #173b35; color: white; padding: 28px 34px; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 26px 24px 42px; }}
    section, .studies {{ background: white; padding: 18px 20px; margin: 14px 0; border-left: 5px solid #2c7bb6; box-shadow: 0 1px 2px rgba(0,0,0,.08); }}
    h1 {{ margin: 0; font-size: 30px; }}
    h2 {{ margin: 0 0 8px; font-size: 19px; }}
    p {{ line-height: 1.55; }}
    li {{ margin-bottom: 12px; }}
    a {{ color: #0b5a74; }}
    .warning {{ border-left-color: #d4573d; background: #fff8f4; }}
  </style>
</head>
<body>
  <header>
    <h1>Comprendre LiDAR Cave Scan</h1>
    <p>Mode d'emploi scientifique court pour lire les resultats sans se tromper de promesse.</p>
  </header>
  <main>
    {section_html}
    <section class="warning">
      <h2>Regle de lecture</h2>
      <p>Plus le score est haut, plus le candidat merite d'etre examine. Il ne faut jamais le lire comme une confirmation de grotte.</p>
    </section>
    <div class="studies">
      <h2>Sources et etudes a lire</h2>
      <ul>{studies_html}</ul>
    </div>
  </main>
</body>
</html>
"""
    (out / "science_guide.html").write_text(guide, encoding="utf-8")
