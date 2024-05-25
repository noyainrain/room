/** Core concepts. */

import {querySelector} from "util";

/**
 * Get the current game client.
 * @returns {Promise<import("game").GameElement>}
 */
export async function getGame() {
    if (!getGame.game) {
        await customElements.whenDefined("room-game");
        getGame.game = /** @type {import("game").GameElement } */ (
            document.querySelector("room-game")
        );
    }
    return getGame.game;
}
/** @type {?import("game").GameElement} */
getGame.game = null;

// Work around TypeScript not supporting tuple for rest @param (see
// https://github.com/microsoft/TypeScript/issues/49801)
/**
 * Decorator for a player request.
 *
 * If there is a general web API error ({@link TypeError}), the player is notified.
 * @template {unknown[]} P
 * @param {(...args: P) => Promise<unknown>} func
 * @returns {(...args: P) => Promise<void>}
 */
export function request(func) {
    return async (...args) => {
        try {
            await func(...args);
        } catch (e) {
            if (e instanceof TypeError) {
                const game = /** @type {import("game").GameElement } */ (
                    document.querySelector("room-game")
                );
                game.dialogWindow.open(
                    "Offline",
                    "Oops, Room is offline. Please check your network connection and try again."
                );
            } else {
                throw e;
            }
        }
    };
}

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

/** Window header. */
export class WindowHeaderElement extends HTMLElement {
    /**
     * Parent window, if any.
     * @type {?WindowElement}
     */
    window = null;

    constructor() {
        super();
        const shadow = this.attachShadow({mode: "open"});
        shadow.append(
            document.importNode(
                querySelector(
                    document, "#room-window-header-template", HTMLTemplateElement
                ).content, true
            )
        );
        querySelector(shadow, ".room-window-header-close").addEventListener(
            "click", () => this.window?.close()
        );
    }

    connectedCallback() {
        (async () => {
            await customElements.whenDefined("room-window");
            this.window = this.closest(".room-window");
        })();
    }

    /**
     * Type of close control, either a close or a back button.
     * @type {"close" | "back"}
     */
    get close() {
        const value = this.getAttribute("close");
        return value === "back" ? value : "close";
    }
}
customElements.define("room-window-header", WindowHeaderElement);

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
