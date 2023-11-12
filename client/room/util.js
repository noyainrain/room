/** Various utilities. */

/** @param {Error} e */
async function reportError(e) {
    try {
        const error = [
            e.toString(),
            (e.stack ?? "").trim(),
            `${location.pathname}${location.search}${location.hash}`,
            navigator.userAgent
        ].filter(part => part).join("\n");
        await fetch("/errors", {
            method: "POST",
            headers: {"Content-Type": "text/plain"},
            body: error
        });
    } catch (e) {
        console.warn("Failed to report error (%s)", e);
    }
}
addEventListener("error", event => reportError(event.error));
addEventListener("unhandledrejection", event => reportError(event.reason));

/**
 * Query the first child that matches the given selectors in a type-safe way.
 *
 * @template {Element} T
 * @param {Element | Document | DocumentFragment} element - Element or document to query
 * @param {string} selectors - Group of CSS selectors
 * @param {new() => T} [type] - Expected type of the child
 * @returns {T}
 */
export function querySelector(element, selectors, type = /** @type {new() => T} */ (Element)) {
    const child = element.querySelector(selectors);
    if (!(child instanceof type)) {
        throw new Error(`Bad element child type ${selectors}`);
    }
    return child;
}

/** Vector operations. */
export class Vector {
    /**
     * Subtract two vectors.
     * @param {DOMPoint} a - Vector to subtract from
     * @param {DOMPoint} b - Vector to subtract
     * @returns {DOMPoint}
     */
    static subtract(a, b) {
        return new DOMPoint(a.x - b.x, a.y - b.y);
    }

    /**
     * Multiply a vector with a scalar.
     * @param {DOMPoint} v - Vector to multiply
     * @param {number} s - Scalar value
     * @returns {DOMPoint}
     */
    static scale(v, s) {
        return new DOMPoint(v.x * s, v.y * s);
    }

    /**
     * Calculate the magnitude of a vector.
     * @param {DOMPoint} v - Evaluated vector
     * @returns {number}
     */
    static abs(v) {
        return Math.sqrt(v.x * v.x + v.y * v.y);
    }
}
