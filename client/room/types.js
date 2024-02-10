/** Game type definitions. */

/**
 * @typedef Player
 * @property {string} id
 * @property {[number, number]} position
 */

/**
 * @typedef UseCause
 * @property {"UseCause"} type
 */

/**
 * @typedef TransformTileEffect
 * @property {"TransformTileEffect"} type
 * @property {string} blueprint_id
 */

/** @typedef {UseCause} Cause */

/** @typedef {TransformTileEffect} Effect */

/**
 * @typedef Tile
 * @property {string} id
 * @property {string} image
 * @property {boolean} wall
 * @property {[Cause, Effect[]][]} effects
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
 * @typedef PlaceTileAction
 * @property {"PlaceTileAction"} type
 * @property {string} player_id
 * @property {number} tile_index
 * @property {string} blueprint_id
 */

/**
 * @typedef UseAction
 * @property {"UseAction"} type
 * @property {string} player_id
 * @property {number} tile_index
 * @property {Effect[]} effects
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

/** @typedef {
   FailedAction | WelcomeAction | PlaceTileAction | UseAction | UpdateBlueprintAction |
   MovePlayerAction
} Action */
