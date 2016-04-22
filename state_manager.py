import struct
import attr
import ssbm
import fields

def generic_wrapper(value, wrapper, default):
    if wrapper is not None:
        try:
            value = wrapper(value)
        except ValueError:
            value = default
    return value

intStruct = struct.Struct('>i')

byte_mask = 0xFF
short_mask = 0xFFFF
int_mask = 0xFFFFFFFF

@attr.s
class IntHandler:
    shift = attr.ib(default=0)
    mask = attr.ib(default=int_mask)
    wrapper = attr.ib(default=None)
    default = attr.ib(default=0)

    def __call__(self, value):
        transformed = (intStruct.unpack(value)[0] >> self.shift) & self.mask
        return generic_wrapper(transformed, self.wrapper, self.default)

intHandler = IntHandler()
byteHandler = IntHandler(shift=24, mask=byte_mask)
shortHandler = IntHandler(shift=16, mask=short_mask)

floatStruct = struct.Struct('>f')

@attr.s
class FloatHandler:
    wrapper = attr.ib(default=None)
    default = attr.ib(default=0.0)

    def __call__(self, value):
        as_float = floatStruct.unpack(value)[0]
        return generic_wrapper(as_float, self.wrapper, self.default)

floatHandler = FloatHandler()

@attr.s
class Handler:
    path = attr.ib()
    handler = attr.ib()

    def __call__(self, obj, value):
        fields.setPath(obj, self.path, self.handler(value))

def add_address(x, y):
    """Returns a string representation of the sum of the two parameters.

    x is a hex string address that can be converted to an int.
    y is an int.
    """
    return "{0:08X}".format(int(x, 16) + y)

# see https://docs.google.com/spreadsheets/d/1JX2w-r2fuvWuNgGb6D3Cs4wHQKLFegZe2jhbBuIhCG8

global_addresses = {}

global_addresses['80479D60'] = Handler(['frame'], intHandler)
global_addresses['80479D30'] = Handler(['menu'], IntHandler(mask=byte_mask))#, Menu, Menu.Characters)
global_addresses['804D6CAD'] = Handler(['stage'], shortHandler)#, Stage, Stage.Unselected)

def playerAddresses(player_id, addresses=None):
    if addresses is None:
        addresses = {}

    player_path = ['players', player_id]

    def playerHandler(field, handler):
        return Handler(player_path + [field], handler)

    cursor_x_address = add_address('81118DEC', -0xB80 * player_id)
    cursor_y_address = add_address('81118DF0', -0xB80 * player_id)
    addresses[cursor_x_address] = playerHandler('cursor_x', floatHandler)
    addresses[cursor_y_address] = playerHandler('cursor_y', floatHandler)

    type_address = add_address('803F0E08', 0x24 * player_id)
    type_handler = playerHandler('type', byteHandler) #, PlayerType, PlayerType.Unselected)
    character_handler = playerHandler('character', IntHandler(8, byte_mask)) #, Character, Character.Unselected)
    addresses[type_address] = [type_handler, character_handler]

    static_pointer = 0x80453080 + 0xE90 * player_id

    def add_static_address(offset, name, handler):
      address = "{0:08X}".format(static_pointer + offset)
      handle = playerHandler(name, handler)
      if address not in addresses:
        addresses[address] = [handle]
      else:
        addresses[address].append(handle)

    add_static_address(0x60, 'percent', shortHandler)
    # add_static_address(0x1890, 'percent', floatHandler)
    add_static_address(0x8E, 'stock', byteHandler)

    # nametag positions
    #add_static_address(0x10, 'x', float_handler)
    #add_static_address(0x14, 'y', float_handler)
    #add_static_address(0x18, 'z', float_handler)

    # hitbox positions
    add_static_address(0x18B4, 'x', floatHandler)
    add_static_address(0x18B8, 'y', floatHandler)
    add_static_address(0x18BC, 'z', floatHandler)

    data_pointer = add_address('80453130', 0xE90 * player_id)

    def add_data_address(offset, name, handler):
      address = data_pointer + ' ' + offset
      handle = playerHandler(name, handler)
      if address not in addresses:
        addresses[address] = [handle]
      else:
        addresses[address].append(handle)

    add_data_address('70', 'action_state', intHandler)#, wrapper=ActionState, default=ActionState.Unselected)
    add_data_address('20CC', 'action_counter', intHandler)
    add_data_address('8F4', 'action_frame', floatHandler)

    add_data_address('19EC', 'vulnerable', intHandler)

    add_data_address('19BC', 'hitlag_frames_left', floatHandler)
    add_data_address('23A0', 'hitstun_frames_left', floatHandler)
    add_data_address('2174', 'charging_smash', IntHandler(mask=0x2))

    add_data_address('19C8', 'jumps_used', byteHandler)
    add_data_address('140', 'in_air', intHandler)

    add_data_address('E0', 'speed_air_x_self', floatHandler)
    add_data_address('E4', 'speed_air_y_self', floatHandler)
    add_data_address('EC', 'speed_x_attack', floatHandler)
    add_data_address('F0', 'speed_y_attack', floatHandler)
    add_data_address('14C', 'speed_ground_x_self', floatHandler)

    add_data_address('8C', 'facing', floatHandler) # 1 is right, -1 is left
    add_data_address('1E4', 'speed_fastfall_self', floatHandler)

    return addresses

class StateManager:
    def __init__(self, player_ids=range(4)):
        self.addresses = global_addresses.copy()

        for player_id in player_ids:
            playerAddresses(player_id, self.addresses)

    def handle(self, obj, address, value):
        """Convert the raw address and value into changes in the State."""
        assert address in self.addresses
        handlers = self.addresses[address]
        if isinstance(handlers, list):
            for handler in handlers:
                handler(obj, value)
        else:
            handlers(obj, value)

    def locations(self):
        """Returns a list of addresses for exporting to Locations.txt."""
        return self.addresses.keys()
