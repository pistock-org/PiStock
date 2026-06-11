# Plugins PiStock

Un plugin est un dossier ici-même qui ajoute des fonctionnalités à PiStock sans toucher au noyau. Le serveur scanne ce dossier au démarrage et charge automatiquement chaque plugin valide.

## Structure minimale d'un plugin

```
plugins/
└── mon_plugin/
    ├── manifest.json    (métadonnées)
    └── plugin.py        (code, expose register(app))
```

### `manifest.json`

```json
{
  "id": "mon_plugin",
  "name": "Mon Plugin",
  "version": "0.1.0",
  "author": "Toi",
  "description": "Ce que fait ce plugin, en une phrase.",
  "icon": "🧩"
}
```

Champs obligatoires : `id`, `name`, `version`. Les autres sont optionnels.

L'`id` doit matcher le nom du dossier (convention). Il sert aussi à préfixer les routes : `/plugin/<id>`.

### `plugin.py`

```python
def register(app):
    """Appelé une fois au démarrage par le noyau.
    'app' est l'instance FastAPI."""
    from nicegui import ui

    @ui.page("/plugin/mon_plugin")
    def ma_page():
        # Construire l'UI ici (NiceGUI complet à disposition)
        ui.label("Hello from mon_plugin!")
```

## Contrat moral

Un plugin peut **lire** librement la base de données du noyau (tables `parts`, `bom`, `bom_line`, `stock`, `project`, `plm`).

Un plugin ne doit **écrire** que dans ses propres tables, préfixées `plugin_<id>_*`. S'il veut modifier le stock ou les BOMs, il doit passer par les endpoints REST du noyau ou les helpers Python (`main.bom_stock_apply`, etc.) — pour bénéficier des validations, des logs, et de la cohérence transactionnelle.

## Points d'extension de l'UI

En plus de ses propres pages, un plugin peut contribuer à des « slots »
prévus par le cœur, sans toucher au code du catalogue.

### Badge en bout de ligne de pièce (catalogue)

Le catalogue (`/catalog`) réserve un emplacement d'icônes à droite de
chaque ligne de pièce. Un plugin peut y faire apparaître une petite
icône — par exemple « cette pièce possède une note de fabrication ».

Depuis `register(app)`, enregistre un *provider*. Il reçoit la liste
complète des pièces affichées (un seul appel par rafraîchissement, pour
permettre une requête groupée) et renvoie `{part_id: PartBadge}` :

```python
def register(app):
    try:
        from plugin_hooks import register_part_badge_provider, PartBadge
    except ImportError:
        return  # cœur trop ancien : le plugin marche quand même

    def provider(parts):
        ids = _parts_avec_donnee()              # 1 requête groupée
        badge = PartBadge(
            icon="sticky_note_2",               # nom d'icône Material, ou un emoji
            tooltip="A une note",
            color="text-amber-600",             # classe Tailwind
            on_click=lambda part: ui.navigate.to(f"/plugin/mon_plugin?part={part['id']}"),
        )
        return {p["id"]: badge for p in parts if p["id"] in ids}

    register_part_badge_provider(provider)
```

Un provider qui plante est loggé et ignoré : il ne casse jamais le
catalogue. Voir l'implémentation de référence dans `fab_notes`.

## Accès au noyau

Depuis `plugin.py`, tu peux importer :
- `import main` : modèles SQLModel et helpers du serveur (`main.engine`, `main.Bom`, `main._flatten_bom`...)
- `from sqlmodel import Session, select` : pour les requêtes SQL
- `from nicegui import ui` : pour l'UI

## Robustesse

Un plugin qui plante au chargement ou au rendu est loggé mais **ne casse pas le reste du serveur**. Les autres plugins continuent à fonctionner.

## Désactivation

Pour désactiver un plugin, soit tu retires son dossier, soit tu le renommes avec un underscore ou un point devant (`_mon_plugin`, `.mon_plugin`) — ces dossiers sont ignorés par le scanner.
