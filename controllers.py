# Python packages
from math import cos, sin, atan2, pi, fmod, radians
import operator
# Third-party packages
from pyglet.window import key
from pyglet.text import Label
# Modules from this project
from cameras import *
import globals
from globals import *
from gui import *
from model import *
from player import *
from savingsystem import *


# Define a simple function to create GLfloat arrays of floats:
def vec(*args):
    return (GLfloat * len(args))(*args)

class Controller(object):
    def __init__(self, window): 
        self.window = window

    def setup(self):            
        pass
        
    def update(self, dt):
        pass

    def set_2d(self):
        width, height = self.window.get_size()
        glDisable(GL_DEPTH_TEST)
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, width, 0, height, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        
    def push_handlers(self):
        self.setup()
        self.window.push_handlers(self)
        
    def pop_handlers(self):
        self.window.pop_handlers()

class MainMenuController(Controller):
    def __init__(self, window, show_gui=True):
        super(MainMenuController, self).__init__(window)
        self.batch = pyglet.graphics.Batch()
        self.group = pyglet.graphics.OrderedGroup(1)
        self.labels_group = pyglet.graphics.OrderedGroup(2)

        self.show_gui = show_gui

        image = pyglet.image.load(os.path.join('resources', 'textures', 'frame.png'))
        self.frame_rect = Rectangle(0, 0, image.width, image.height)
        self.frame = pyglet.sprite.Sprite(image.get_region(0, 0, image.width, image.height), batch=self.batch, group=pyglet.graphics.OrderedGroup(0))
        button_image = pyglet.image.load(os.path.join('resources', 'textures', 'button.png'))
        self.start_game = Button(0, 0, 160, 50, image=button_image, caption="Start game", batch=self.batch, group=self.group)
        self.exit_game = Button(0, 0, 160, 50, image=button_image, caption="Exit game", batch=self.batch, group=self.group)
        self.label = Label(APP_NAME, font_name='Arial', font_size=30, x=window.width/2, y=window.height - 10,
            anchor_x='center', anchor_y='top', color=(0, 0, 0, 255), batch=self.batch,
            group=self.labels_group)
        
    def clear(self):
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
    def on_mouse_press(self, x, y, button, modifiers):
        if self.start_game.hit_test(x, y):
            controller = GameController(self.window, show_gui=self.show_gui)
            self.window.switch_controller(controller)
            return pyglet.event.EVENT_HANDLED
        elif self.exit_game.hit_test(x, y):
            pyglet.app.exit()
            return pyglet.event.EVENT_HANDLED

    def on_resize(self, width, height):
        self.frame.x, self.frame.y = (width - self.frame.width) / 2, (height - self.frame.height) / 2
        self.label.y = self.frame.y + self.frame.height
        self.label.x = width / 2
        button_x = self.frame.x + (self.frame.width - self.start_game.width) / 2
        button_y = self.frame.y + (self.frame.height - self.start_game.height) / 2
        self.start_game.set_position(button_x, button_y)
        self.exit_game.set_position(button_x, button_y - self.start_game.height - 20)

    def on_draw(self):
        self.clear()
        glColor3d(1, 1, 1)
        self.set_2d()
        self.batch.draw()


class GameController(Controller):
    def __init__(self, window, show_gui=True):
        super(GameController, self).__init__(window)
        self.show_gui = show_gui
        self.sector = None
        self.time_of_day = 0.0
        self.count = 0
        self.clock = 6
        self.light_y = 1.0
        self.light_z = 1.0
        self.bg_red = 0.0
        self.bg_green = 0.0
        self.bg_blue = 0.0
        self.hour_deg = 15.0
        self.highlighted_block = None
        self.block_damage = 0
        self.crack = None
        self.mouse_pressed = False
        self.show_fog = config.getboolean('World', 'show_fog')
        self.last_key = None
        self.sorted = False
        self.key_inventory = config.getint('Controls', 'inventory')
        self.key_sound_up = config.getint('Controls', 'sound_up')
        self.key_sound_down = config.getint('Controls', 'sound_down')

    def update(self, dt):
        sector = sectorize(self.player.position)
        if sector != self.sector:
            self.model.change_sectors(self.sector, sector)
            # When the world is loaded, show every visible sector.
            if self.sector is None:
                self.model.process_entire_queue()
            self.sector = sector

        self.model.content_update(dt)

        m = 8
        df = min(dt, 0.2)
        for _ in xrange(m):
            self.player.update(df / m, self)
        if self.mouse_pressed:
            vector = self.player.get_sight_vector()
            block, previous = self.model.hit_test(self.player.position, vector, self.player.attack_range)
            if block:
                if self.highlighted_block != block:
                    self.set_highlighted_block(block)

            if self.highlighted_block:
                hit_block = self.model[self.highlighted_block]
                if hit_block.hardness >= 0:
                    self.block_damage += self.player.attack_power
                    if self.block_damage >= hit_block.hardness:
                        self.model.remove_block(self.player, self.highlighted_block)
                        self.set_highlighted_block(None)
                        if hit_block.drop_id is not None \
                                and self.player.add_item(hit_block.drop_id):
                            self.item_list.update_items()
                            self.inventory_list.update_items()
                else:
                    self.set_highlighted_block(None)
        self.update_time()
        self.camera.update(dt)

    def setup(self):            
        glClearColor(self.bg_red, self.bg_green, self.bg_blue, 1)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_LIGHT1)
        glEnable(GL_LIGHT2)
        glEnable(GL_CULL_FACE)
        glEnable(GL_BLEND)
        glEnable(GL_LINE_SMOOTH)

        if self.show_fog:
            glEnable(GL_FOG)
            glFogfv(GL_FOG_COLOR, vec(self.bg_red, self.bg_green, self.bg_blue, 1))
            glHint(GL_FOG_HINT, GL_DONT_CARE)
            glFogi(GL_FOG_MODE, GL_LINEAR)
            glFogf(GL_FOG_DENSITY, 0.35)
            glFogf(GL_FOG_START, 20.0)
            glFogf(GL_FOG_END, DRAW_DISTANCE) # 80)
            
        self.window.set_exclusive_mouse(True)
        self.focus_block = Block(width=1.05, height=1.05)
        self.earth = vec(0.8, 0.8, 0.8, 1.0)
        self.white = vec(1.0, 1.0, 1.0, 1.0)
        self.ambient = vec(1.0, 1.0, 1.0, 1.0)
        self.polished = GLfloat(100.0)
        self.crack_batch = pyglet.graphics.Batch()
        if DISABLE_SAVE and world_exists(game_dir, SAVE_FILENAME):
            open_world(self, game_dir, SAVE_FILENAME)
        else:
            self.model = Model()
            self.player = Player((0, 0, 0), (-20, 0), game_mode=GAMEMODE)
        if self.player.game_mode == 0:
            print('Game mode: Creative')
        if self.player.game_mode == 1:
            print('Game mode: Survival')
        self.item_list = ItemSelector(self, self.player, self.model)
        self.inventory_list = InventorySelector(self, self.player, self.model)
        self.item_list.on_resize(self.window.width, self.window.height)
        self.inventory_list.on_resize(self.window.width, self.window.height)
        self.camera = Camera3D(target=self.player)
        if self.show_gui:
            self.label = pyglet.text.Label(
                '', font_name='Arial', font_size=8, x=10, y=self.window.height - 10,
                anchor_x='left', anchor_y='top', color=(255, 255, 255, 255))
        pyglet.clock.schedule_interval_soft(self.model.process_queue, 1.0 / MAX_FPS)

    def update_time(self):
        """
        The idle function advances the time of day.
        The day has 24 hours, from sunrise to sunset and from sunrise to
        second sunset.
        The time of day is converted to degrees and then to radians.
        """

        if not self.window.exclusive:
            return

        time_of_day = self.time_of_day if self.time_of_day < 12.0 \
            else 24.0 - self.time_of_day

        if time_of_day <= 2.5:
            self.time_of_day += 1.0 / TIME_RATE
            time_of_day += 1.0 / TIME_RATE
            self.count += 1
        else:
            self.time_of_day += 20.0 / TIME_RATE
            time_of_day += 20.0 / TIME_RATE
            self.count += 1.0 / 20.0
        if self.time_of_day > 24.0:
            self.time_of_day = 0.0
            time_of_day = 0.0

        side = len(self.model.sectors) * 2.0

        self.light_y = 2.0 * side * sin(time_of_day * self.hour_deg * DEG_RAD)
        self.light_z = 2.0 * side * cos(time_of_day * self.hour_deg * DEG_RAD)
        if time_of_day <= 2.5:
            ambient_value = 1.0
        else:
            ambient_value = 1 - (time_of_day - 2.25) / 9.5
        self.ambient = vec(ambient_value, ambient_value, ambient_value, 1.0)

        # Calculate sky colour according to time of day.
        sin_t = sin(pi * time_of_day / 12.0)
        self.bg_red = 0.1 * (1.0 - sin_t)
        self.bg_green = 0.9 * sin_t
        self.bg_blue = min(sin_t + 0.4, 0.8)

        if fmod(self.count / 2, TIME_RATE) == 0:
            if self.clock == 18:
                self.clock = 6
            else:
                self.clock += 1

    def set_highlighted_block(self, block):
        self.highlighted_block = block
        self.block_damage = 0
        if self.crack:
            self.crack.delete()
        self.crack = None

    def save_to_file(self, compression=False):
        if DISABLE_SAVE:
            if compression:
                save_world(self, game_dir, SAVE_FILENAME)
            else:
                save_world(self, game_dir, SAVE_FILENAME, CLASSIC_SAVE_TYPE)

    def on_mouse_press(self, x, y, button, modifiers):
        if self.window.exclusive:
            vector = self.player.get_sight_vector()
            block, previous = self.model.hit_test(self.player.position, vector, self.player.attack_range)
            if button == pyglet.window.mouse.LEFT:
                if block:
                    self.mouse_pressed = True
                    self.set_highlighted_block(None)
            else:
                if previous:
                    hit_block = self.model[block]
                    if hit_block.density >= 1:
                        current_block = self.item_list.get_current_block()
                        if current_block is not None:
                            # if current block is an item,
                            # call its on_right_click() method to handle this event
                            if current_block.id >= ITEM_ID_MIN:
                                current_block.on_right_click()
                            else:
                                localx, localy, localz = map(operator.sub,previous,normalize(self.player.position))
                                if localx != 0 or localz != 0 or (localy != 0 and localy != -1):
                                    self.model.add_block(previous, current_block)
                                    self.item_list.remove_current_block()
                elif self.item_list.get_current_block() and self.item_list.get_current_block().regenerated_health != 0 and self.player.health < self.player.max_health:
                    self.player.change_health(self.item_list.get_current_block().regenerated_health)
                    self.item_list.get_current_block_item().change_amount(-1)
                    self.item_list.update_health()
                    self.item_list.update_items()
        else:
            self.window.set_exclusive_mouse(True)

    def on_mouse_release(self, x, y, button, modifiers):
        if self.window.exclusive:
            self.set_highlighted_block(None)
            self.mouse_pressed = False

    def on_mouse_motion(self, x, y, dx, dy):
        if self.window.exclusive:
            m = 0.15
            x, y = self.player.rotation
            x, y = x + dx * m, y + dy * m
            y = max(-90, min(90, y))
            self.player.rotation = (x, y)
            self.camera.rotate(x, y)

    def on_mouse_drag(self, x, y, dx, dy, button, modifiers):
        if button == pyglet.window.mouse.LEFT:
            self.on_mouse_motion(x, y, dx, dy)

    def on_key_press(self, symbol, modifiers):
        if symbol == key.B or symbol == key.F3:
            self.show_gui = not self.show_gui
        elif symbol == key.V:
            self.save_to_file()
        elif symbol == key.M:
            if self.last_key == symbol and not self.sorted:
                self.player.quick_slots.sort()
                self.player.inventory.sort()
                self.sorted = True
            else:
                self.player.quick_slots.change_sort_mode()
                self.player.inventory.change_sort_mode()
                self.item_list.update_items()
                self.inventory_list.update_items()
        elif symbol == self.key_inventory:
            self.set_highlighted_block(None)
            self.mouse_pressed = False
            self.inventory_list.toggle()
        elif symbol == self.key_sound_up:
            globals.EFFECT_VOLUME = min(globals.EFFECT_VOLUME + .1, 1)
        elif symbol == self.key_sound_down:
            globals.EFFECT_VOLUME = max(globals.EFFECT_VOLUME - .1, 0)
        self.last_key = symbol

    def on_resize(self, width, height):
        if self.show_gui:
            self.label.y = height - 10

    def set_3d(self):
        width, height = self.window.get_size()
        if self.show_fog:
            glFogfv(GL_FOG_COLOR, vec(self.bg_red, self.bg_green, self.bg_blue, 1.0))
        glEnable(GL_DEPTH_TEST)
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        if width != float(height):
            gluPerspective(FOV, width / float(height), NEAR_CLIP_DISTANCE,
                           FAR_CLIP_DISTANCE)
        else:
            gluPerspective(FOV, 1, NEAR_CLIP_DISTANCE, FAR_CLIP_DISTANCE)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        self.camera.transform()
        glEnable(GL_LIGHTING)
        glLightfv(GL_LIGHT0, GL_DIFFUSE, vec(0.9, 0.9, 0.9, 1.0))
        glLightfv(GL_LIGHT0, GL_SPECULAR, vec(0.9, 0.9, 0.9, 1.0))
        glLightfv(GL_LIGHT0, GL_POSITION,
                  vec(1.0, self.light_y, self.light_z, 1.0))
        glLightfv(GL_LIGHT1, GL_AMBIENT, self.ambient)
        glLightfv(GL_LIGHT2, GL_AMBIENT, self.ambient)
        glMaterialfv(GL_FRONT, GL_AMBIENT, self.earth)
        glMaterialfv(GL_FRONT, GL_DIFFUSE, self.white)
        glMaterialfv(GL_FRONT, GL_SHININESS, self.polished)
        
    def clear(self):
        glClearColor(self.bg_red, self.bg_green, self.bg_blue, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    def on_draw(self):
        self.clear()
        self.set_3d()
        glColor3d(1, 1, 1)
        self.model.batch.draw()
        self.crack_batch.draw()
        self.draw_focused_block()
        self.set_2d()
        if self.show_gui:
            self.draw_label()
            self.item_list.draw()
            self.inventory_list.draw()

    def draw_focused_block(self):
        glDisable(GL_LIGHTING)
        vector = self.player.get_sight_vector()
        position = self.model.hit_test(self.player.position, vector, self.player.attack_range)[0]
        if position:
            hit_block = self.model[position]
            if hit_block.density >= 1:
                self.focus_block.width = hit_block.width * 1.05
                self.focus_block.height = hit_block.height * 1.05
                vertex_data = self.focus_block.get_vertices(*position)
                glColor3d(0, 0, 0)
                glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
                pyglet.graphics.draw(24, GL_QUADS, ('v3f/static', vertex_data))
                glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
                if self.block_damage == 0:
                    pass
                else:   # also show the cracks
                    crack_level = int(floor((self.block_damage / hit_block.hardness) * CRACK_LEVEL)) # range: [0, CRACK_LEVEL]
                    if crack_level > CRACK_LEVEL:
                        return
                    texture_data = crack_textures.texture_data[crack_level]
                    if self.crack:
                        self.crack.delete()
                    self.crack = self.crack_batch.add(24, GL_QUADS, self.model.group, ('v3f/static', vertex_data) ,
                                                                            ('t2f/static', texture_data))

    def draw_label(self):
        x, y, z = self.player.position
        self.label.text = '%.1f %02d (%.2f, %.2f, %.2f) %d / %d' \
            % (self.time_of_day if (self.time_of_day < 12.0)
               else (24.0 - self.time_of_day),
               pyglet.clock.get_fps(), x, y, z,
               len(self.model._shown), len(self.model))
        self.label.draw()
        
    def push_handlers(self):
        self.setup()
        self.window.push_handlers(self.camera)
        self.window.push_handlers(self.player)
        self.window.push_handlers(self)
        self.window.push_handlers(self.item_list)
        self.window.push_handlers(self.inventory_list)
        
    def pop_handlers(self):
        self.window.pop_handlers()
        self.window.pop_handlers()
        self.window.pop_handlers()
        self.window.pop_handlers()
        self.window.pop_handlers()
