/** Core concepts. */

/**
 * @typedef Player
 * @property {string} id
 * @property {[number, number]} position
 */

/**
 * @typedef Tile
 * @property {string} id
 * @property {string} image
 * @property {boolean} wall
 */

/**
 * @typedef Room
 * @property {string} id
 * @property {string[]} tile_ids
 * @property {Object<string, Tile>} blueprints
 * @property {string} version
 * @property {Object<string, Player>} players
 */

/**
 * @typedef FailedAction
 * @property {"FailedAction"} type
 * @property {string} player_id
 * @property {string} message
 */

/**
 * @typedef WelcomeAction
 * @property {"WelcomeAction"} type
 * @property {string} player_id
 * @property {Room} room
 */

/**
 * @typedef UseAction
 * @property {"UseAction"} type
 * @property {string} player_id
 * @property {number} tile_index
 * @property {string} item_id
 */

/**
 * @typedef UpdateBlueprintAction
 * @property {"UpdateBlueprintAction"} type
 * @property {string} player_id
 * @property {Tile} blueprint
 */

/**
 * @typedef MovePlayerAction
 * @property {"MovePlayerAction"} type
 * @property {string} player_id
 * @property {[number, number]} position
 */

/**
 * @typedef {FailedAction | WelcomeAction | UseAction | UpdateBlueprintAction | MovePlayerAction}
 *     Action
 */
