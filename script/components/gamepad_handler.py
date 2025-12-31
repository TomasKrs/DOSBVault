import pygame
import threading
import time
import tkinter as tk

class GamepadHandler:
    def __init__(self, app):
        self.app = app
        self.running = False
        self.joystick = None
        self.thread = None
        self.last_action_time = 0
        self.action_cooldown = 0.2  # Seconds between actions to prevent scrolling too fast

    def start(self):
        try:
            pygame.init()
            pygame.joystick.init()
            self._scan_for_joystick()
            self.running = True
            self.thread = threading.Thread(target=self._input_loop, daemon=True)
            self.thread.start()
        except Exception as e:
            print(f"Failed to initialize gamepad: {e}")

    def _scan_for_joystick(self):
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            print(f"Gamepad detected: {self.joystick.get_name()}")
        else:
            print("No gamepad detected.")

    def _input_loop(self):
        while self.running:
            if not self.joystick:
                # Try to reconnect occasionally
                pygame.joystick.quit()
                pygame.joystick.init()
                if pygame.joystick.get_count() > 0:
                    self._scan_for_joystick()
                time.sleep(2)
                continue

            for event in pygame.event.get():
                if event.type == pygame.JOYBUTTONDOWN:
                    self._handle_button(event.button)
                elif event.type == pygame.JOYHATMOTION:
                    self._handle_hat(event.value)
                elif event.type == pygame.JOYAXISMOTION:
                    self._handle_axis(event.axis, event.value)

            time.sleep(0.01)

    def _handle_button(self, button):
        # Generic mapping (Xbox/PS style)
        # 0: A / Cross (Select/Launch)
        # 1: B / Circle (Back/Focus Tree)
        # 2: X / Square
        # 3: Y / Triangle
        
        current_time = time.time()
        if current_time - self.last_action_time < self.action_cooldown:
            return

        if button == 0: # A - Launch or Enter
            self.app.after(0, self._action_select)
        elif button == 1: # B - Back / Focus Tree
            self.app.after(0, self._action_focus_tree)
        
        self.last_action_time = current_time

    def _handle_hat(self, value):
        # D-Pad
        dx, dy = value
        if dy == 1: self.app.after(0, lambda: self._navigate_tree(-1)) # Up
        elif dy == -1: self.app.after(0, lambda: self._navigate_tree(1)) # Down
        
    def _handle_axis(self, axis, value):
        # Analog Stick (usually axis 1 is Left Stick Y)
        if axis == 1:
            if value < -0.5: self.app.after(0, lambda: self._navigate_tree(-1))
            elif value > 0.5: self.app.after(0, lambda: self._navigate_tree(1))

    def _navigate_tree(self, direction):
        current_time = time.time()
        if current_time - self.last_action_time < self.action_cooldown:
            return
            
        tree = self.app.library_panel.tree
        if not tree.get_children(): return

        selection = tree.selection()
        if not selection:
            # Select first item
            children = tree.get_children()
            if children:
                tree.selection_set(children[0])
                tree.see(children[0])
        else:
            current_id = selection[0]
            current_idx = tree.index(current_id)
            next_idx = current_idx + direction
            
            children = tree.get_children()
            if 0 <= next_idx < len(children):
                next_id = children[next_idx]
                tree.selection_set(next_id)
                tree.see(next_id)
        
        self.last_action_time = current_time

    def _action_select(self):
        # If tree has focus and item selected, launch it
        # Or if we want to simulate double click
        tree = self.app.library_panel.tree
        selection = tree.selection()
        if selection:
            self.app.launch_game(selection[0])

    def _action_focus_tree(self):
        self.app.library_panel.tree.focus_set()

    def stop(self):
        self.running = False
