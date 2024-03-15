/** Blueprint workshop UI. */

import {WindowElement, renderTileItem} from "core";
import {AssertionError, chunk, querySelector} from "util";

/** Blueprint effects editor window. */
export class BlueprintEffectsElement extends WindowElement {
    /** @type {[Cause, Effect[]][]} */
    #effects = [];
    #dl = querySelector(this, "dl", HTMLDListElement);
    #addCauseElement = querySelector(this, ".room-blueprint-effects-add-cause", HTMLElement);
    #input = querySelector(this, "input", HTMLInputElement);
    #template = querySelector(this, ".room-blueprint-effects-item-template", HTMLTemplateElement);

    constructor() {
        super();
        const form = querySelector(this, "form", HTMLFormElement);
        form.addEventListener("submit", event => {
            event.preventDefault();
            if (form.checkValidity()) {
                // Apply changes
                this.#effects = this.#readEffects();
                this.close();
            }
        });
        querySelector(this, ".room-blueprint-effects-back").addEventListener(
            "click", () => this.close()
        );
        querySelector(this, ".room-blueprint-effects-use-cause").addEventListener(
            "click", event => {
                this.#addItem({type: "UseCause"}, []);
                // @ts-ignore
                event.currentTarget.blur();
            }
        );
    }

    /**
     * Blueprint effects to edit.
     * @type {[Cause, Effect[]][]}
     */
    get effects() {
        return this.#effects;
    }

    set effects(value) {
        this.#effects = value;
        for (const element of Array.from(this.#dl.children)) {
            if (element !== this.#addCauseElement) {
                element.remove();
            }
        }
        for (const [cause, effects] of value) {
            this.#addItem(cause, effects);
        }
        this.#updateInput();
    }

    /**
     * @param {Cause} cause
     * @param {Effect[]} effects
     */
    #addItem(cause, effects) {
        const fragment = document.importNode(this.#template.content, true);
        const dt = querySelector(fragment, "dt");
        const dd = querySelector(fragment, "dd");
        const causeElement = this.#renderCause(cause);
        causeElement.addEventListener("remove", () => {
            dt.remove();
            dd.remove();
            this.#updateInput();
        });
        dt.append(causeElement);
        const effectList = querySelector(dd, "room-effect-list", EffectListElement);
        effectList.effects = effects;
        this.#addCauseElement.before(fragment);
        this.#updateInput();
    }

    /** @returns {[Cause, Effect[]][]} */
    #readEffects() {
        return chunk(Array.from(this.#dl.children).slice(0, -1), 2).map(([dt, dd]) => {
            const causeElement = dt?.firstElementChild;
            const effectList = dd?.firstElementChild;
            if (
                !(causeElement instanceof CauseElement && effectList instanceof EffectListElement)
            ) {
                throw new AssertionError();
            }
            return [causeElement.cause, effectList.effects];
        });
    }

    /**
     * @param {Cause} cause
     * @returns {CauseElement}
     */
    #renderCause(cause) {
        const CauseElement = {UseCause: UseCauseElement}[cause.type];
        const element = new CauseElement();
        element.classList.add("card");
        element.cause = cause;
        return element;
    }

    #updateInput() {
        const effects = this.#readEffects();
        const set = new Set(effects.map(([cause]) => JSON.stringify(cause)));
        this.#input.setCustomValidity(effects.length === set.size ? "" : "invalid");
    }
}
customElements.define("room-blueprint-effects", BlueprintEffectsElement);

/** Effect list form. */
class EffectListElement extends HTMLElement {
    #ul = querySelector(this, "ul", HTMLUListElement);
    #addEffectElement = querySelector(this, ".room-effect-list-add-effect", HTMLLIElement);
    #input = querySelector(this, "input", HTMLInputElement);

    constructor() {
        super();
        const game =
            /** @type {import("./game.js").GameElement} */ (document.querySelector("room-game"));
        querySelector(this, ".room-effect-list-transform-tile-effect").addEventListener(
            "click", event => {
                const result = game.blueprints.values().next();
                if (result.done) {
                    throw new AssertionError();
                }
                this.#addItem({type: "TransformTileEffect", blueprint_id: result.value.id});
                // @ts-ignore
                event.currentTarget.blur();
            }
        );
        this.#updateInput();
    }

    /**
     * Current value.
     * @type {Effect[]}
     * */
    get effects() {
        return Array.from(this.#ul.children).slice(0, -1).map(element => {
            const effectElement = element.firstElementChild;
            if (!(effectElement instanceof EffectElement)) {
                throw new AssertionError();
            }
            return effectElement.effect;
        });
    }

    set effects(value) {
        for (const effect of value) {
            this.#addItem(effect);
        }
    }

    /** @param {Effect} effect */
    #addItem(effect) {
        const li = document.createElement("li");
        const effectElement = this.#renderEffect(effect);
        effectElement.addEventListener("remove", () => {
            li.remove();
            this.#updateInput();
        });
        li.append(effectElement);
        this.#addEffectElement.before(li);
        this.#updateInput();
    }

    /**
     * @param {Effect} effect
     * @returns {EffectElement}
     */
    #renderEffect(effect) {
        const EffectElement = {TransformTileEffect: TransformTileEffectElement}[effect.type];
        const element = new EffectElement();
        element.classList.add("card");
        element.effect = effect;
        return element;
    }

    #updateInput() {
        this.#input.setCustomValidity(this.#ul.children.length - 1 ? "" : "invalid");
    }
}
customElements.define("room-effect-list", EffectListElement);

/** Cause form. */
class CauseElement extends HTMLElement {
    /**
     * Current value.
     * @type {Cause}
     */
    get cause() {
        throw new AssertionError();
    }

    set cause(value) {}
}

/** Effect form. */
class EffectElement extends HTMLElement {
    /**
     * Current value.
     * @type {Effect}
     */
    get effect() {
        throw new AssertionError();
    }

    set effect(value) {}
}

/**
 * Header for cause and effect forms.
 * @fires {Event#remove}
 */
class EffectHeaderElement extends HTMLElement {
    constructor() {
        super();
        const shadow = this.attachShadow({mode: "open"});
        shadow.append(
            document.importNode(
                querySelector(
                    document, "#room-effect-header-template", HTMLTemplateElement
                ).content, true
            )
        );
        querySelector(shadow, ".room-effect-header-remove").addEventListener(
            "click", () => this.dispatchEvent(new Event("remove", {bubbles: true}))
        );
    }
}
customElements.define("room-effect-header", EffectHeaderElement);

/** Use cause form. */
class UseCauseElement extends CauseElement {
    constructor() {
        super();
        this.append(
            document.importNode(
                querySelector(document, "#room-use-cause-template", HTMLTemplateElement).content,
                true
            )
        );
    }

    /** @type {UseCause} */
    get cause() {
        return {type: "UseCause"};
    }

    set cause(value) {}
}
customElements.define("room-use-cause", UseCauseElement);

/** Transform tile effect form. */
class TransformTileEffectElement extends EffectElement {
    /** @type {?Tile} */
    #blueprint = null;
    /** @type {HTMLImageElement} */
    #blueprintImage;
    #game = /** @type {import("./game.js").GameElement} */ (document.querySelector("room-game"));

    constructor() {
        super();
        this.append(
            document.importNode(
                querySelector(
                    document, "#room-transform-tile-effect-template", HTMLTemplateElement
                ).content, true
            )
        );
        this.#blueprintImage = querySelector(
            this, ".room-transform-tile-effect-blueprint img", HTMLImageElement
        );

        const ul = querySelector(this, ".room-transform-tile-effect-blueprint ul");
        for (const blueprint of this.#game.blueprints.values()) {
            const li = renderTileItem(blueprint);
            li.addEventListener("click", event => {
                this.#blueprint = blueprint;
                this.#blueprintImage.src = this.#blueprint.image;
                // @ts-ignore
                event.currentTarget.blur();
            });
            ul.append(li);
        }
    }

    /** @type {TransformTileEffect} */
    get effect() {
        return {type: "TransformTileEffect", blueprint_id: this.#blueprint?.id || ""};
    }

    set effect(value) {
        const blueprint = this.#game.blueprints.get(value.blueprint_id);
        if (!blueprint) {
            throw new AssertionError();
        }
        this.#blueprint = blueprint;
        this.#blueprintImage.src = blueprint.image;
    }
}
customElements.define("room-transform-tile-effect", TransformTileEffectElement);
