# PiStock

> A lightweight, self-hosted PLM and inventory system for **FreeCAD** — running on a Raspberry Pi, with web-based 3D visualization.

![License](https://img.shields.io/badge/license-AGPLv3-blue)
![Status](https://img.shields.io/badge/status-early%20development-orange)
![Python](https://img.shields.io/badge/python-3.10%2B-green)
![FreeCAD](https://img.shields.io/badge/FreeCAD-1.1-red)

PiStock is an open-source **Product Lifecycle Management (PLM) and inventory tracking** ecosystem built for makers, hackerspaces, and small engineering workshops. It acts as a digital bridge between your CAD models and your physical parts, running efficiently on low-power hardware like a Raspberry Pi.

The idea is simple: **stop re-ordering new parts when you already have what you need.** PiStock helps you catalog the profiles, fasteners, salvaged components, and printed parts piling up in your workshop — and actually reuse them in your projects, straight from FreeCAD.

> **⚠️ Status — early development.** PiStock works and is usable today (see the videos below), but it's young: the architecture and APIs may change in breaking ways. Issues and feedback are very welcome; pull requests are not being actively merged yet while the core stabilizes.

---

## 🎬 Overview

Short screen-capture walkthroughs introduce PiStock and show how to install it.

> 🇫🇷 **The videos are in French.** For now, turn on YouTube's auto-translated subtitles (or the auto-dubbed audio track). Not ideal, I know — this is a personal project, so it'll do for now. If PiStock gains traction, I'll do better.

<!-- TODO: wrap the "Presentation" thumbnail below in its youtu.be link once the overview video is published. -->

| Presentation | Introduction | Installation |
| --- | --- | --- |
| ![PiStock — Presentation](https://github.com/pistock-org/PiStock/raw/main/docs/images/youtube-pistock_presentation.png) | [![PiStock — Introduction](https://github.com/pistock-org/PiStock/raw/main/docs/images/youtube-intro.jpg)](https://youtu.be/7C0r99gCSrI) | [![PiStock — Installation](https://github.com/pistock-org/PiStock/raw/main/docs/images/youtube-install.jpg)](https://youtu.be/Fmihq0oUiy8) |
| **▶ Coming soon** | **[▶ Watch the introduction](https://youtu.be/7C0r99gCSrI)** | **[▶ Watch the installation guide](https://youtu.be/Fmihq0oUiy8)** |

---

## ▶️ See it in action

Export a part from FreeCAD and it shows up in the browser within seconds — with an interactive 3D viewer, no CAD software required.

<video src="https://github.com/pistock-org/PiStock/raw/main/docs/images/FreeCAD_to_WebPLM.mp4" controls muted width="100%"></video>

> If the clip above doesn't play inline, [watch the FreeCAD → Web PLM demo here](https://github.com/pistock-org/PiStock/raw/main/docs/images/FreeCAD_to_WebPLM.mp4).

---

## ✨ Features

**Working today**

- ✅ **Web dashboard** with two main views: *Projects* (parts grouped by subject) and *Catalog* (all parts, filterable).
- ✅ **FreeCAD workbench** — the *PiStock Explorer* and part exporter let you push `.FCStd` files and metadata directly to your server, and pull parts back into a working folder.
- ✅ **Browser 3D viewer** — inspect parts and assemblies in the browser via optimized `.glb` rendering, no CAD software required (great for collaborators who don't run FreeCAD).
- ✅ **Revision control** — track part versions by revision index.
- ✅ **Mobile-ready (PWA)** — the web app installs as a Progressive Web App, so you can browse and update your stock from your phone.
- ✅ **Inventory tracking** — quantity, physical location, supplier, status (`init` → `review` → `asset`), keywords, and an optional component datasheet per part.
- ✅ **Stores & projects** — organize parts into stores (e.g. mechanical stock, fasteners) and link them into projects.
- ✅ **"Ghost" links** — reference shared stock parts inside a project without duplicating them.
- ✅ **Manufacturing notes** — assembly instructions and docs attached to a part.
- ✅ **Stock search** — by name, location, supplier, quantity, etc.
- ✅ **Plugin architecture** — a modular core; ships with admin (DB export/restore), notes, manufacturing notes, and stock search plugins.
- ✅ **Access control** — access and admin passwords, so a guest on your network can't poke through your inventory.
- ✅ **BOM / nomenclatures** — basic creation from the catalog.

**Planned**

- 🚧 **Docker deployment** — one-command containerized setup.
- 🚧 **Public extension API** — a documented way to build your own extensions. Community add-ons (component pricing APIs, pick-to-light LED shelves, QR/camera stock workflows, …) will build on top of it.

> ℹ️ **On the word "project":** in PiStock a *project* is a **grouping of parts by subject**, not time-based project management. (The term is overloaded everywhere — this is what it means here.)

---

## 📸 Screenshots

<table>
  <tr>
    <td align="center" width="33%"><a href="https://github.com/pistock-org/PiStock/raw/main/docs/images/dashboard.png"><img src="https://github.com/pistock-org/PiStock/raw/main/docs/images/dashboard.png" alt="Web dashboard"></a><br><sub>Web dashboard</sub></td>
    <td align="center" width="33%"><a href="https://github.com/pistock-org/PiStock/raw/main/docs/images/catalog-collection.png"><img src="https://github.com/pistock-org/PiStock/raw/main/docs/images/catalog-collection.png" alt="Catalog"></a><br><sub>Catalog</sub></td>
    <td align="center" width="33%"><a href="https://github.com/pistock-org/PiStock/raw/main/docs/images/viewer-3D.png"><img src="https://github.com/pistock-org/PiStock/raw/main/docs/images/viewer-3D.png" alt="In-browser 3D viewer"></a><br><sub>In-browser 3D viewer</sub></td>
  </tr>
  <tr>
    <td align="center"><a href="https://github.com/pistock-org/PiStock/raw/main/docs/images/detailPart-stock.png"><img src="https://github.com/pistock-org/PiStock/raw/main/docs/images/detailPart-stock.png" alt="Part detail & stock"></a><br><sub>Part detail &amp; stock</sub></td>
    <td align="center"><a href="https://github.com/pistock-org/PiStock/raw/main/docs/images/revisions.png"><img src="https://github.com/pistock-org/PiStock/raw/main/docs/images/revisions.png" alt="Revision history"></a><br><sub>Revision history</sub></td>
    <td align="center"><a href="https://github.com/pistock-org/PiStock/raw/main/docs/images/FreeCAD-workbench.png"><img src="https://github.com/pistock-org/PiStock/raw/main/docs/images/FreeCAD-workbench.png" alt="FreeCAD workbench"></a><br><sub>FreeCAD workbench</sub></td>
  </tr>
  <tr>
    <td align="center"><a href="https://github.com/pistock-org/PiStock/raw/main/docs/images/mobile-pwa.png"><img src="https://github.com/pistock-org/PiStock/raw/main/docs/images/mobile-pwa.png" alt="Mobile PWA"></a><br><sub>Mobile (PWA)</sub></td>
    <td align="center"><a href="https://github.com/pistock-org/PiStock/raw/main/docs/images/stock-search.png"><img src="https://github.com/pistock-org/PiStock/raw/main/docs/images/stock-search.png" alt="Stock search"></a><br><sub>Stock search</sub></td>
    <td align="center"><a href="https://github.com/pistock-org/PiStock/raw/main/docs/images/plugins.png"><img src="https://github.com/pistock-org/PiStock/raw/main/docs/images/plugins.png" alt="Plugins"></a><br><sub>Plugins</sub></td>
  </tr>
</table>

---

## 🛠️ Architecture

![PiStock architecture](https://github.com/pistock-org/PiStock/raw/main/docs/images/architecture.png)

PiStock is built with strict decoupling for modularity and long-term maintainability:

1. **PiStock Core (backend)** — a lightweight async Python API (FastAPI) over a local SQLite/PostgreSQL database, handling file storage, version history, and item states.
2. **PiStock Web (frontend)** — a responsive interface (NiceGUI) hosting the inventory dashboard and an embedded WebGL viewer (optimized `.glb`). Installable as a Progressive Web App (PWA) for mobile use.
3. **PiStock CAD Link** — a Python workbench/macro for FreeCAD that handles automated, headless background exports.

---

## 📦 Installation

> The full deployment guide (Raspberry Pi / Docker) will grow as the core stabilizes. The script below is the path shown in the [installation video](https://youtu.be/Fmihq0oUiy8).

### Quick start — Raspberry Pi (early)

```bash
git clone https://github.com/pistock-org/PiStock.git
cd PiStock
./deploy/install_pi.sh
```

Once it finishes, the service is reachable at:

```
https://pistock.local:8000
```

On first launch you'll add the SSL certificate (`cert.pem`, generated during install) to your browser, then set an **access** password and an **admin** password.

### FreeCAD workbench

From the web UI, open the **Database Admin** plugin and copy the FreeCAD workbench to a USB drive, then drop it into your FreeCAD `Mod` folder and restart FreeCAD:

- **Linux:** `~/.local/share/FreeCAD/Mod/`

The *PiStock* workbench should then appear in your workbench list.

> 💡 You can also run PiStock **locally on any Linux machine** without a Raspberry Pi — handy for single-user setups.

### Development prerequisites

- Python 3.10+
- FreeCAD 1.1 (for testing the export pipeline)

---

## 🤝 Contributing

Feedback, bug reports, and feature ideas are genuinely welcome — open an issue and tell me what's blocking you or what you'd want.

A note on the contribution model:

- The core server and official web client are licensed under **AGPLv3**.
- This is an early, single-maintainer project. I want to keep a coherent vision, so I'll be deliberate about which feature requests get merged — that's not a "no", it's a "let's talk".
- You're free to **fork and adapt** PiStock to your own needs at any time (that's the whole point of open source).

---

## 📄 License

PiStock is open-source software licensed under the **GNU Affero General Public License v3 (AGPLv3)**. See the [`LICENSE`](LICENSE) file for details.
