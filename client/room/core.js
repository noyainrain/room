/** Core concepts. */

import {querySelector} from "./util.js";

/**
 * Foreground window.
 *
 * @fires {Event#close}
 */
export class WindowElement extends HTMLElement {
    constructor() {
        super();
        this.classList.add("room-window");
    }

    /** Open the window. */
    async open() {
        this.classList.add("room-window-open");
        return new Promise(resolve => this.addEventListener("close", resolve, {once: true}));
    }

    /** Close the window. */
    close() {
        this.classList.remove("room-window-open");
        this.dispatchEvent(new Event("close"));
    }

    /** Open or close the window depending on its state. */
    toggle() {
        this.classList.contains("room-window-open") ? this.close() : this.open();
    }
}
customElements.define("room-window", WindowElement);

/**
 * Render a tile list item.
 * @param {Tile} blueprint - Relevant tile blueprint
 * @returns HTMLLIElement
 */
export function renderTileItem(blueprint) {
    const li = querySelector(
        document.importNode(renderTileItem.template.content, true), "li", HTMLLIElement
    );
    querySelector(li, ".tile", HTMLImageElement).src = blueprint.image;
    return li;
}
renderTileItem.template = querySelector(document, "#tile-item-template", HTMLTemplateElement);
