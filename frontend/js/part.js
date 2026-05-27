// ----------------------------------------------------------------------
//  PAGE VIEWER 3D : affiche le .glb d'une piece donnee
// ----------------------------------------------------------------------

// Recupere l'id depuis l'URL : /part.html?id=42
const urlParams = new URLSearchParams(window.location.search);
const partId = urlParams.get("id");

const titleEl = document.getElementById("part-title");
const viewerEl = document.getElementById("viewer-container");
const metaEl = document.getElementById("viewer-meta");

function escapeHtml(text) {
    if (text === null || text === undefined) return "";
    return String(text)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatDate(iso) {
    if (!iso) return "—";
    try {
        const d = new Date(iso);
        return d.toLocaleString();  // locale du navigateur
    } catch {
        return iso;
    }
}

async function loadPart() {
    if (!partId) {
        titleEl.textContent = "Erreur";
        viewerEl.innerHTML = '<div class="error">Aucun id de pièce fourni dans l\'URL.</div>';
        return;
    }

    try {
        const response = await fetch(`/api/v1/parts/${partId}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const part = await response.json();

        titleEl.textContent = part.part_name;
        document.title = `PiStock — ${part.part_name}`;

        if (!part.glb_url) {
            viewerEl.innerHTML = '<div class="error">'
                + 'Cette pièce n\'a pas de modèle 3D associé.</div>';
        } else {
            // Injection du web component model-viewer.
            // 'camera-controls' active la rotation/zoom à la souris.
            // 'auto-rotate' lance une animation de présentation discrète.
            viewerEl.innerHTML = `
                <model-viewer
                    src="${escapeHtml(part.glb_url)}"
                    alt="Modèle 3D de ${escapeHtml(part.part_name)}"
                    camera-controls
                    auto-rotate
                    shadow-intensity="1"
                    exposure="1">
                </model-viewer>
            `;
        }

        // Bloc d'infos sous le viewer
        metaEl.innerHTML = `
            Dernière révision par <span>${escapeHtml(part.last_author || "—")}</span>
            le <span>${escapeHtml(formatDate(part.last_timestamp))}</span>
        `;

    } catch (err) {
        titleEl.textContent = "Erreur";
        viewerEl.innerHTML = `<div class="error">Impossible de charger la pièce : `
            + `${escapeHtml(err.message)}</div>`;
        console.error(err);
    }
}

loadPart();
