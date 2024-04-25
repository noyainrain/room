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

/** Thrown when an assertion fails. */
export class AssertionError extends Error {
    /**
     * @param {string} [message]
     * @param {ErrorOptions} [options]
     */
    constructor(message = "Assertion failed", options = {}) {
        super(message, options);
    }
}

/**
 * Split an array into chunks.
 * @template T
 * @param {T[]} array - Array to split
 * @param {number} size - Chunk size
 * @returns {T[][]}
 */
export function chunk(array, size) {
    return new Array(Math.ceil(array.length / size)).fill(null).map(
        (_, i) => array.slice(i * size, (i + 1) * size)
    );
}

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

/**
 * CSS properties of a particle.
 *
 * The special property `class` corresponds to the `class` attribute of the particle.
 *
 * Alternatively, may be a {@link string} directly specifying the `class` attribute.
 * @typedef {Object<string, string> | string} ParticleStyle
 */

/**
 * Emit a particle and apply a CSS transition.
 *
 * By default, the particle is absolutely positioned at the origin. After the transition, the
 * particle is removed.
 *
 * @param {Element} element - Element to emit the particle at
 * @param {ParticleStyle} start - Initial style of the particle. Should define a `transition`.
 * @param {ParticleStyle} end - Final style of the particle. Should change a property named in
 * `transition`.
 */
export async function emitParticle(element, start, end) {
    if (typeof start === "string") {
        start = {class: start};
    }
    if (typeof end === "string") {
        end = {class: end};
    }

    const particle = document.createElement("div");
    particle.style.position = "absolute";
    particle.style.inset = "0 auto auto 0";
    if ("class" in start) {
        particle.className = start.class;
    }
    for (const [key, value] of Object.entries(start)) {
        // Unsupported properties (like class) are ignored
        particle.style.setProperty(key, value);
    }
    element.append(particle);
    // Trigger reflow, so the next style update will start a transition
    particle.offsetHeight;

    return /** @type {Promise<void>} */ (
        new Promise(resolve => {
            particle.addEventListener("transitionend", () => {
                if (!particle.getAnimations().length) {
                    particle.remove();
                    resolve();
                }
            });
            if (typeof end !== "object") {
                throw new Error("Assertion failed");
            }
            if ("class" in end) {
                particle.className = end.class;
            }
            for (const [key, value] of Object.entries(end)) {
                particle.style.setProperty(key, value);
            }
        })
    );
}

/**
 * TODO.
 * @template T
 * @callback ResolveCallback
 * @param {...string} args
 * @returns {T}
 */

/**
 * TODO.
 * @template T
 */
export class Router {
    /**
     * TODO.
     * @type {[string, T | ResolveCallback<T>][]}
     */
    routes;

    /** @param {[string, T | ResolveCallback<T>][]} routes */
    constructor(routes) {
        this.routes = routes;
    }

    /**
     * TODO.
     * @param {string} path
     * @returns {?T}
     */
    route(path) {
        /** @type {T | ResolveCallback<T> | null} */
        let route = null;
        let args = null;
        for (const [pattern, target] of this.routes) {
            const match = path.match(pattern);
            console.log("MATCH", pattern, match);
            if (match) {
                route = target;
                args = match.slice(1);
                break;
            }
        }

        if (route) {
            // Yes, T might also be function, will raise error, that's documented
            // @ts-ignore
            return typeof route === "function" ? route(...args) : route;
        }
        return null;
    }
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
