const PALETTE = [
    // black
    "rgb(0, 0, 0)",
    "rgb(85, 85, 85)",
    // red
    "rgb(170, 0, 0)",
    "rgb(255, 85, 85)",
    // green
    "rgb(0, 170, 0)",
    "rgb(85, 255, 85)",
    // yellow
    "rgb(170, 85, 0)",
    "rgb(255, 255, 85)",
    // blue
    "rgb(0, 0, 170)",
    "rgb(85, 85, 255)",
    // magenta
    "rgb(170, 0, 170)",
    "rgb(255, 85, 255)",
    // cyan
    "rgb(0, 170, 170)",
    "rgb(85, 255, 255)",
    // white
    "rgb(170, 170, 170)",
    "rgb(255, 255, 255)",
]

class Vector {
    static length(v) {
        return Math.sqrt(v.x * v.x + v.y * v.y);
    }

    static scale(v, s) {
        return {x: v.x * s, y: v.y * s};
    }

    static add(a, b) {
        return {x: a.x + b.x, y: a.y + b.y};
    }

    static sub(a, b) {
        return {x: a.x - b.x, y: a.y - b.y};
    }
}

const PLAYER_IMAGE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAPklEQVQYV2NkIAAYkeVD////D+KvZmSEi8MZIMnVq1eD1YeGhsIVgRUgS8JMhCkiTgG6KRhWwI3F50hcvgUA66okCTKgZHUAAAAASUVORK5CYII="

class GameElement extends HTMLElement {
    blueprints = [];
    #item = null;

    #worldElement;
    #workshopElement;
    #itemDiv;
    #black = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAFElEQVQYV2NkYGD4D8Q4AePIUAAAhWQIAUzZY7sAAAAASUVORK5CYII="
    #socket;

    constructor() {
        super();
        this.#worldElement = this.querySelector("room-world");
        this.#workshopElement = this.querySelector("room-workshop");
        this.#itemDiv = this.querySelector(".room-game-item");
    }

    connectedCallback() {
        const resize = () => {
            // const height = Math.floor(this.parentElement.offsetHeight / 8) * 8;
            // const maxHeight = Math.floor(this.parentElement.offsetHeight / 8) * 8;
            // const scale = maxHeight / this.offsetHeight;
            this.scale = Math.min(
                Math.floor(this.parentElement.offsetWidth / 64),
                Math.floor(this.parentElement.offsetHeight / 64)
            );
            const height = this.scale * 64;
            this.#worldElement.scale = this.scale;
            this.#worldElement.style.transform = `scale(${this.scale})`;
            this.style.width = `${height}px`;
            this.style.height = `${height}px`;
        };
        window.addEventListener("resize", resize);
        resize();

        this.blueprints = JSON.parse(localStorage.blueprints ?? "[]");
        // XXX
        //setTimeout(() => {
        //    let room = JSON.parse(localStorage.room ?? "null");
        //    if (!room) {
        //        room = {
        //            tiles: new Array(8 * 8).fill({image: this.#black, wall: false})
        //        };
        //    }
        //    this.#worldElement.room = room;

        //    //this.showWorkshop();
        //}, 10);

        this.querySelector(".room-game-no-item").addEventListener("click", () => {
            this.item = null;
            this.toggleInventory();
        });

        this.querySelector(".room-game-item").addEventListener("click", () => {
            this.toggleInventory();
        });

        this.querySelector(".room-game-open-workshop").addEventListener("click", () => {
            this.toggleInventory();
            this.showWorkshop();
        });

        let roomID = location.hash.slice(1);
        if (!roomID) {
            roomID = localStorage.roomID ?? "new";
        }
        console.log("scheme", location.protocol);
        const scheme = (location.protocol === "https:") ? "wss" : "ws";
        this.#socket = new WebSocket(`${scheme}://${location.host}/rooms/${roomID}`);
        this.#socket.addEventListener("close", event => {
            console.log("OMG CLOSED", event.code, event.reason);
        });
        this.#socket.addEventListener("error", () => {
            console.log("OMG ERROR");
        });
        this.#socket.addEventListener("open", () => {
            console.log("OMG open");
        });
        this.#socket.addEventListener("message", event => {
            console.log("MESSAGE RECEIVED", event.data);
            const action = JSON.parse(event.data);
            switch (action.type) {
            case "JoinAction":
                if (roomID === "new") {
                    localStorage.roomID = action.room.id;
                }
                location.hash = action.room.id;

                this.onJoin(action);
                break;
            case "UpdateBlueprintAction":
                this.onBlueprintUpdate(action);
                break;
            case "UseAction":
                this.onUse(action);
                break;
            case "MoveAction":
                this.onMove(action);
                break;
            default:
                throw new Error("Assertion failed");
            }
        });

        const intro = document.querySelector(".room-game-intro");
        const tutorial = document.querySelector(".room-game-tutorial");
        intro.querySelector("button").addEventListener("click", () => {
            intro.style.display = "none";
            tutorial.style.display = "block";
        });
        tutorial.querySelector("button").addEventListener("click", () => {
            tutorial.style.display = "none";
        });
    }

    set item(value) {
        this.#item = value;
        if (value) {
            this.#itemDiv.firstElementChild.src = value.image;
        } else {
            this.#itemDiv.firstElementChild.src = "";
        }
        this.classList.toggle("room-world-has-item", value);
        this.#worldElement.item = value;
    }

    onJoin(action) {
        console.log("STARTED WORLD");
        this.userID = action.user_id;
        const room = action.room;
        this.blueprints = room.blueprints;
        room.tiles = room.tile_ids.map(tileID => this.blueprints[tileID]);
        this.#worldElement.room = room;
    }

    onBlueprintUpdate(action) {
        this.blueprints[action.blueprint.id] = action.blueprint;
        const room = this.#worldElement.room;
        room.tiles = room.tile_ids.map(tileID => this.blueprints[tileID]);
        this.#worldElement.room = room;
        if (this.#workshopElement.blueprints) {
            this.showWorkshop();
        }
        //this.blueprints.push(blueprint);
        //localStorage.blueprints = JSON.stringify(this.blueprints);
        //this.#workshopElement.blueprints = this.blueprints;
    }

    onUse(action) {
        console.log("USEEEE");
        const tile = this.blueprints[action.item_id];
        this.#worldElement.room.tile_ids[action.tile_index] = tile.id;
        this.#worldElement.room.tiles[action.tile_index] = tile;
        this.querySelector(".room-world-map").children[action.tile_index].querySelector("img").src =
            tile.image;
    }

    onMove(action) {
        if (action.user_id === this.userID) {
            return;
        }
        this.#worldElement.movePlayer(action.user_id, {x: action.position[0], y: action.position[1]});
    }

    run(action) {
        this.#socket.send(JSON.stringify(action));
    }

    showWorkshop() {
        this.#workshopElement.blueprints = this.blueprints;
    }

    toggleInventory() {
        const div = this.querySelector(".room-game-inventory");
        if (div.style.display === "block") {
            div.style.display = "none";
            //this.#worldElement.item = null;
            return;
        }

        div.style.display = "block";

        const ul = div.querySelector("ul");
        for (let elem of ul.querySelectorAll(".bluerpint")) {
            elem.remove();
        }

        const template = document.querySelector("#blueprint-template");
        for (let blueprint of Object.values(this.blueprints)) {
            let li = template.content.cloneNode(true).firstElementChild;
            li.querySelector("img").src = blueprint.image;
            li.tabIndex = 0;
            li.dataset.tileID = blueprint.id;
            li.addEventListener("click", event => {
                const i = Array.from(ul.children).indexOf(event.currentTarget);
                console.log("I", i);

                //this.item = this.blueprints[i - 1];
                this.item = this.blueprints[event.currentTarget.dataset.tileID];
                div.style.display = "none";
            });
            ul.append(li);
        }

        const a = this.querySelector(".room-game-inventory a");
        a.href = location.href;
        a.textContent = location.href;
    }
}
customElements.define("room-game", GameElement);

class EntityElement extends HTMLElement {
    #position;

    constructor() {
        super();
        this.classList.add("room-entity");
        this.position = {x: 0, y: 0};
    }

    set position(value) {
        this.#position = value;
        this.style.transform = `translate(${value.x - 4}px, ${value.y - 4}px)`;
    }

    get position() {
        return this.#position;
    }
}
customElements.define("room-entity", EntityElement);

class PlayerElement extends EntityElement {};
customElements.define("room-player", PlayerElement);

class WorldElement extends HTMLElement {
    #target;
    #room = null;
    #player;
    #playerElements = new Map();
    #itemElement;
    #item = null;
    #pointer = {x: 0, y: 0};
    #mapDiv;
    #focusedIndex = null;
    #focusedDiv = null;
    scale = 1;
    #gameElement;

    constructor() {
        super();
        this.#gameElement = document.querySelector("room-game");
        this.#player = this.querySelector("room-player");
        this.#itemElement = this.querySelector(".room-world-item");
        this.#mapDiv = this.querySelector(".room-world-map");
    }

    getIndex(p) {
        return Math.floor(p.x / 8) + 8 * Math.floor(p.y / 8);
    }

    getPosition(i) {
        const y = Math.floor(i / 8);
        const x = i - y * 8;
        return {x, y};
    }

    connectedCallback() {
        this.#player.style.background = `url(${PLAYER_IMAGE})`;
        this.#player.position = {x: 32, y: 32};

        //this.#player.addEventListener("click", () => {
        //    document.querySelector("room-game").toggleInventory();
        //});

        // const map = this.querySelector(".room-world-map");
        const map = document.querySelector("body");
        let pointerDown = false;
        let moveInterval = null;
        const updateTarget = event => {
            this.#target = {
                x: Math.min(Math.max(event.clientX / this.#gameElement.scale, 0), 63),
                y: Math.min(Math.max(event.clientY / this.#gameElement.scale, 0), 63)
            };
            if (!moveInterval) {
                moveInterval = setInterval(() => {
                    const action = {
                        type: "MoveAction",
                        user_id: this.#gameElement.userID,
                        position: [this.#player.position.x, this.#player.position.y]
                    };
                    this.#gameElement.run(action);
                }, 1000 / 8);
            }
            //this.#target = {
            //    x: event.target.offsetLeft + event.offsetX, y: event.target.offsetTop + event.offsetY
            //};
            //console.log("TARGET", this.#target);
        };
        let t = null;
        let timeout = null;
        const TAP_TIMEOUT = 200;
        map.addEventListener("pointerdown", event => {
            event.preventDefault();
            t = new Date();
            timeout = setTimeout(() => {
                updateTarget(event);
            }, TAP_TIMEOUT);
        });

        const cleanup = () => {
            clearTimeout(timeout);
            t = null;
            clearInterval(moveInterval);
            moveInterval = null;
            this.#target = null;
        };
        window.addEventListener("pointerup", event => {
            cleanup();
        });
        map.addEventListener("pointerup", event => {
            if (t && (new Date() - t < TAP_TIMEOUT)) {
                // click
                if (this.#item) {
                    this.#itemElement.position = {x: event.clientX / this.#gameElement.scale, y: event.clientY / this.#gameElement.scale};
                }
                    // const i = Array.from(div.children).indexOf(event.currentTarget);
                    //const i = Math.floor(event.clientX / this.#scale / 8) + 8 * Math.floor(event.clientY / this.#scale / 8);
                    //console.log("I", i, event.clientX / this.#scale / 8);
                if (this.#focusedDiv) {
                    const i = this.getIndex({x: this.#focusedDiv.offsetLeft, y: this.#focusedDiv.offsetTop});
                    console.log("IIII", i);

                    if (this.#item) {
                        const action = {
                            type: "UseAction",
                            user_id: this.#gameElement.userID,
                            tile_index: i,
                            item_id: this.#item.id
                        };
                        this.#gameElement.run(action);

                        //this.#room.tiles[i] = this.#item;
                        //this.querySelector(".room-world-map").children[i].querySelector("img").src = this.#item.image;
                        //localStorage.room = JSON.stringify(this.#room);
                    } else {
                        //window.alert("INTERACT");
                        // TODO change tile if it has an action attached
                        // -> build a door tile (open and closed)
                        // TODO add button for workshop
                        // TODO let player wobble a bit
                    }
                }
            }

            //cleanup();
        });
        map.addEventListener("pointermove", event => {
            // if (event.buttons) {
            this.#pointer = {
                x: Math.min(Math.max(event.clientX / this.#gameElement.scale, 0), 63),
                y: Math.min(Math.max(event.clientY / this.#gameElement.scale, 0), 63)
            };
            if (t && (new Date() - t >= TAP_TIMEOUT)) {
                updateTarget(event);
            }
            this.#itemElement.position = {x: event.clientX / this.#gameElement.scale, y: event.clientY / this.#gameElement.scale};
        });

        this.#step();
    }

    set room(value) {
        console.log("ROOM", this.#room);
        this.#room = value;

        // render
        const div = this.querySelector(".room-world-map");
        div.textContent = "";
        for (let tile of this.#room.tiles) {
            const d = document.createElement("div");
            const img = document.createElement("img");
            img.src = tile.image;
            d.append(img);
            div.append(d);
            //d.addEventListener("click", event => {
            //    //document.querySelector("room-game").showWorkshop();
            //    if (this.#item) {
            //        const i = Array.from(div.children).indexOf(event.currentTarget);
            //        this.#room.tiles[i] = this.#item;
            //        event.currentTarget.querySelector("img").src = this.#item.image;
            //    }
            //});
        }
    }

    get room() {
        return this.#room;
    }

    set item(value) {
        this.#item = value;
        if (value) {
            this.#itemElement.style.display = "block";
            this.#itemElement.style.background = `url(${value.image})`;
        } else {
            this.#itemElement.style.display = "none";
        }
        this.classList.toggle("room-world-has-item", value);
    }

    movePlayer(playerID, position) {
        let playerElement = this.#playerElements.get(playerID);
        if (!playerElement) {
            //playerElement = document.createElement("room-player");
            playerElement = new PlayerElement();
            playerElement.style.background = `url(${PLAYER_IMAGE})`;
            this.append(playerElement);
            this.#playerElements.set(playerID, playerElement);
        }
        console.log("SETTING POSITION", position);
        if (position.x === -1) {
            playerElement.remove();
            this.#playerElements.delete(playerID);
        } else {
            playerElement.position = position;
        }
    }

    #step() {
        requestAnimationFrame(this.#step.bind(this));

        //this.#player.position = Vector.add(this.#player.position, {x: 0.1, y: 0.1});

        if (this.#target) {
            let v = Vector.sub(this.#target, this.#player.position);
            const length = Vector.length(v);
            if (length > 1) {
                v = Vector.scale(v, 4 * 8 / 60 / length);
                //const toPos = Vector.add(this.#player.position, v);

                const xPos = {x: this.#player.position.x + v.x, y: this.#player.position.y};
                const yPos = {x: this.#player.position.x, y: this.#player.position.y + v.y};
                const xI = this.getIndex(xPos);
                const yI = this.getIndex(yPos);
                const xTile = this.#room.tiles[xI];
                const yTile = this.#room.tiles[yI];

                // move out of wall
                const i = this.getIndex(this.#player.position);

                //const fromI = this.getIndex(this.#player.position);
                //const toI = this.getIndex(toPos);
                //const to = this.#room.tiles[toI];
                //const xAxis = this.getPosition(toI).x - this.getPosition(fromI).x;
                //const yAxis = this.getPosition(toI).y - this.getPosition(fromI).y;

                this.#player.position = {
                    x: (xI !== i && xTile.wall) ? this.#player.position.x : xPos.x,
                    y: (yI !== i && yTile.wall) ? this.#player.position.y : yPos.y
                };
            }
        }

        // action selection
        if (!this.#room) {
            return;
        }
        let focus = null;
        let v = Vector.sub(this.#pointer, this.#player.position);
        const length = Vector.length(v);
        const i = this.getIndex(this.#pointer);
        const tile = this.#room.tiles[i];
        // if (tile.wall || this.#item) {
        if (this.#item) {
            const d = this.#mapDiv.children[i];
            if (length <= 2 * 8) {
                focus = d;
            }
        }

        if (this.#focusedDiv !== focus) {
            if (this.#focusedDiv) {
                this.#focusedDiv.classList.remove("room-world-focused");
                this.#focusedDiv = null;
            }
            if (focus)  {
                this.#focusedDiv = focus;
                this.#focusedDiv.classList.add("room-world-focused");
            }
        }
    }
}
customElements.define("room-world", WorldElement);

class WorkshopElement extends HTMLElement {
    #blueprints = null;
    #roomEditor;

    constructor() {
        super();
        this.blueprints = null;
        this.#roomEditor = document.querySelector("room-editor");
    }

    set blueprints(value) {
        this.#blueprints = value;
        if (this.#blueprints) {
            this.style.display = "flex";
            this.#renderBlueprints();
        } else {
            this.style.display = "none";
        }
    }

    get blueprints() {
        return this.#blueprints;
    }

    connectedCallback() {
        // Blueprints view
        this.querySelector(".room-workshop-create").addEventListener("click", () => {
            this.#roomEditor.blueprint = {id: ""};
        });
        this.querySelector(".room-workshop-back").addEventListener("click", () => {
            this.blueprints = null;
        });
    }

    #renderBlueprints() {
        const ul = this.querySelector("ul");
        for (let elem of ul.querySelectorAll(".bluerpint")) {
            elem.remove();
        }

        const template = document.querySelector("#blueprint-template");
        for (let blueprint of Object.values(this.#blueprints)) {
            let li = template.content.cloneNode(true).firstElementChild;
            li.querySelector("img").src = blueprint.image;
            li.dataset.tileID = blueprint.id;
            li.tabIndex = "0"
            li.addEventListener("click", event => {
                console.log("CLICK");
                //event.currentTarget;
                // const i = Array.from(ul.children).indexOf(event.currentTarget);
                //this.#roomEditor.blueprint = this.#blueprints[i];
                this.#roomEditor.blueprint = this.#blueprints[event.currentTarget.dataset.tileID];
            });
            ul.lastElementChild.before(li);
        }
    }
}
customElements.define("room-workshop", WorkshopElement);

class EditorElement extends HTMLElement {
    #blueprint = null;
    #canvas;
    #context = null;

    constructor() {
        super();

        const fieldset = this.querySelector("#colors");
        const template = document.querySelector("#color-template");

        let label = template.content.cloneNode(true);
        label.querySelector("span").classList.add("room-editor-erasor");
        label.querySelector("input").value = "";
        fieldset.append(label);

        for (let color of PALETTE) {
            let label = template.content.cloneNode(true);
            label.querySelector("span").style.backgroundColor = color;
            label.querySelector("input").value = color;
            fieldset.append(label);
        }
        fieldset.querySelector("input").checked = true;

        this.blueprint = null;
        this.#canvas = this.querySelector("canvas");
    }

    connectedCallback() {
        const fieldset = this.querySelector("#colors");
        let color = "#000";
        fieldset.addEventListener("click", event => {
            color = event.target.value;
            this.#context.fillStyle = color;
        });

        let pointerDown = false;
        this.#canvas.addEventListener("pointerdown", () => {
            pointerDown = true;
        });
        this.#canvas.addEventListener("pointerup", () => {
            pointerDown = false;
            this.querySelector("p").textContent = this.#canvas.toDataURL();
        });
        this.#canvas.addEventListener("pointermove", event => {
            if (pointerDown) {
                const x = Math.floor(event.offsetX / (this.#canvas.offsetWidth / 8));
                const y = Math.floor(event.offsetY / (this.#canvas.offsetHeight / 8));
                if (!color) {
                    this.#context.clearRect(x, y, 1, 1);
                } else {
                    this.#context.fillRect(x, y, 1, 1);
                }
            }
        });

        this.querySelector("form").addEventListener("submit", event => {
            event.preventDefault();

            // TODO send blueprint to server
            const gameElement = document.querySelector("room-game");
            const action = {
                type: "UpdateBlueprintAction",
                user_id: gameElement.userID,
                blueprint: {
                    id: this.#blueprint.id,
                    image: this.#canvas.toDataURL(),
                    wall: this.querySelector("[name=wall]").checked
                }
            };
            gameElement.run(action);
            //document.querySelector("room-game").onBlueprintUpdate(blueprint);
            this.blueprint = null;
        });
        this.querySelector("#editor-back").addEventListener("click", () => {
            this.blueprint = null;
        });
    }

    set blueprint(value) {
        this.#blueprint = value;
        if (value) {
            this.style.display = "block";
            this.#context = this.#canvas.getContext("2d");
            this.#context.clearRect(0, 0, this.#canvas.width, this.#canvas.height);
            this.querySelector("p").textContent = "";
            this.querySelector("[name=wall]").checked = value.wall;
            if (this.#blueprint.image) {
                const img = this.querySelector("img");
                img.src = this.#blueprint.image;
                this.#context.drawImage(img, 0, 0);
            }
        } else {
            this.style.display = "none";
            this.#context = null;
        }
    }
}
customElements.define("room-editor", EditorElement);
