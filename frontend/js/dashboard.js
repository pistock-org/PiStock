// ----------------------------------------------------------------------
//  DASHBOARD : liste des pieces dans la base de donnees PiStock
// ----------------------------------------------------------------------
//  Appelle GET /api/v1/parts/full et affiche une ligne par piece avec :
//   nom  |  thumbnail (cliquable -> viewer 3D)  |  photo stock
//   |  quantite  |  location
// ----------------------------------------------------------------------

const API_URL = "/api/v1/parts/full";
const container = document.getElementById("parts-container");

// Petit helper pour echapper les contenus textuels avant injection HTML.
// Indispensable : un part_name pourrait contenir des caracteres
// comme '<' ou '&' qui casseraient le rendu sans cela.
function escapeHtml(text) {
    if (text === null || text === undefined) return "";
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Construit le HTML d'UNE ligne de piece.
function renderPartRow(part) {
    // Cellule "vignette CAO". Cliquable -> ouvre la page viewer 3D
    // si on a effectivement un .glb associé.
    let thumbnailCell;
    if (part.thumbnail_url) {
        const clickable = part.glb_url ? `onclick="openViewer(${part.id})"` : "";
        const cursor = part.glb_url ? "" : 'style="cursor:default"';
        thumbnailCell = `
            <div class="thumbnail-cell" ${clickable} ${cursor}
                 title="${part.glb_url ? "Cliquer pour voir en 3D" : "Pas de modèle 3D"}">
                <img src="${escapeHtml(part.thumbnail_url)}"
                     alt="${escapeHtml(part.part_name)}">
            </div>`;
    } else {
        thumbnailCell = `<div class="thumbnail-cell">
            <span class="placeholder">Pas de vignette</span>
        </div>`;
    }

    // Cellule "photo de la piece en stock" : pas encore alimentée
    // dans le projet, on garde l'emplacement visible (placeholder).
    let stockImgCell;
    if (part.stock_img_url) {
        stockImgCell = `<div class="stock-img-cell">
            <img src="${escapeHtml(part.stock_img_url)}" alt="Stock">
        </div>`;
    } else {
        stockImgCell = `<div class="stock-img-cell">
            <span class="placeholder">Photo<br>stock</span>
        </div>`;
    }

    // Quantite : 0 est une valeur valide (affichee), null = inconnu (—)
    const qtyDisplay = (part.quantity === null || part.quantity === undefined)
        ? `<div class="quantity empty-value">—</div>`
        : `<div class="quantity">${part.quantity}</div>`;

    const locDisplay = part.location
        ? `<div class="location">${escapeHtml(part.location)}</div>`
        : `<div class="location empty-value">—</div>`;

    return `
        <div class="part-row">
            <div class="part-name">${escapeHtml(part.part_name)}</div>
            ${thumbnailCell}
            ${stockImgCell}
            ${qtyDisplay}
            ${locDisplay}
        </div>
    `;
}

// Navigation vers le viewer 3D. Exposee globalement pour etre
// accessible depuis l'attribut onclick="" du HTML genere.
window.openViewer = function(partId) {
    window.location.href = `/part.html?id=${partId}`;
};

// Charge la liste depuis l'API et l'affiche.
async function loadParts() {
    try {
        const response = await fetch(API_URL);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const parts = await response.json();

        if (parts.length === 0) {
            container.className = "empty";
            container.innerHTML = "Aucune pièce dans la base pour l'instant. "
                + "Exportez-en une depuis FreeCAD pour commencer.";
            return;
        }

        // On remplace le conteneur "loading" par la liste rendue.
        container.className = "parts-list";
        container.innerHTML = parts.map(renderPartRow).join("");

    } catch (err) {
        container.className = "error";
        container.innerHTML = `Erreur lors du chargement : ${escapeHtml(err.message)}`;
        console.error(err);
    }
}

loadParts();
