/** Room UI. */

import {WindowElement, WindowHeaderElement, getGame, renderTileItem, request} from "core";
import {AssertionError, Router, Vector, emitParticle, querySelector} from "util";
import {BlueprintEffectsElement} from "workshop";

const VERSION = "0.9.3";

/**
 * Player inventory window.
 *
 * @fires {InventoryEvent#select}
 */
class InventoryElement extends WindowElement {
    /** @type {Tile[]} */
    #items = [];
    /** @type {?Room} */
    #room = null;
    #ul = querySelector(this, "ul");
    #noItem = querySelector(this, ".room-inventory-no-item");
    #a = querySelector(this, "a", HTMLAnchorElement);

    constructor() {
        super();
        querySelector(this, ".room-inventory-close").addEventListener("click", () => this.close());
        this.#noItem.addEventListener("click", () => {
            this.dispatchEvent(new InventoryEvent("select", null));
            this.close();
        });
        querySelector(this, ".room-inventory-open-workshop").addEventListener("click", async () => {
            const game = await getGame();
            game.workshopWindow.open();
            this.close();
        });
        querySelector(this, ".room-inventory-about").addEventListener("click", async () => {
            const game = await getGame();
            game.aboutWindow.open();
            this.close();
        });
        querySelector(this, ".room-inventory-howto").addEventListener("click", async () => {
            const game = await getGame();
            game.howtoWindow.tutorial = false;
            game.howtoWindow.open();
            this.close();
        });
        querySelector(this, ".room-inventory-open-credits").addEventListener("click", async () => {
            const game = await getGame();
            game.creditsWindow.open();
            this.close();
        });
        querySelector(this, ".room-inventory-player").addEventListener("click", async () => {
            const game = await getGame();
            game.playerEditorWindow.open();
        });
    }

    async connectedCallback() {
        const game = await getGame();
        const playerImg = querySelector(this, ".room-inventory-player img", HTMLImageElement);
        const playerSpan = querySelector(this, ".room-inventory-player span");
        game.addEventListener("playerupdate", event => {
            if (!(event instanceof PlayerEvent)) {
                throw new AssertionError();
            }
            playerImg.src = GameElement.MEMBER_IMAGE;
            playerSpan.textContent = event.player.name;
        });
    }

    /**
     * Inventory items.
     * @returns {Tile[]}
     */
    get items() {
        return this.#items;
    }

    set items(value) {
        this.#items = value;

        for (const li of Array.from(this.#ul.children)) {
            if (li !== this.#noItem) {
                li.remove();
            }
        }
        for (const item of this.#items) {
            const li = renderTileItem(item);
            li.addEventListener("click", () => {
                this.dispatchEvent(new InventoryEvent("select", item));
                this.close();
            });
            this.#ul.append(li);
        }
    }

    /**
     * Related room.
     * @returns {?Room}
     */
    get room() {
        return this.#room;
    }

    set room(value) {
        this.#room = value;
        querySelector(this.#a, "span").textContent = this.#a.href =
            this.#room ? `${location.origin}/invites/${this.#room.id}` : "";
    }
}
customElements.define("room-inventory", InventoryElement);

/** Event about the player inventory. */
class InventoryEvent extends Event {
    /**
     * Affected item.
     * @type {?Tile}
     */
    item;

    /**
     * @param {"select"} type
     * @param {?Tile} item
     */
    constructor(type, item) {
        super(type);
        this.item = item;
    }
}

/** About room window. */
class AboutElement extends WindowElement {
    #titleElement = querySelector(this, "room-window-header span");
    #p = querySelector(this, "p");

    constructor() {
        super();
        querySelector(this, ".room-about-edit").addEventListener("click", async () => {
            const game = await getGame();
            game.roomEditorWindow.open();
        });
    }

    connectedCallback() {
        (async () => {
            const game = await getGame();
            game.addEventListener(
                "WelcomeAction",
                event => this.#update(/** @type {ActionEvent<WelcomeAction>} */ (event).action.room)
            );
            game.addEventListener(
                "UpdateRoomAction",
                event => this.#update(
                    /** @type {ActionEvent<UpdateRoomAction>} */ (event).action.room
                )
            );
        })();
    }

    /** @param {BaseRoom} room */
    #update(room) {
        this.#titleElement.textContent = room.title;
        this.#p.textContent = room.description;
    }
}
customElements.define("room-about", AboutElement);

/** Room details editor window. */
class RoomEditorElement extends WindowElement {
    #titleInput = querySelector(this, '[name="title"]', HTMLInputElement);
    #descriptionTextArea = querySelector(this, '[name="description"]', HTMLTextAreaElement);

    constructor() {
        super();
        const form = querySelector(this, "form", HTMLFormElement);
        form.addEventListener("submit", async event => {
            event.preventDefault();
            const game = await getGame();
            if (form.checkValidity() && game.room && game.member) {
                game.perform({
                    type: "UpdateRoomAction",
                    member_id: game.member.id,
                    room: {
                        id: game.room.id,
                        title: this.#titleInput.value,
                        description: this.#descriptionTextArea.value.trim() || null
                    }
                });
                this.close();
            }
        });
    }

    async open() {
        const game = await getGame();
        if (game.room) {
            this.#titleInput.value = game.room.title;
            this.#descriptionTextArea.value = game.room.description ?? "";
        }
        await super.open();
    }
}
customElements.define("room-editor", RoomEditorElement);

/** How to play window. */
class HowtoElement extends WindowElement {
    #header = querySelector(this, "room-window-header", WindowHeaderElement);

    constructor() {
        super();
        querySelector(this, ".room-howto-start").addEventListener("click", () => this.close());
    }

    /**
     * Indicates if the window is in tutorial mode.
     * @type {boolean}
     */
    get tutorial() {
        return this.hasAttribute("tutorial");
    }

    set tutorial(value) {
        this.toggleAttribute("tutorial", value);
        this.#header.close = value ? "none" : "close";
    }
}
customElements.define("room-howto", HowtoElement);

/** Credits window. */
class CreditsElement extends WindowElement {
    constructor() {
        super();
        querySelector(this, "h2 span").textContent = VERSION;
        querySelector(this, "button").addEventListener("click", () => this.close());
    }
}
customElements.define("room-credits", CreditsElement);

/** Player editor window. */
class PlayerEditorElement extends WindowElement {
    #nameInput = querySelector(this, '[name="name"]', HTMLInputElement);

    constructor() {
        super();
        const form = querySelector(this, "form", HTMLFormElement);
        form.addEventListener("submit", request(
            /** @param {SubmitEvent} event */
            async event => {
                event.preventDefault();
                if (form.checkValidity()) {
                    const game = await getGame();
                    await game.updatePlayer({
                        id: game.player.id,
                        token: game.player.token,
                        name: this.#nameInput.value,
                        tutorial: game.player.tutorial
                    });
                    this.close();
                }
            }
        ));
    }

    async open() {
        const game = await getGame();
        this.#nameInput.value = game.player.name;
        await super.open();
    }
}
customElements.define("room-player-editor", PlayerEditorElement);

/** Workshop window. */
class WorkshopElement extends WindowElement {
    /** @type {Map<string, Tile>} */
    #blueprints = new Map();
    #ul = querySelector(this, "ul");
    #createBlueprintItem = querySelector(this, ".room-workshop-create-blueprint");

    connectedCallback() {
        querySelector(this, ".room-workshop-close").addEventListener("click", () => this.close());
        this.#createBlueprintItem.addEventListener("click", () => {
            const {blueprintWindow} = querySelector(document, "room-game", GameElement);
            blueprintWindow.blueprint = null;
            blueprintWindow.open();
        });
    }

    /**
     * Tile blueprints.
     * @returns {Map<string, Tile>}
     */
    get blueprints() {
        return this.#blueprints;
    }

    set blueprints(value) {
        this.#blueprints = value;

        for (const li of Array.from(this.#ul.children)) {
            if (li !== this.#createBlueprintItem) {
                li.remove();
            }
        }
        for (const blueprint of this.#blueprints.values()) {
            const li = renderTileItem(blueprint);
            li.addEventListener("click", () => {
                const {blueprintWindow} = querySelector(document, "room-game", GameElement);
                blueprintWindow.blueprint = blueprint;
                blueprintWindow.open();
            });
            this.#createBlueprintItem.before(li);
        }
    }
}
customElements.define("room-workshop", WorkshopElement);

/** Blueprint editor window. */
class BlueprintElement extends WindowElement {
    // CGA color palette (see https://en.wikipedia.org/wiki/Color_Graphics_Adapter#Color_palette)
    static #PALETTE = [
        // Black
        "#000", "#555",
        // White
        "#aaa", "#fff",
        // Red
        "#a00", "#f55",
        // Yellow / Brown
        "#a50", "#ff5",
        // Green
        "#0a0", "#5f5",
        // Cyan
        "#0aa", "#5ff",
        // Blue
        "#00a", "#55f",
        // Magenta
        "#a0a", "#f5f"
    ];

    /** @type {?Tile} */
    #blueprint = null;
    /** @type {[Cause, Effect[]][]} */
    #effects = [];
    #canvas = querySelector(this, "canvas", HTMLCanvasElement);
    /** @type {CanvasRenderingContext2D} */
    #context;
    #sourceImg = querySelector(this, ".room-blueprint-source", HTMLImageElement);
    #wallInput = querySelector(this, '[name="wall"]', HTMLInputElement);
    #effectsElement = querySelector(this, ".room-blueprint-effects span");

    constructor() {
        super();

        const context = this.#canvas.getContext("2d");
        if (!context) {
            throw new Error("Assertion failed");
        }
        this.#context = context;

        const fieldset = querySelector(this, "fieldset");
        const template = querySelector(this, ".room-blueprint-color-template", HTMLTemplateElement);
        for (const [i, color] of [...BlueprintElement.#PALETTE, ""].entries()) {
            const label = querySelector(
                /** @type {DocumentFragment} */ (template.content.cloneNode(true)), "label",
                HTMLLabelElement
            );
            label.style.setProperty("--room-blueprint-color-value", color);
            const input = querySelector(label, "input", HTMLInputElement);
            input.value = color;
            input.checked = i === 0;
            querySelector(label, "span").classList.toggle("placeholder", !color);
            fieldset.append(label);
        }

        let color = BlueprintElement.#PALETTE[0] ?? "";
        fieldset.addEventListener("change", event => {
            const input = event.target;
            if (!(input instanceof HTMLInputElement)) {
                throw new Error("Assertion failed");
            }
            color = input.value;
        });
        /** @param {PointerEvent} event */
        const paint = event => {
            if (event.buttons) {
                this.#context.fillStyle = color || "black";
                this.#context.globalCompositeOperation = color ? "source-over" : "destination-out";
                this.#context.fillRect(
                    Math.floor(event.offsetX * this.#canvas.width / this.#canvas.clientWidth),
                    Math.floor(event.offsetY * this.#canvas.height / this.#canvas.clientHeight), 1,
                    1
                );
            }
        };
        this.#canvas.addEventListener("pointerdown", paint);
        this.#canvas.addEventListener("pointermove", paint);

        querySelector(this, "form").addEventListener("submit", event => {
            event.preventDefault();

            const game = querySelector(document, "room-game", GameElement);
            const image = this.#canvas.toDataURL();
            if (game.member) {
                game.perform({
                    type: "UpdateBlueprintAction",
                    member_id: game.member.id,
                    blueprint: {
                        id: this.#blueprint?.id ?? "",
                        image,
                        wall: this.#wallInput.checked,
                        effects: this.#effects
                    }
                });
            }
            this.close();
            console.log("Updated blueprint", image);
        });
        querySelector(this, ".room-blueprint-back").addEventListener("click", () => this.close());
        querySelector(this, ".room-blueprint-effects").addEventListener("click", async () => {
            const game = querySelector(document, "room-game", GameElement);
            game.blueprintEffectsWindow.effects = this.#effects;
            await game.blueprintEffectsWindow.open();
            this.#effects = game.blueprintEffectsWindow.effects;
            this.#updateEffectsElement();
        });
    }

    /**
     * Blueprint to edit. `null` if new.
     * @returns {?Tile}
     */
    get blueprint() {
        return this.#blueprint;
    }

    set blueprint(value) {
        this.#blueprint = value;
        this.#effects = value?.effects ?? [];
        if (this.#blueprint) {
            this.#sourceImg.src = this.#blueprint.image;
            this.#context.globalCompositeOperation = "copy";
            this.#context.drawImage(this.#sourceImg, 0, 0);
            this.#sourceImg.src = "";
            this.#wallInput.checked = this.#blueprint.wall;
        } else {
            this.#context.clearRect(0, 0, this.#canvas.width, this.#canvas.height);
            this.#wallInput.checked = false;
        }
        this.#updateEffectsElement();
    }

    #updateEffectsElement() {
        this.#effectsElement.textContent = this.#effects.length === 0 ? "No Effects"
            : (this.#effects.length === 1 ? "1 Effect" : `${this.#effects.length} Effects`);
    }
}
customElements.define("room-blueprint", BlueprintElement);

/** Dialog window. */
class DialogElement extends WindowElement {
    /** @type {HTMLHeadingElement} */
    #h2;
    /** @type {HTMLParagraphElement} */
    #p;
    /** @type {HTMLButtonElement} */
    #button;

    constructor() {
        super();
        this.append(
            querySelector(document, "#room-dialog-template", HTMLTemplateElement).content.cloneNode(true)
        );
        this.#h2 = querySelector(this, "h2");
        this.#p = querySelector(this, "p");
        this.#button = querySelector(this, "button");
        this.#button.addEventListener("click", () => this.close());
    }

    /**
     * Message text.
     * @type {string}
     */
    get text() {
        if (this.#p.textContent === null) {
            throw new AssertionError();
        }
        return this.#p.textContent;
    }

    set text(value) {
        this.#p.textContent = value;
    }

    /**
     * Message title.
     * @type {string}
     */
    get caption() {
        if (this.#h2.textContent === null) {
            throw new AssertionError();
        }
        return this.#h2.textContent;
    }

    set caption(value) {
        this.#h2.textContent = value;
    }

    /**
     * Suggested player reply.
     * @type {string}
     */
    get reply() {
        if (this.#button.textContent === null) {
            throw new AssertionError();
        }
        return this.#button.textContent;
    }

    set reply(value) {
        this.#button.textContent = value;
    }
}
customElements.define("room-dialog", DialogElement);

/** Scene entity. */
class EntityElement extends HTMLElement {
    #position = new DOMPoint();
    /** @type {?string} */
    #image = null;

    constructor() {
        super();
        this.classList.add("room-entity");
    }

    /**
     * Current position in px.
     * @returns {DOMPoint}
     */
    get position() {
        return this.#position;
    }

    set position(value) {
        this.#position = value;
        this.style.setProperty("--room-entity-x", `${this.#position.x}px`);
        this.style.setProperty("--room-entity-y", `${this.#position.y}px`);
    }

    /**
     * Rendered image as data URL. Invisible if `null`.
     * @returns {?string}.
     */
    get image() {
        return this.#image;
    }

    set image(value) {
        this.#image = value;
        this.style.setProperty(
            "--room-entity-image", this.#image ? `url("${this.#image}")` : "none"
        );
    }
}
customElements.define("room-entity", EntityElement);

/**
 * Game client.
 *
 * @fires {ActionEvent#WelcomeAction}
 * @fires {ActionEvent#UseAction}
 * @fires {ActionEvent#UpdateBlueprintAction}
 * @fires {ActionEvent#MoveMemberAction}
 */
export class GameElement extends HTMLElement {
    /** Member avatar URL. */
    static MEMBER_IMAGE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAPklEQVQYV2NkIAAYkeVD////D+KvZmSEi8MZIMnVq1eD1YeGhsIVgRUgS8JMhCkiTgG6KRhWwI3F50hcvgUA66okCTKgZHUAAAAASUVORK5CYII=";

    static #ROOM_WIDTH = 16;
    static #ROOM_HEIGHT = 9;
    // In px
    static #TILE_SIZE = 8;
    // In px / s
    static #MEMBER_SPEED = GameElement.#ROOM_HEIGHT / 2 * GameElement.#TILE_SIZE;
    // Two tiles horizontally, one vertically
    static #MEMBER_REACH = Math.sqrt(5);
    // In px
    static #MOVE_DELTA = 1;
    // In s
    static #TAP_TIMEOUT = 1 / 5;
    // In s
    static #MOVE_INTERVAL = 1 / 8;
    // Popular proxy servers have a default timeout of 60 s
    static #HEARTBEAT = 60 / 2;

    /**
     * Represented room. `null` before joining.
     * @type {?Room}
     */
    room = null;

    /**
     * Tile blueprints by ID.
     * @type {Map<string, Tile>}
     */
    blueprints = new Map();

    /**
     * Current member. `null` before joining.
     * @type {?Member}
     */
    member = null;

    /** Player inventory window. */
    inventoryWindow = querySelector(this, "room-inventory", InventoryElement);

    /** About room window. */
    aboutWindow = querySelector(this, "room-about", AboutElement);

    /** Room details editor window. */
    roomEditorWindow = querySelector(this, "room-editor", RoomEditorElement);

    /** How to play window. */
    howtoWindow = querySelector(this, "room-howto", HowtoElement);

    /** Credits window. */
    creditsWindow = querySelector(this, "room-credits", CreditsElement);

    /** Player editor window. */
    playerEditorWindow = querySelector(this, "room-player-editor", PlayerEditorElement);

    /** Workshop window. */
    workshopWindow = querySelector(this, "room-workshop", WorkshopElement);

    /** Blueprint editor window. */
    blueprintWindow = querySelector(this, "room-blueprint", BlueprintElement);

    /** Blueprint effects editor window. */
    blueprintEffectsWindow = querySelector(this, "room-blueprint-effects", BlueprintEffectsElement);

    /** @type {?PrivatePlayer} */
    #player = null;
    /** @type {Tile[]} */
    #tiles = [];
    /** @type {Map<string, Member>} */
    #members = new Map();
    /** @type {?Tile} */
    #item = null;
    #time = performance.now() / 1000;
    /** @type {?DOMPoint} */
    #moveTarget = null;
    /**
     * @callback ApplyEffectCallback
     * @param {Effect} effect
     * @param {number} tileIndex
     * @param {Member} member
     * @type {Object<string, ApplyEffectCallback>}
     */
    #effects = {
        TransformTileEffect: this.#applyTransformTileEffect.bind(this),
        OpenDialogEffect: this.#applyOpenDialogEffect.bind(this)
    };

    #tilesElement = querySelector(this, ".room-game-tiles");
    #tileTemplate = querySelector(this, ".room-game-tile-template", HTMLTemplateElement);
    /** @type {Set<HTMLDivElement>} */
    #reachableTileElements = new Set();
    /** @type {Map<string, EntityElement>} */
    #memberElements = new Map();
    /** @type {?EntityElement} */
    #memberElement = null;
    #itemElement = querySelector(this, ".room-game-item", EntityElement);
    #dialogsElement = querySelector(this, ".room-game-dialogs");
    #connectionWindow = querySelector(this, ".room-game-connection", WindowElement);

    /** @type {Router<void>} */
    #router;
    #scale = 1;
    #tapTimeout = 0;
    #moveInterval = 0;
    /** @type {?DOMPoint} */
    #pointer = null;
    /** @type {?WebSocket} */
    #socket = null;
    #lessons = new Set(["moveMember", "placeTile"]);

    constructor() {
        super();

        const showError = () => this.openDialog(
            "Oops, something went very wrong! We will fix the problem as soon as possible. " +
            "Meanwhile, you may try again.",
            {caption: "Error"}
        );
        addEventListener("error", showError);
        addEventListener("unhandledrejection", showError);

        this.#router = new Router([
            ["^/invites/([^/]+)$", this.#initRoom.bind(this)],
            ["^/$", this.#initPlayerRoom.bind(this)]
        ]);

        this.classList.toggle(
            "room-game-can-fullscreen",
            "fullscreenEnabled" in document && document.fullscreenEnabled
        );
        querySelector(this, ".room-game-fullscreen button").addEventListener("click", async () => {
            if (document.fullscreenElement) {
                document.exitFullscreen();
            } else {
                this.requestFullscreen();
                if ("lock" in screen.orientation) {
                    try {
                        // @ts-ignore
                        await screen.orientation.lock("landscape");
                    } catch (e) {
                        if (e instanceof DOMException && e.name === "NotSupportedError") {
                            // Ignore
                        } else {
                            throw e;
                        }
                    }
                }
            }
        });

        const equipmentElement = querySelector(this, ".room-game-equipment");
        equipmentElement.addEventListener("click", () => this.inventoryWindow.toggle());
        this.inventoryWindow.addEventListener("select", event => {
            this.#item = /** @type {InventoryEvent} */ (event).item;
            this.classList.toggle("room-game-equipped", Boolean(this.#item));
            this.#itemElement.image = this.#item?.image ?? null;
            querySelector(equipmentElement, ".tile", HTMLImageElement).src =
                this.#item?.image ?? "";
        });

        this.addEventListener(
            "WelcomeAction",
            event => this.#join(/** @type {ActionEvent<WelcomeAction>} */ (event).action)
        );
        this.addEventListener(
            "UpdateRoomAction",
            event => this.#updateRoom(/** @type {ActionEvent<UpdateRoomAction>} */ (event).action)
        );
        this.addEventListener(
            "PlaceTileAction",
            event => this.#placeTile(/** @type {ActionEvent<PlaceTileAction>} */ (event).action)
        );
        this.addEventListener(
            "UseAction",
            event => this.#use(/** @type {ActionEvent<UseAction>} */ (event).action)
        );
        this.addEventListener(
            "UpdateBlueprintAction",
            event => this.#updateBlueprint(
                /** @type {ActionEvent<UpdateBlueprintAction>} */ (event).action
            )
        );
        this.addEventListener(
            "MoveMemberAction",
            event => this.#moveMember(/** @type {ActionEvent<MoveMemberAction>} */ (event).action)
        );
        this.addEventListener("FailedAction", event => {
            throw new Error(/** @type {ActionEvent<FailedAction>} */ (event).action.message);
        });
    }

    connectedCallback() {
        let sceneBounds = new DOMRect();

        const sceneContent = querySelector(this, ".room-game-scene .room-game-content");
        const scale = () => {
            this.#scale = Math.floor(
                Math.min(
                    this.offsetWidth * devicePixelRatio /
                        (GameElement.#ROOM_WIDTH * GameElement.#TILE_SIZE),
                    this.offsetHeight * devicePixelRatio /
                        (GameElement.#ROOM_HEIGHT * GameElement.#TILE_SIZE)
                )
            ) / devicePixelRatio;
            this.style.setProperty("--room-game-scale", this.#scale.toString());
            sceneBounds = sceneContent.getBoundingClientRect();
        };
        addEventListener("resize", scale);
        scale();

        const updateOrientation = () => {
            this.classList.toggle(
                "room-game-portrait",
                ["portrait-primary", "portrait-secondary"].includes(screen.orientation.type)
            );
        };
        screen.orientation.addEventListener("change", updateOrientation);
        updateOrientation();

        // Work around Safari recognizing touch-action only on clickable elements (see
        // https://bugs.webkit.org/show_bug.cgi?id=149854)
        document.documentElement.addEventListener("click", () => {});

        /**
         * @param {PointerEvent} event
         * @returns {DOMPoint}
         */
        const getSceneCoordinates =
            event => new DOMPoint(
                (event.clientX - sceneBounds.left) / this.#scale,
                (event.clientY - sceneBounds.top) / this.#scale
            );
        const scene = querySelector(this, ".room-game-scene", HTMLDivElement);

        scene.addEventListener("pointerdown", event => {
            this.#tapTimeout = setTimeout(() => {
                this.#moveInterval = setInterval(() => {
                    if (this.member && this.#memberElement) {
                        this.perform({
                            type: "MoveMemberAction",
                            member_id: this.member.id,
                            position: [
                                this.#memberElement.position.x, this.#memberElement.position.y
                            ]
                        });
                    }
                }, GameElement.#MOVE_INTERVAL * 1000);
                this.#moveTarget = getSceneCoordinates(event);
            }, GameElement.#TAP_TIMEOUT * 1000);
        });
        scene.addEventListener("pointerup", event => {
            if (!this.#moveTarget) {
                const element = this.#getTileElement(getSceneCoordinates(event));
                const index = parseInt(element?.dataset.index ?? "");
                if (element?.classList.contains("room-game-tile-reachable") && this.member) {
                    if (this.#item) {
                        this.perform({
                            type: "PlaceTileAction",
                            member_id: this.member.id,
                            tile_index: index,
                            blueprint_id: this.#item.id
                        });
                        this.#completeLesson("placeTile");

                    } else {
                        this.perform({
                            type: "UseAction",
                            member_id: this.member.id,
                            tile_index: index,
                            effects: []
                        });
                    }
                }
            }
        });
        // When the pointer is down, detect its release outside of the scene
        addEventListener("pointerup", () => {
            clearTimeout(this.#tapTimeout);
            if (this.#moveTarget) {
                this.#moveTarget = null;
                clearInterval(this.#moveInterval);
                this.#completeLesson("moveMember");
            }
        });

        // When the pointer is down, detect movement outside of the scene
        addEventListener("pointermove", event => {
            this.#pointer = getSceneCoordinates(event);
            if (this.#moveTarget) {
                this.#moveTarget = this.#pointer;
            }
            this.#itemElement.position = this.#pointer;
        });

        scene.addEventListener("pointerenter", event => {
            this.#pointer = getSceneCoordinates(event);
            this.#itemElement.position = this.#pointer;
            scene.classList.add("room-game-scene-has-pointer");
        });
        scene.addEventListener("pointerleave", () => {
            this.#pointer = null;
            scene.classList.remove("room-game-scene-has-pointer");
        });

        setInterval(() => {
            if (this.member && this.#memberElement) {
                this.perform({
                    type: "MoveMemberAction",
                    member_id: this.member.id,
                    position: [this.#memberElement.position.x, this.#memberElement.position.y]
                });
            }
        }, GameElement.#HEARTBEAT * 1000);
        this.#tick();

        this.#launch();
    }

    #launch = request(
        async () => {
            const response = await fetch("/api/players/self");
            this.#player = await response.json();
            this.dispatchEvent(new PlayerEvent("playerupdate", this.player));

            // Compatibility with legacy invite links
            if (location.pathname === "/" && location.hash) {
                history.replaceState(null, "", `/invites/${location.hash.slice(1)}`);
            }

            this.#router.route(location.pathname);
        }
    );

    /** @param {?string} id */
    #initRoom(id) {
        if (!id) {
            throw new AssertionError();
        }
        this.#connect(id);
    }

    #initPlayerRoom = request(
        async () => {
            let roomID = localStorage.roomID ?? null;
            if (!roomID) {
                const response = await fetch("/api/rooms", {method: "POST"});
                const room = await response.json();
                roomID = localStorage.roomID = room.id;
            }
            this.#connect(roomID);
        }
    );

    /**
     * Current player.
     * @type {PrivatePlayer}
     */
    get player() {
        if (!this.#player) {
            throw new Error("Uninitialized game");
        }
        return this.#player;
    }

    /**
     * Send an action to the server to perform it.
     * @param {Action} action - Action to perform
     */
    perform(action) {
        try {
            this.#socket?.send(JSON.stringify(action));
        } catch (e) {
            if (e instanceof DOMException && e.name === "InvalidStateError") {
                // Drop if reconnecting
            } else {
                throw e;
            }
        }
    }

    /**
     * Update the current player.
     * @param {PrivatePlayer} patch - Player patch
     */
    async updatePlayer(patch) {
        const response = await fetch(
            "/api/players/self", {method: "PUT", body: JSON.stringify(patch)}
        );
        this.#player = await response.json();
        this.dispatchEvent(new PlayerEvent("playerupdate", this.player));
    }

    /**
     * Open a dialog.
     *
     * Return once the dialog is closed.
     * @param {string} text - Message text
     * @param {Object} [options] - Options
     * @param {string} [options.caption] - Message title
     * @param {string} [options.reply] - Suggested player reply
     */
    async openDialog(text, {caption = "", reply = "Okay"} = {}) {
        const dialog = new DialogElement();
        dialog.text = text;
        dialog.caption = caption;
        dialog.reply = reply;
        this.#dialogsElement.append(dialog);
        await dialog.open();
        dialog.remove();
    }

    /**
     * @param {number | DOMPoint} index
     * @returns {?HTMLDivElement}
     */
    #getTileElement(index) {
        if (index instanceof DOMPoint) {
            if (
                !(
                    index.x >= 0 && index.x < GameElement.#ROOM_WIDTH * GameElement.#TILE_SIZE &&
                    index.y >= 0 && index.y < GameElement.#ROOM_HEIGHT * GameElement.#TILE_SIZE
                )
            ) {
                return null;
            }
            return this.#getTileElement(
                Math.trunc(index.x / GameElement.#TILE_SIZE) +
                Math.trunc(index.y / GameElement.#TILE_SIZE) * GameElement.#ROOM_WIDTH
            );
        }
        const div = this.#tilesElement.children[index] ?? null;
        if (div && !(div instanceof HTMLDivElement)) {
            throw new Error("Assertion failed");
        }
        return div;
    }

    /**
     * @param {HTMLDivElement} tile
     * @param {number} radius
     * @returns {Set<HTMLDivElement>}
     */
    #findTileElementsAround(tile, radius) {
        //   w     C: Center of area
        // H---V   V: Vertical offset
        //  \  |   H: Horizontal offset
        // r \ | h r: Radius of area
        //    \|   h: Height
        //     C   w: Width of area at height
        //
        // h^2 + w^2 = r^2
        // w = sqrt(r^2 - h^2)
        const index = parseInt(tile.dataset.index ?? "");
        const center = new DOMPoint(
            index % GameElement.#ROOM_WIDTH, Math.trunc(index / GameElement.#ROOM_WIDTH)
        );

        const tiles = new Set();
        const top = Math.max(Math.ceil(center.y - radius), 0);
        const bottom = Math.min(center.y + radius, GameElement.#ROOM_HEIGHT - 1);
        for (let y = top; y <= bottom; y++) {
            const height = Math.abs(y - center.y);
            const width = Math.sqrt(radius ** 2 - height ** 2);
            const left = Math.max(Math.ceil(center.x - width), 0);
            const right = Math.min(center.x + width, GameElement.#ROOM_WIDTH - 1);
            for (let x = left; x <= right; x++) {
                tiles.add(this.#getTileElement(y * GameElement.#ROOM_WIDTH + x));
            }
        }
        return tiles;
    }

    /**
     * @param {string} roomID
     * @param {Object} [options]
     * @param {number} [options.delay]
     */
    #connect(roomID, {delay = 0} = {}) {
        (async () => {
            this.#connectionWindow.open();
            await new Promise(resolve => setTimeout(resolve, delay * 1000));

            const protocol = location.protocol === "https:" ? "wss:" : "ws:";
            this.#socket = new WebSocket(
                `${protocol}//${location.host}/api/rooms/${roomID}/actions`
            );
            this.#socket.addEventListener("open", () => this.#connectionWindow.close());
            this.#socket.addEventListener("close", async event => {
                this.#connectionWindow.close();
                if (event.code === 4004) {
                    this.openDialog(
                        `Oops, there is no room #${roomID}!`, {caption: "Unknown Room"}
                    );
                } else if ([1001, 1006].includes(event.code)) {
                    this.#connect(roomID, {delay: 1});
                } else {
                    throw new AssertionError();
                }
            });
            this.#socket.addEventListener(
                "message",
                event => this.dispatchEvent(
                    new ActionEvent(/** @type {Action} */ (JSON.parse(event.data)))
                )
            );
        })();
    }

    /** @param {WelcomeAction} action */
    #join(action) {
        this.room = action.room;
        this.blueprints = new Map(Object.entries(this.room.blueprints));
        this.#tiles = this.room.tile_ids.map(id => {
            const tile = this.blueprints.get(id);
            if (!tile) {
                throw new Error("Assertion failed");
            }
            return tile;
        });
        this.#members = new Map(this.room.members.map(member => [member.id, member]));
        this.member = this.#members.get(action.member_id) ?? null;

        this.inventoryWindow.room = this.room;
        this.inventoryWindow.items = Array.from(this.blueprints.values());
        this.workshopWindow.blueprints = this.blueprints;

        this.#renderTiles();
        for (const element of this.#memberElements.values()) {
            element.remove();
        }
        this.#memberElements.clear();
        for (const member of this.#members.values()) {
            this.#spawnMember(member);
        }
        this.#memberElement = this.#memberElements.get(action.member_id) ?? null;
        history.replaceState(null, "", `/invites/${this.room.id}${location.hash}`);

        // Start
        if (!this.player.tutorial) {
            this.howtoWindow.tutorial = true;
            this.howtoWindow.open();
        }
    }

    /** @param {UpdateRoomAction} action */
    async #updateRoom(action) {
        if (!this.room) {
            throw new AssertionError();
        }
        Object.assign(this.room, action.room);
    }

    /** @param {PlaceTileAction} action */
    async #placeTile(action) {
        const tile = this.blueprints.get(action.blueprint_id);
        const cell = this.#getTileElement(action.tile_index);
        if (!(tile && cell)) {
            throw new Error("Assertion failed");
        }
        this.#tiles[action.tile_index] = tile;
        await emitParticle(
            cell, {class: "room-game-tile-particle", background: `url(${tile.image})`},
            "room-game-tile-particle room-game-tile-particle-end"
        );
        this.#updateTileElement(action.tile_index);
    }

    /** @param {UseAction} action */
    #use(action) {
        const member = this.#members.get(action.member_id);
        if (!member) {
            throw new AssertionError();
        }
        for (const effect of action.effects) {
            const apply = this.#effects[effect.type];
            if (apply) {
                apply(effect, action.tile_index, member);
            } else {
                console.warn("Unknown effect %s", effect.type);
            }
        }
    }

    /** @param {UpdateBlueprintAction} action */
    #updateBlueprint(action) {
        this.blueprints.set(action.blueprint.id, action.blueprint);
        this.inventoryWindow.items = Array.from(this.blueprints.values());
        this.workshopWindow.blueprints = this.blueprints;

        for (const [i, tile] of this.#tiles.entries()) {
            if (tile.id === action.blueprint.id) {
                this.#tiles[i] = action.blueprint;
                const cell = this.#getTileElement(i);
                if (!cell) {
                    throw new Error("Assertion failed");
                }
                this.#blend(cell, () => this.#updateTileElement(i));
            }
        }
    }

    /** @param {MoveMemberAction} action */
    #moveMember(action) {
        if (action.member_id === this.member?.id) {
            return;
        }
        let memberElement = this.#memberElements.get(action.member_id);
        const position = new DOMPoint(...action.position);

        // Join
        if (!memberElement) {
            const member = {
                id: action.member_id, player_id: "", player: {id: "", name: ""},
                position: action.position
            };
            this.#members.set(member.id, member);
            memberElement = this.#spawnMember(member);
        }

        // Leave
        if (position.x === -1) {
            this.#members.delete(action.member_id);
            memberElement.remove();
            this.#memberElements.delete(action.member_id);
        }

        memberElement.position = position;
    }

    /** @type {ApplyEffectCallback} */
    #applyTransformTileEffect(effect, tileIndex) {
        if (effect.type !== "TransformTileEffect") {
            throw new AssertionError();
        }
        const tile = this.blueprints.get(effect.blueprint_id);
        if (!tile) {
            throw new AssertionError();
        }
        this.#tiles[tileIndex] = tile;
        this.#updateTileElement(tileIndex);
    }

    /** @type {ApplyEffectCallback} */
    #applyOpenDialogEffect(effect, tileIndex, member) {
        if (effect.type !== "OpenDialogEffect") {
            throw new AssertionError();
        }
        if (member.id !== this.member?.id) {
            return;
        }
        (async () => {
            const lines = effect.message.split("\n").flatMap(line => line.trim() || []);
            for (const [i, line] of lines.entries()) {
                await this.openDialog(line, {reply: i === lines.length - 1 ? "Okay" : "Continue"});
            }
        })();
    }

    #tick() {
        const now = performance.now() / 1000;
        const t = now - this.#time;
        this.#time = now;

        // Move member
        if (this.#moveTarget && this.#memberElement) {
            const direction = Vector.subtract(this.#moveTarget, this.#memberElement.position);
            const distance = Vector.abs(direction);

            if (distance > GameElement.#MOVE_DELTA) {
                let {x, y} = this.#memberElement.position;
                const currentIndex = parseInt(
                    this.#getTileElement(this.#memberElement.position)?.dataset.index ?? ""
                );
                const v = Vector.scale(direction, GameElement.#MEMBER_SPEED * t / distance);

                let tileElement = this.#getTileElement(
                    new DOMPoint(x + v.x, this.#memberElement.position.y)
                );
                if (tileElement) {
                    const i = parseInt(tileElement.dataset.index ?? "");
                    // Do not block if stuck inside wall
                    if (!this.#tiles[i]?.wall || i === currentIndex) {
                        x += v.x;
                    }
                }

                tileElement = this.#getTileElement(
                    new DOMPoint(this.#memberElement.position.x, y + v.y)
                );
                if (tileElement) {
                    const i = parseInt(tileElement.dataset.index ?? "");
                    // Do not block if stuck inside wall
                    if (!this.#tiles[i]?.wall || i === currentIndex) {
                        y += v.y;
                    }
                }

                this.#memberElement.position = new DOMPoint(x, y);
            }
        }

        // Find reachable tiles
        if (this.#memberElement) {
            const tile = this.#getTileElement(this.#memberElement.position);
            if (!tile) {
                throw new Error("Assertion failed");
            }
            const reachableTileElements = this.#findTileElementsAround(
                tile, GameElement.#MEMBER_REACH
            );
            for (const tile of this.#reachableTileElements) {
                if (!reachableTileElements.has(tile)) {
                    tile.classList.remove("room-game-tile-reachable");
                }
            }
            for (const tile of reachableTileElements) {
                if (!this.#reachableTileElements.has(tile)) {
                    tile.classList.add("room-game-tile-reachable");
                }
            }
            this.#reachableTileElements = reachableTileElements;
        }

        requestAnimationFrame(() => this.#tick());
    }

    #renderTiles() {
        this.#tilesElement.textContent = "";
        for (let i = 0; i < this.#tiles.length; i++) {
            const tile = querySelector(
                /** @type {DocumentFragment} */ (this.#tileTemplate.content.cloneNode(true)), "div",
                HTMLDivElement
            );
            tile.dataset.index = i.toString();
            this.#tilesElement.append(tile);
            this.#updateTileElement(i);
        }
    }

    /** @param {number} index */
    #updateTileElement(index) {
        const tile = this.#tiles[index];
        const div = this.#getTileElement(index);
        div?.classList.toggle(
            "room-game-tile-usable",
            Boolean(tile?.effects.find(([cause]) => cause.type === "UseCause"))
        );
        const img = div?.firstElementChild;
        if (!(img instanceof HTMLImageElement)) {
            throw new Error("Assertion failed");
        }
        img.src = tile?.image ?? "";
    }

    /**
     * @param {Member} member
     * @returns {EntityElement}
     */
    #spawnMember(member) {
        const memberElement = new EntityElement();
        memberElement.classList.add("room-game-member");
        memberElement.style.setProperty("--room-game-member-hover-delay", Math.random().toString());
        memberElement.position = new DOMPoint(...member.position);
        memberElement.image = GameElement.MEMBER_IMAGE;
        this.#tilesElement.after(memberElement);
        this.#memberElements.set(member.id, memberElement);
        return memberElement;
    }

    /** @callback UpdateBlendCallback */

    /**
     * @param {Element} element
     * @param {UpdateBlendCallback} update
     */
    #blend(element, update) {
        element.addEventListener("transitionend", () => {
            element.classList.remove("blended");
            update();
        }, {once: true});
        element.classList.add("blended");
    }

    /** @param {"moveMember" | "placeTile"} lesson */
    async #completeLesson(lesson) {
        this.#lessons.delete(lesson);
        if (this.#lessons.size === 0 && !this.player.tutorial) {
            try {
                await this.updatePlayer({...this.player, tutorial: true});
            } catch (e) {
                if (e instanceof TypeError) {
                    // Ignore and retry update on the next completed lesson
                } else {
                    throw e;
                }
            }
        }
    }
}
customElements.define("room-game", GameElement);

/**
 * Event for an action performed by a room member.
 * @template {Action} T
 */
class ActionEvent extends Event {
    /**
     * Action performed by a room member.
     * @type {T}
     */
    action;

    /** @param {T} action */
    constructor(action) {
        super(action.type);
        this.action = action;
    }
}

/** Event about a player. */
class PlayerEvent extends Event {
    /**
     * Relevant player.
     * @type {PrivatePlayer}
     */
    player;

    /**
     * @param {string} type
     * @param {PrivatePlayer} player
     */
    constructor(type, player) {
        super(type);
        this.player = player;
    }
}
