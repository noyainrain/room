/** Game type definitions. */

/**
 * @typedef Player
 * @property {string} id
 */

/**
 * @typedef Member
 * @property {string} id
 * @property {string} player_id
 * @property {Player} player
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
 * @property {Member[]} members
 */

/**
 * @typedef FailedAction
 * @property {"FailedAction"} type
 * @property {string} member_id
 * @property {string} message
 */

/**
 * @typedef WelcomeAction
 * @property {"WelcomeAction"} type
 * @property {string} member_id
 * @property {Room} room
 */

/**
 * @typedef PlaceTileAction
 * @property {"PlaceTileAction"} type
 * @property {string} member_id
 * @property {number} tile_index
 * @property {string} blueprint_id
 */

/**
 * @typedef UseAction
 * @property {"UseAction"} type
 * @property {string} member_id
 * @property {number} tile_index
 * @property {Effect[]} effects
 */

/**
 * @typedef UpdateBlueprintAction
 * @property {"UpdateBlueprintAction"} type
 * @property {string} member_id
 * @property {Tile} blueprint
 */

/**
 * @typedef MoveMemberAction
 * @property {"MoveMemberAction"} type
 * @property {string} member_id
 * @property {[number, number]} position
 */

/** @typedef {
   FailedAction | WelcomeAction | PlaceTileAction | UseAction | UpdateBlueprintAction |
   MoveMemberAction
} Action */
