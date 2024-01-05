/** Various utilities. */

// because we do not get particle as return value, it must be possible to set dynamic css properties
// for start
// spawnParticle(container, start, end, startProperties, endProperties)
// spawnParticle(body, "foo", "foo-end", {"background": b, "translate": t1}, {"translate": t2, "opacity": o});

// alt: start/end Object<string, string> | string
// spawnParticle(container, start, end)
// spawnParticle(body, "foo", {"class": "foo-end", "opacity": 1});
// ^ also cool: if no end given, we can assume animation :)

/**
 * TODO.
 * @param {Element} element - TODO
 * @param {Object<string, string> | string} start - TODO
 * @param {Object<string, string> | string} [end] - TODO
 */
export async function emitParticle(element, start, end = {}) {
    if (typeof start === "string") {
        start = {class: start};
    }
    if (typeof end === "string") {
        end = {class: end};
    }

    const particle = document.createElement("div");
    particle.style.position = "absolute";
    particle.style.inset = "0 auto auto 0";
    if (start.class) {
        particle.className = start.class;
    }
    Object.assign(particle.style, start);
    //for (const [key, value] of Object.entries(start)) {
    //    if (key === "class") {
    //        particle.className = value;
    //        continue;
    //    }
    //    particle.style.setProperty(key, value);
    //}
    element.append(particle);
    // render particle to apply transition rules, next change will then be transition
    particle.offsetHeight;

    return /** @type {Promise<void>} */ (
        new Promise(resolve => {
            particle.addEventListener("transitionend", () => {
                particle.remove();
                resolve();
            });
            //particle.classList.add(...end);
            //for (const [key, [_, to]] of Object.entries(transitions)) {
            //    particle.style.setProperty(key, to);
            //}
            if (typeof end !== "object") {
                throw new Error("Assertion failed");
            }
            if (end.class) {
                particle.className = end.class;
            }
            Object.assign(particle.style, end);
        })
    );
}

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
