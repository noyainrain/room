/** Room UI. */

import {WindowElement, renderTileItem} from "./core.js";
import {Vector, emitParticle, querySelector} from "./util.js";
import {BlueprintEffectsElement} from "./workshop.js";

const VERSION = "0.1.2";

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
        querySelector(this, ".room-inventory-open-workshop").addEventListener("click", () => {
            querySelector(document, "room-game", GameElement).workshopWindow.open();
            this.close();
        });
        querySelector(this, ".room-inventory-open-credits").addEventListener("click", () => {
            querySelector(document, "room-game", GameElement).creditsWindow.open();
            this.close();
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
            this.#room ? `${location.origin}/#${this.#room.id}` : "";
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

/** Credits window. */
class CreditsElement extends WindowElement {
    constructor() {
        super();
        querySelector(this, "h2 span").textContent = VERSION;
        querySelector(this, "button").addEventListener("click", () => this.close());
    }
}
customElements.define("room-credits", CreditsElement);

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
            if (game.player) {
                game.perform({
                    type: "UpdateBlueprintAction",
                    player_id: game.player.id,
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
    #h2 = querySelector(this, "h2");
    #p = querySelector(this, "p");
    #button = querySelector(this, "button");

    constructor() {
        super();
        this.#button.addEventListener("click", () => this.close());
    }

    /**
     * Open a dialog.
     * @param {string} [title] - Message title
     * @param {string} [text] - Message text
     * @param {string} [reply] - Suggested player reply
     */
    async open(title = "", text = "", reply = "Okay") {
        this.#h2.textContent = title;
        this.#p.textContent = text;
        this.#button.textContent = reply;
        return super.open();
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
 * @fires {ActionEvent#MovePlayerAction}
 */
export class GameElement extends HTMLElement {
    static #ROOM_SIZE = 8;
    static #ROOM_WIDTH = this.#ROOM_SIZE;
    static #ROOM_HEIGHT = this.#ROOM_SIZE;
    // In px
    static #TILE_SIZE = 8;
    static #PLAYER_IMAGE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAPklEQVQYV2NkIAAYkeVD////D+KvZmSEi8MZIMnVq1eD1YeGhsIVgRUgS8JMhCkiTgG6KRhWwI3F50hcvgUA66okCTKgZHUAAAAASUVORK5CYII=";
    // In px / s
    static #PLAYER_SPEED = GameElement.#ROOM_HEIGHT / 2 * GameElement.#TILE_SIZE;
    // Two tiles horizontally, one vertically
    static #PLAYER_REACH = Math.sqrt(5);
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
     * Current player. `null` before joining.
     * @type {?Player}
     */
    player = null;

    /**
     * Player inventory window.
     * @type {InventoryElement}
     */
    inventoryWindow = querySelector(this, "room-inventory", InventoryElement);

    /**
     * Credits window.
     * @type {CreditsElement}
     */
    creditsWindow = querySelector(this, "room-credits", CreditsElement);

    /**
     * Workshop window.
     * @type {WorkshopElement}
     */
    workshopWindow = querySelector(this, "room-workshop", WorkshopElement);

    /**
     * Blueprint editor window.
     * @type {BlueprintElement}
     */
    blueprintWindow = querySelector(this, "room-blueprint", BlueprintElement);

    /** Blueprint effects editor window. */
    blueprintEffectsWindow = querySelector(this, "room-blueprint-effects", BlueprintEffectsElement);

    /**
     * Dialog window.
     * @type {DialogElement}
     */
    dialogWindow = querySelector(this, "room-dialog", DialogElement);

    /** @type {Tile[]} */
    #tiles = [];
    /** @type {Map<string, Player>} */
    #players = new Map();
    /** @type {?Tile} */
    #item = null;
    #time = performance.now() / 1000;
    /** @type {?DOMPoint} */
    #moveTarget = null;

    #tilesElement = querySelector(this, ".room-game-tiles");
    #tileTemplate = querySelector(this, ".room-game-tile-template", HTMLTemplateElement);
    /** @type {Set<HTMLDivElement>} */
    #reachableTileElements = new Set();
    /** @type {Map<string, EntityElement>} */
    #playerElements = new Map();
    /** @type {?EntityElement} */
    #playerElement = null;
    #itemElement = querySelector(this, ".room-game-item", EntityElement);
    #connectionWindow = querySelector(this, ".room-game-connection", WindowElement);

    #scale = 1;
    #tapTimeout = 0;
    #moveInterval = 0;
    /** @type {?DOMPoint} */
    #pointer = null;
    /** @type {?WebSocket} */
    #socket = null;

    constructor() {
        super();

        const showError = () => this.dialogWindow.open(
            "Error",
            "Oops, something went very wrong! We will fix the problem as soon as possible. " +
            "Meanwhile, you may try again."
        );
        addEventListener("error", showError);
        addEventListener("unhandledrejection", showError);

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
            "MovePlayerAction",
            event => this.#movePlayer(/** @type {ActionEvent<MovePlayerAction>} */ (event).action)
        );
        this.addEventListener("FailedAction", event => {
            throw new Error(/** @type {ActionEvent<FailedAction>} */ (event).action.message);
        });
    }

    connectedCallback() {
        const scale = () => {
            const size = GameElement.#ROOM_SIZE * GameElement.#TILE_SIZE;
            this.#scale = Math.min(
                Math.floor(this.offsetWidth / size), Math.floor(this.offsetHeight / size)
            );
            this.style.setProperty("--room-game-scale", this.#scale.toString());
        };
        addEventListener("resize", scale);
        scale();

        // Work around Safari recognizing touch-action only on clickable elements (see
        // https://bugs.webkit.org/show_bug.cgi?id=149854)
        document.documentElement.addEventListener("click", () => {});

        /**
         * @param {PointerEvent} event
         * @returns {DOMPoint}
         */
        const getSceneCoordinates =
            event => new DOMPoint(event.clientX / this.#scale, event.clientY / this.#scale);
        const scene = querySelector(this, ".room-game-scene", HTMLDivElement);

        scene.addEventListener("pointerdown", event => {
            this.#tapTimeout = setTimeout(() => {
                this.#moveInterval = setInterval(() => {
                    if (this.player && this.#playerElement) {
                        this.perform({
                            type: "MovePlayerAction",
                            player_id: this.player.id,
                            position: [
                                this.#playerElement.position.x, this.#playerElement.position.y
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
                if (element?.classList.contains("room-game-tile-reachable") && this.player) {
                    if (this.#item) {
                        this.perform({
                            type: "PlaceTileAction",
                            player_id: this.player.id,
                            tile_index: index,
                            blueprint_id: this.#item.id
                        });
                    } else {
                        this.perform({
                            type: "UseAction",
                            player_id: this.player.id,
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
            this.#moveTarget = null;
            clearInterval(this.#moveInterval);
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
            if (this.player && this.#playerElement) {
                this.perform({
                    type: "MovePlayerAction",
                    player_id: this.player.id,
                    position: [this.#playerElement.position.x, this.#playerElement.position.y]
                });
            }
        }, GameElement.#HEARTBEAT * 1000);
        this.#tick();

        const roomID = (location.hash.slice(1) || localStorage.roomID) ?? null;
        // When a new room is created, store it
        if (!roomID) {
            this.addEventListener("WelcomeAction", event => {
                localStorage.roomID =
                    /** @type {ActionEvent<WelcomeAction>} */ (event).action.room.id;
            }, {once: true});
        }
        this.#connect(roomID);
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
     * @param {?string} roomID
     * @param {Object} [options]
     * @param {number} [options.delay]
     */
    #connect(roomID, {delay = 0} = {}) {
        (async () => {
            this.#connectionWindow.open();
            await new Promise(resolve => setTimeout(resolve, delay * 1000));

            const protocol = location.protocol === "https:" ? "wss:" : "ws:";
            const path = roomID ? `/rooms/${roomID}` : "/rooms";
            this.#socket = new WebSocket(`${protocol}//${location.host}${path}`);
            this.#socket.addEventListener("open", () => this.#connectionWindow.close());
            this.#socket.addEventListener("close", async event => {
                this.#connectionWindow.close();
                if (event.code === 4004) {
                    this.dialogWindow.open("Unknown Room", `Oops, there is no room #${roomID}!`);
                } else if ([1001, 1006].includes(event.code)) {
                    this.#connect(roomID, {delay: 1});
                } else {
                    throw new Error("Assertion failed");
                }
            });
            this.#socket.addEventListener("message", event => {
                const action = /** @type {Action} */ (JSON.parse(event.data));
                // When a new room is created, remember it for reconnecting
                if (!roomID && action.type === "WelcomeAction") {
                    roomID = action.room.id;
                }
                this.dispatchEvent(new ActionEvent(action));
            });
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
        this.#players = new Map(Object.entries(this.room.players));
        this.player = this.#players.get(action.player_id) ?? null;

        this.inventoryWindow.room = this.room;
        this.inventoryWindow.items = Array.from(this.blueprints.values());
        this.workshopWindow.blueprints = this.blueprints;

        this.#renderTiles();
        for (const element of this.#playerElements.values()) {
            element.remove();
        }
        this.#playerElements.clear();
        for (const player of this.#players.values()) {
            this.#spawnPlayer(player);
        }
        this.#playerElement = this.#playerElements.get(action.player_id) ?? null;
        location.hash = this.room.id;

        // Start
        (async () => {
            await this.dialogWindow.open(
                "Room", "What should we do with all this limited space?", "Start"
            );
            this.dialogWindow.open(
                "Welcome!", "Hold / Touch to move. Click / Tap to use items."
            );
        })();
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
        for (const effect of action.effects) {
            switch (effect.type) {
            case "TransformTileEffect":
                // eslint-disable-next-line no-case-declarations
                const tile = this.blueprints.get(effect.blueprint_id);
                if (!tile) {
                    throw new Error("Assertion failed");
                }
                this.#tiles[action.tile_index] = tile;
                this.#updateTileElement(action.tile_index);
                break;
            default:
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

    /** @param {MovePlayerAction} action */
    #movePlayer(action) {
        if (action.player_id === this.player?.id) {
            return;
        }
        let playerElement = this.#playerElements.get(action.player_id);
        const position = new DOMPoint(...action.position);

        // Join
        if (!playerElement) {
            const player = {id: action.player_id, position: action.position};
            this.#players.set(player.id, player);
            playerElement = this.#spawnPlayer(player);
        }

        // Leave
        if (position.x === -1) {
            this.#players.delete(action.player_id);
            playerElement.remove();
            this.#playerElements.delete(action.player_id);
        }

        playerElement.position = position;
    }

    #tick() {
        const now = performance.now() / 1000;
        const t = now - this.#time;
        this.#time = now;

        // Move player
        if (this.#moveTarget && this.#playerElement) {
            const direction = Vector.subtract(this.#moveTarget, this.#playerElement.position);
            const distance = Vector.abs(direction);

            if (distance > GameElement.#MOVE_DELTA) {
                let {x, y} = this.#playerElement.position;
                const currentIndex = parseInt(
                    this.#getTileElement(this.#playerElement.position)?.dataset.index ?? ""
                );
                const v = Vector.scale(direction, GameElement.#PLAYER_SPEED * t / distance);

                let tileElement = this.#getTileElement(
                    new DOMPoint(x + v.x, this.#playerElement.position.y)
                );
                if (tileElement) {
                    const i = parseInt(tileElement.dataset.index ?? "");
                    // Do not block if stuck inside wall
                    if (!this.#tiles[i]?.wall || i === currentIndex) {
                        x += v.x;
                    }
                }

                tileElement = this.#getTileElement(
                    new DOMPoint(this.#playerElement.position.x, y + v.y)
                );
                if (tileElement) {
                    const i = parseInt(tileElement.dataset.index ?? "");
                    // Do not block if stuck inside wall
                    if (!this.#tiles[i]?.wall || i === currentIndex) {
                        y += v.y;
                    }
                }

                this.#playerElement.position = new DOMPoint(x, y);
            }
        }

        // Find reachable tiles
        if (this.#playerElement) {
            const tile = this.#getTileElement(this.#playerElement.position);
            if (!tile) {
                throw new Error("Assertion failed");
            }
            const reachableTileElements = this.#findTileElementsAround(
                tile, GameElement.#PLAYER_REACH
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
     * @param {Player} player
     * @returns {EntityElement}
     */
    #spawnPlayer(player) {
        const playerElement = new EntityElement();
        playerElement.classList.add("room-game-player");
        playerElement.style.setProperty("--room-game-player-hover-delay", Math.random().toString());
        playerElement.position = new DOMPoint(...player.position);
        playerElement.image = GameElement.#PLAYER_IMAGE;
        this.#tilesElement.after(playerElement);
        this.#playerElements.set(player.id, playerElement);
        return playerElement;
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
}
customElements.define("room-game", GameElement);

/**
 * Event for a performed player action.
 * @template {Action} T
 */
class ActionEvent extends Event {
    /**
     * Performed player action.
     * @type {T}
     */
    action;

    /** @param {T} action */
    constructor(action) {
        super(action.type);
        this.action = action;
    }
}
