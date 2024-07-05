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

/** Extension for :class:`HTMLTextAreaElement` conforming to a pattern. */
export class WithPattern {
    /**
     * Extended element.
     * @type {HTMLTextAreaElement}
     */
    textArea;
    /**
     * Required pattern.
     * @type {RegExp}
     */
    pattern;

    /**
     * @param {HTMLTextAreaElement} textArea
     * @param {RegExp | string} pattern
     */
    constructor(textArea, pattern) {
        this.textArea = textArea;
        this.pattern = new RegExp(pattern);
        this.textArea.addEventListener("input", () => this.#validate());
        this.#validate();
    }

    #validate() {
        const valid = !this.textArea.value ||
            this.pattern.exec(this.textArea.value)?.[0] === this.textArea.value;
        this.textArea.setCustomValidity(valid ? "" : "Please match the requested format.");
    }
}

/**
 * Query with arguments.
 *
 * If there is no result, `undefined` is returned.
 * @template T
 * @callback QueryCallback
 * @param {...?string} args - Query arguments
 * @returns {T | undefined}
 */

/**
 * Router forwarding queries to appropriate query functions.
 * @template T
 */
export class Router {
    /**
     * Routing table, defining the query function to call for paths matching a pattern.
     * @type {[RegExp, QueryCallback<Promise<T>> | QueryCallback<T>][]}
     */
    routes;

    /** @param {[RegExp | string, QueryCallback<Promise<T>> | QueryCallback<T>][]} routes */
    constructor(routes) {
        this.routes = routes.map(([pattern, query]) => [new RegExp(pattern), query]);
    }

    /**
     * Query a path.
     *
     * If there is no result, `undefined` is returned.
     * @param {string} path - Query path
     * @returns {Promise<T | undefined>}
     */
    async route(path) {
        for (const [pattern, query] of this.routes) {
            const match = pattern.exec(path);
            if (match) {
                return await query(...match.slice(1).map(arg => arg ?? null));
            }
        }
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
