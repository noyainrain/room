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

class GameElement extends HTMLElement {
    blueprints = [];
    #item = null;

    #worldElement;
    #workshopElement;
    #itemDiv;
    #black = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAFElEQVQYV2NkYGD4D8Q4AePIUAAAhWQIAUzZY7sAAAAASUVORK5CYII="

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
            this.scale = Math.floor(this.parentElement.offsetHeight / 64);
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
        setTimeout(() => {
            let room = JSON.parse(localStorage.room ?? "null");
            if (!room) {
                room = {
                    tiles: new Array(8 * 8).fill({image: this.#black, wall: false})
                };
            }
            this.#worldElement.room = room;

            //this.showWorkshop();
        }, 10);

        this.querySelector(".room-game-no-item").addEventListener("click", () => {
            this.item = null;
            this.toggleInventory();
        });

        this.querySelector(".room-game-item").addEventListener("click", () => {
            this.toggleInventory();
        });
    }

    set item(value) {
        this.#item = value;
        if (value) {
            this.#itemDiv.firstElementChild.src = value.image;
        } else {
            this.#itemDiv.firstElementChild.src = this.#black;
        }
        this.classList.toggle("room-world-has-item", value);
        this.#worldElement.item = value;
    }

    onBlueprintUpdate(blueprint) {
        this.blueprints.push(blueprint);
        localStorage.blueprints = JSON.stringify(this.blueprints);
        //this.#workshopElement.blueprints = this.blueprints;
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
        for (let blueprint of this.blueprints) {
            let li = template.content.cloneNode(true).firstElementChild;
            li.querySelector("img").src = blueprint.image;
            li.addEventListener("click", event => {
                const i = Array.from(ul.children).indexOf(event.currentTarget);
                console.log("I", i);

                this.item = this.blueprints[i - 1];
                div.style.display = "none";
            });
            ul.append(li);
        }
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
        const player = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAPklEQVQYV2NkIAAYkeVD////D+KvZmSEi8MZIMnVq1eD1YeGhsIVgRUgS8JMhCkiTgG6KRhWwI3F50hcvgUA66okCTKgZHUAAAAASUVORK5CYII="
        this.#player.style.background = `url(${player})`;
        this.#player.position = {x: 32, y: 32};

        //this.#player.addEventListener("click", () => {
        //    document.querySelector("room-game").toggleInventory();
        //});

        // const map = this.querySelector(".room-world-map");
        const map = document.querySelector("body");
        let pointerDown = false;
        const updateTarget = event => {
            this.#target = {
                x: Math.min(Math.max(event.clientX / this.#gameElement.scale, 0), 63),
                y: Math.min(Math.max(event.clientY / this.#gameElement.scale, 0), 63)
            };
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
                        this.#room.tiles[i] = this.#item;
                        // event.currentTarget.querySelector("img").src = this.#item.image;
                        this.querySelector(".room-world-map").children[i].querySelector("img").src = this.#item.image;
                        localStorage.room = JSON.stringify(this.#room);
                    } else {
                        window.alert("INTERACT");
                        // TODO change tile if it has an action attached
                        // -> build a door tile (open and closed)
                        // TODO add button for workshop
                        // TODO let player wobble a bit
                    }
                }
            }
            t = null;
            clearTimeout(timeout);
            this.#target = null;
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

                //const fromI = this.getIndex(this.#player.position);
                //const toI = this.getIndex(toPos);
                //const to = this.#room.tiles[toI];
                //const xAxis = this.getPosition(toI).x - this.getPosition(fromI).x;
                //const yAxis = this.getPosition(toI).y - this.getPosition(fromI).y;

                this.#player.position = {
                    x: xTile.wall ? this.#player.position.x : xPos.x,
                    y: yTile.wall ? this.#player.position.y : yPos.y
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
        if (tile.wall || this.#item) {
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
            this.style.display = "block";
            this.#renderBlueprints();
        } else {
            this.style.display = "none";
        }
    }

    connectedCallback() {
        // Blueprints view
        this.querySelector("button").addEventListener("click", () => {
            this.#roomEditor.blueprint = {};
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
        for (let blueprint of this.#blueprints) {
            let li = template.content.cloneNode(true).firstElementChild;
            li.querySelector("img").src = blueprint.image;
            li.addEventListener("click", event => {
                console.log("CLICK");
                //event.currentTarget;
                const i = Array.from(ul.children).indexOf(event.currentTarget);
                this.#roomEditor.blueprint = this.#blueprints[i];
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
        label.querySelector("span").textContent = "x";
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
            const blueprint = {
                image: this.#canvas.toDataURL(),
                wall: this.querySelector("[name=wall]").checked
            }
            document.querySelector("room-game").onBlueprintUpdate(blueprint);
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
