/** Game type definitions. */

// Use intersection to work around TypeScript not supporting typedef inheritance (see
// https://github.com/microsoft/TypeScript/issues/20077)

/**
 * @typedef Player
 * @property {string} id
 */

/**
 * @typedef PrivatePlayerProperties
 * @property {string} token
 * @property {boolean} tutorial
 * @typedef {PrivatePlayerProperties & Player} PrivatePlayer
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
 * @typedef OtherCause
 * @property {"*"} type
 */

/**
 * @typedef TransformTileEffect
 * @property {"TransformTileEffect"} type
 * @property {string} blueprint_id
 */

/**
 * @typedef OtherEffect
 * @property {"*"} type;
 */

/** @typedef {UseCause | OtherCause} Cause */

/** @typedef {TransformTileEffect | OtherEffect} Effect */

/**
 * @typedef Tile
 * @property {string} id
 * @property {string} image
 * @property {boolean} wall
 * @property {[Cause, Effect[]][]} effects
 */

/**
 * @typedef BaseRoom
 * @property {string} id
 * @property {string} title
 * @property {?string} description
 */

/**
 * @typedef RoomProperties
 * @property {string[]} tile_ids
 * @property {Object<string, Tile>} blueprints
 * @property {string} version
 * @property {Member[]} members
 * @typedef {RoomProperties & BaseRoom} Room
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
 * @typedef UpdateRoomAction
 * @property {"UpdateRoomAction"} type
 * @property {string} member_id
 * @property {BaseRoom} room
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
   FailedAction | WelcomeAction | UpdateRoomAction | PlaceTileAction | UseAction |
   UpdateBlueprintAction | MoveMemberAction
} Action */
