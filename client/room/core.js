/** Core concepts. */

import {querySelector} from "util";

/**
 * @callback RequestCallback
 * @param {...unknown} args
 * @returns {void}
 */

/**
 * TODO.
 *
 * @param {RequestCallback} func
 */
export function request(func) {
    /** @param {unknown[]} args */
    return async (...args) => {
        try {
            await func(...args);
        } catch (e) {
            if (e instanceof TypeError) {
                const game = /** @type {import("./game.js").GameElement } */ (
                    document.querySelector("room-game")
                );
                game.dialogWindow.open(
                    "Offline",
                    "Oops, you seem to be offline. Please check your connection and try again."
                );
                return;
            }
            throw e;
        }
    };
}

/**
 * Decorator for a user request.
 *
 * If the request cannot be fulfilled because of a common web API error (:ref:`NotFoundError`,
 * :ref:`PermissionError`, :ref:`RateLimitError`, :class:`micro.NetworkError`), the user is notified
 * and :attr:`micro.core.request.ABORTED` is returned. A user request function is async.
 *
 * The decorated function may be async.
 */

/**
 * Handle a common call error *e* with a default reaction.
 *
 * :class:`NetworkError`, ``NotFoundError``, ``PermissionError`` and `RateLimitError` are
 * handled. Other errors are re-thrown.
 */

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

/**
 * TODO.
 * @param {string} url
 * @returns {[string, string, string]}
 */
export function parseRoomURL(url) {
    const parsed = new URL(url, location.origin);
    const [, type, roomID, ...excess] = parsed.pathname.split("/");
    console.log("SEGMENTS", type, roomID, excess);
    if (!(type === "invites" && roomID && !excess.length)) {
        throw TypeError(`Bad room url ${url}`);
    }
    return [type, roomID, parsed.hash];
}

/**
 * TODO.
 * @param {string} roomID
 */
export function makeRoomURL(roomID) {
    return `${location.origin}/invites/${roomID}`;
}

//export function parseRoomURL(url) {
//    // const segments = new URL(url).pathname.split("/");
//    // console.log("SEGEMENTS", segments, segments.length);
//    const parsed = new URL(url);
//    const [_, prefix, roomID, ...excess] = parsed.pathname.split("/");
//    console.log("SEGMENTS", _, prefix, roomID, excess);
//    if (!(prefix === "invites" && roomID && !excess.length)) {
//        throw TypeError(`Bad room url ${url}`);
//    }
//    return [prefix, roomID, parsed.hash];
//}
