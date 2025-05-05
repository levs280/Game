import pygame
import sys
import random
import math
from collections import deque
import time
import numpy as np

pygame.init()

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Mirror Knights - Adaptive Boss Fight")

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
PURPLE = (128, 0, 128)
DARK_GRAY = (20, 20, 20)
LIGHT_GRAY = (200, 200, 200)
ORANGE = (255, 165, 0)
CYAN = (0, 255, 255)
YELLOW = (255, 255, 0)

clock = pygame.time.Clock()
FPS = 60

font_small = pygame.font.Font(None, 24)
font_medium = pygame.font.Font(None, 32)
font_large = pygame.font.Font(None, 48)

try:
    player_attack_sound = pygame.mixer.Sound("player_attack.wav")
    player_dash_sound = pygame.mixer.Sound("player_dash.wav")
    hit_sound = pygame.mixer.Sound("hit.wav")
    game_over_sound = pygame.mixer.Sound("game_over.wav")
    victory_sound = pygame.mixer.Sound("victory.wav")
    phase_change_sound = pygame.mixer.Sound("phase_change.wav")
    boss_attack_sound = pygame.mixer.Sound("boss_attack.wav")
    boss_dash_sound = pygame.mixer.Sound("boss_dash.wav")
    projectile_sound = pygame.mixer.Sound("projectile.wav")
    hazard_sound = pygame.mixer.Sound("hazard.wav")
    laser_sound = pygame.mixer.Sound("hazard.wav")  
except FileNotFoundError:
    dummy_array = np.zeros((44100, 2), dtype=np.int16)
    dummy_sound = pygame.mixer.Sound(pygame.sndarray.make_sound(dummy_array))
    player_attack_sound = dummy_sound
    player_dash_sound = dummy_sound
    hit_sound = dummy_sound
    game_over_sound = dummy_sound
    victory_sound = dummy_sound
    phase_change_sound = dummy_sound
    boss_attack_sound = dummy_sound
    boss_dash_sound = dummy_sound
    projectile_sound = dummy_sound
    hazard_sound = dummy_sound
    laser_sound = dummy_sound

class ParticleSystem:
    def __init__(self):
        self.particles = []
    
    def add_particles(self, x, y, color, count=5, speed=2, size_range=(2, 5), lifetime_range=(30, 60)):
        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            speed_val = random.uniform(1, speed)
            size = random.randint(size_range[0], size_range[1])
            lifetime = random.randint(lifetime_range[0], lifetime_range[1])
            
            if len(color) > 3:  
                color = color[:3]
            
            self.particles.append({
                'x': x,
                'y': y,
                'vx': math.cos(angle) * speed_val,
                'vy': math.sin(angle) * speed_val,
                'size': size,
                'color': color,
                'lifetime': lifetime,
                'max_lifetime': lifetime
            })
    
    def update(self):
        self.particles = [particle for particle in self.particles if particle['lifetime'] > 0]
        
        for particle in self.particles:
            particle['x'] += particle['vx']
            particle['y'] += particle['vy']
            particle['lifetime'] -= 1
    
    def draw(self, surface):
        for particle in self.particles:
            alpha = particle['lifetime'] / particle['max_lifetime']
            color = particle['color']
            if len(color) == 3:
                faded_color = tuple(int(c * alpha) for c in color)
            else:
                faded_color = tuple(int(c * alpha) for c in color[:3])
                
            pygame.draw.circle(
                surface, 
                faded_color,
                (int(particle['x']), int(particle['y'])), 
                particle['size']
            )

class Projectile:
    def __init__(self, x, y, target_x, target_y, speed, size, color, damage, homing=False, lifetime=180):
        self.x = x
        self.y = y
        
        dx = target_x - x
        dy = target_y - y
        distance = max(1, math.sqrt(dx*dx + dy*dy))  
        self.vx = (dx / distance) * speed
        self.vy = (dy / distance) * speed
        
        self.size = size
        self.color = color
        self.damage = damage
        self.lifetime = lifetime
        self.homing = homing
        self.homing_strength = 0.08  
        self.particles = ParticleSystem()
    
    def update(self, player=None):
        self.x += self.vx
        self.y += self.vy
        
        if self.homing and player:
            dx = player.x + player.width/2 - self.x
            dy = player.y + player.height/2 - self.y
            distance = max(1, math.sqrt(dx*dx + dy*dy))
            
            self.vx += (dx / distance) * self.homing_strength
            self.vy += (dy / distance) * self.homing_strength
            
            velocity_magnitude = math.sqrt(self.vx*self.vx + self.vy*self.vy)
            if velocity_magnitude > 0:
                self.vx = self.vx / velocity_magnitude * 5  
                self.vy = self.vy / velocity_magnitude * 5
        
        self.lifetime -= 1
        
        if random.random() < 0.3:
            self.particles.add_particles(
                self.x, self.y,
                self.color,
                count=2,
                speed=1,
                size_range=(1, 3),
                lifetime_range=(10, 20)
            )
            
        self.particles.update()
        
        return (self.lifetime <= 0 or 
                self.x < -50 or self.x > SCREEN_WIDTH + 50 or 
                self.y < -50 or self.y > SCREEN_HEIGHT + 50)
    
    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.size)
        
        self.particles.draw(surface)
    
    def get_rect(self):
        return pygame.Rect(self.x - self.size, self.y - self.size, self.size * 2, self.size * 2)

class ArenaHazard:
    def __init__(self, x, y, width, height, hazard_type, damage, lifetime=120, warning_time=60):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.type = hazard_type  
        self.damage = damage
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.warning_time = warning_time
        self.active = False
        self.particles = ParticleSystem()
        
        self.colors = {
            'spike': (150, 150, 150),  
            'fire': (255, 100, 0),     
            'poison': (0, 180, 0),
            'laser': (255, 0, 0),
        }

        
        self.moving = False
        self.vel_x = 0
        self.vel_y = 0
    
    def update(self):
        self.lifetime -= 1
        
        if self.lifetime <= self.max_lifetime - self.warning_time and not self.active:
            self.active = True
            hazard_sound.play()
        
        
        if self.moving and self.active:
            self.x += self.vel_x
            self.y += self.vel_y
            
            
            if self.x <= 0 or self.x + self.width >= SCREEN_WIDTH:
                self.vel_x *= -1
            if self.y <= 0 or self.y + self.height >= SCREEN_HEIGHT - 100:
                self.vel_y *= -1
        
        if self.active and random.random() < 0.2:
            self.particles.add_particles(
                self.x + random.uniform(0, self.width),
                self.y + random.uniform(0, self.height),
                self.colors[self.type],
                count=3,
                speed=2,
                size_range=(2, 5),
                lifetime_range=(10, 30)
            )
        
        self.particles.update()
        
        return self.lifetime <= 0
    
    def draw(self, surface):
        if not self.active:
            if (self.max_lifetime - self.lifetime) % 10 < 5:
                alpha = 0.8
            else:
                alpha = 0.3
            color = (255, 0, 0)  
        else:
            alpha = 0.7
            color = self.colors[self.type]
        
        hazard_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        hazard_color = (*color, int(255 * alpha))
        pygame.draw.rect(hazard_surface, hazard_color, (0, 0, self.width, self.height))
        
        surface.blit(hazard_surface, (self.x, self.y))
        
        pygame.draw.rect(surface, color, (self.x, self.y, self.width, self.height), 2)
        
        self.particles.draw(surface)
    
    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

class Laser:
    def __init__(self, x, y, speed, damage, lifetime=180, warning_time=60):
        self.x = x
        self.y = y
        self.speed = speed
        self.damage = damage
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.warning_time = warning_time
        self.active = False
        self.particles = ParticleSystem()
        self.warning_shown = False  
        
       
        self.width = 10
        self.height = SCREEN_HEIGHT - 100
    
    def update(self):
        self.lifetime -= 1
        
        if self.lifetime <= self.max_lifetime - self.warning_time and not self.active:
            self.active = True
            self.warning_shown = True  
            laser_sound.play()
        
        
        if self.active:
            self.x += self.speed
            if self.x < 0 or self.x + self.width > SCREEN_WIDTH:
                self.speed *= -1
        
        
        if self.active and random.random() < 0.3:
            particle_x = self.x + self.width / 2
            particle_y = random.uniform(self.y, self.y + self.height)
                
            self.particles.add_particles(
                particle_x, particle_y,
                (255, 0, 0),  
                count=2,
                speed=1,
                size_range=(1, 3),
                lifetime_range=(5, 15)
            )
        
        self.particles.update()
        
        return self.lifetime <= 0
    
    def draw(self, surface):
        if not self.active:
            
            if (self.max_lifetime - self.lifetime) % 10 < 5:
                alpha = 0.4
            else:
                alpha = 0.1
                
            laser_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            color = (255, 0, 0, int(255 * alpha))  
            pygame.draw.rect(laser_surface, color, (0, 0, self.width, self.height))
            
            surface.blit(laser_surface, (self.x, self.y))
            
            
            pygame.draw.rect(surface, (255, 0, 0), (self.x, self.y, self.width, self.height), 1)
        else:
            
            laser_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            color = (255, 0, 0, 150)  
            pygame.draw.rect(laser_surface, color, (0, 0, self.width, self.height))
            
            surface.blit(laser_surface, (self.x, self.y))
            
            
            pygame.draw.line(surface, (255, 200, 200), 
                            (self.x + self.width//2, self.y), 
                            (self.x + self.width//2, self.y + self.height), 3)
        
        self.particles.draw(surface)
    
    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

class Boss:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 40
        self.height = 50
        self.vel_x = 0
        self.vel_y = 0
        self.base_speed = 4
        self.speed = self.base_speed
        self.jump_power = -12
        self.gravity = 0.6
        self.is_jumping = False
        self.on_ground = False
        self.health = 100
        self.max_health = 100
        self.attack_cooldown = 0
        self.attack_cooldown_max = 10
        self.base_attack_cooldown = 10
        self.dash_cooldown = 0
        self.dash_cooldown_max = 60
        self.base_dash_cooldown = 60
        self.dash_duration = 0
        self.dash_duration_max = 10
        self.dash_speed = 12
        self.dash_direction = 0
        self.invincibility = 0
        self.attacking = False
        self.facing_right = False
        self.learning_timer = 0
        self.learning_timer_max = 1200  
        self.adaptation_phase = 0
        self.adaptations = []
        self.max_adaptations = 3
        self.current_adaptation_text = ""
        self.adaptation_display_time = 0
        self.particles = ParticleSystem()
        
        
        self.decision_timer = 0
        self.decision_timer_max = 30
        self.current_decision = 'idle'
        self.target_x = 0
        self.aggression = 0.5
        self.aerial_preference = 0.5
        self.dash_frequency = 0.2
        self.attack_distance = 70
        self.retreat_distance = 40
        self.phase_transition = False
        self.phase_transition_timer = 0
        self.phase_messages = [
            "I see your patterns...",
            "Your style is transparent to me...",
            "Time to change the rhythm...",
            "Adapting to your weaknesses..."
        ]
        self.current_phase_message = ""
        self.attack_delay = 0
        self.dash_preference = 1.0
        self.tracking_intensity = 0.5
        self.playerAttackPattern = []
        self.patternFrequency = {}
        
        
        self.phase = 1
        self.phase_shift_threshold = [0.75, 0.5, 0.25]  
        self.phase_shifting = False
        self.phase_shift_timer = 0
        self.phase_shift_duration = 600  
        self.phase_shift_invulnerable = False
        self.is_visible = True
        self.reappear_portal_active = False
        self.reappear_portal_timer = 0
        self.reappear_portal_duration = 60  
        
        self.projectiles = []
        self.projectile_cooldown = 0
        self.projectile_patterns = [
            'single',      
            'triple',      
            'circle',      
            'homing',      
            'barrage'      
        ]
        self.current_projectile_pattern = 'single'
        self.projectile_cooldown_max = 180  
        self.barrage_count = 0
        self.barrage_timer = 0
        
        
        self.hazards = []
        self.hazard_cooldown = 0
        self.hazard_cooldown_max = 300  
        self.hazard_types = ['spike', 'fire', 'poison']
        self.hazard_patterns = [
            'random',     
            'targeted',   
            'grid',       
            'walls'       
        ]
        self.current_hazard_pattern = 'random'
        
        
        self.lasers = []

    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def get_attack_rect(self):
        if not self.attacking:
            return None
        
        attack_width = 50
        attack_height = 25
        attack_x = self.x + self.width if self.facing_right else self.x - attack_width
        attack_y = self.y + 10
        return pygame.Rect(attack_x, attack_y, attack_width, attack_height)

    def take_damage(self, amount):
        if self.phase_shifting and self.phase_shift_invulnerable:
            return False
        
        clamped_damage = min(amount, 10)
        
        if self.invincibility <= 0:
            prev_health_percentage = self.health / self.max_health
            
            self.health -= clamped_damage
            self.invincibility = 40
            hit_sound.play()
            
            self.particles.add_particles(
                self.x + self.width // 2,
                self.y + self.height // 2,
                RED,
                count=15,
                speed=3,
                size_range=(2, 6),
                lifetime_range=(20, 40)
            )
            
            current_health_percentage = self.health / self.max_health
            for threshold in self.phase_shift_threshold:
                if prev_health_percentage > threshold and current_health_percentage <= threshold:
                    self.initiate_phase_shift()
                    break
                    
            return True
        return False

    def initiate_phase_shift(self):
        if not self.phase_shifting:
            self.phase_shifting = True
            self.phase_shift_timer = 0
            self.phase_shift_invulnerable = True
            self.phase += 1
            self.is_visible = False
            self.reappear_portal_active = False
            
            
            self.create_phase_shift_lasers()
            
            self.speed += 0.5
            self.aggression += 0.1
            self.attack_cooldown_max = max(5, self.attack_cooldown_max - 2)
            self.dash_cooldown_max = max(30, self.dash_cooldown_max - 10)
            
            
            self.hazard_cooldown_max = max(150, self.hazard_cooldown_max - 50)
            
            if self.phase == 2:
                self.current_projectile_pattern = 'triple'
                self.current_hazard_pattern = 'targeted'
            elif self.phase == 3:
                self.current_projectile_pattern = 'homing'
                self.current_hazard_pattern = 'grid'
            elif self.phase >= 4:
                self.current_projectile_pattern = 'barrage'
                self.current_hazard_pattern = 'walls'
                
            phase_change_sound.play()
            
            self.current_phase_message = f"Phase {self.phase}: {random.choice(self.phase_messages)}"
            self.adaptation_display_time = 180  
    
    def create_phase_shift_lasers(self):
       
        self.hazards.clear()
        self.lasers.clear()
        self.projectiles.clear()
        
       
        num_lasers = min(4, 2 + self.phase)  
        for _ in range(num_lasers):
            x = random.randint(50, SCREEN_WIDTH - 100)
            speed = random.choice([-4, -3, 3, 4])  
                
            laser = Laser(x, 0, speed, 10, lifetime=self.phase_shift_duration, warning_time=30)
            self.lasers.append(laser)

    def create_phase_shift_hazards(self):
       
        pass

    def fire_projectile(self, player, pattern=None):
        if pattern is None:
            pattern = self.current_projectile_pattern
            
        projectile_sound.play()
        
        center_x = self.x + self.width / 2
        center_y = self.y + self.height / 2
        player_center_x = player.x + player.width / 2
        player_center_y = player.y + player.height / 2
        
        if pattern == 'single':
            self.projectiles.append(
                Projectile(center_x, center_y, player_center_x, player_center_y, 
                          6, 8, PURPLE, 10, homing=False)
            )
            
        elif pattern == 'triple':
            angle_to_player = math.atan2(player_center_y - center_y, player_center_x - center_x)
            angles = [angle_to_player - 0.3, angle_to_player, angle_to_player + 0.3]
            
            for angle in angles:
                target_x = center_x + math.cos(angle) * 300
                target_y = center_y + math.sin(angle) * 300
                self.projectiles.append(
                    Projectile(center_x, center_y, target_x, target_y, 
                              5, 6, PURPLE, 8, homing=False)
                )
                
        elif pattern == 'circle':
            for i in range(8):
                angle = i * (math.pi * 2 / 8)
                target_x = center_x + math.cos(angle) * 300
                target_y = center_y + math.sin(angle) * 300
                self.projectiles.append(
                    Projectile(center_x, center_y, target_x, target_y, 
                              4, 5, PURPLE, 6, homing=False)
                )
                
        elif pattern == 'homing':
            self.projectiles.append(
                Projectile(center_x, center_y, player_center_x, player_center_y, 
                          3, 10, CYAN, 15, homing=True, lifetime=300)
            )
            
        elif pattern == 'barrage':
            self.barrage_count = 3
            self.barrage_timer = 15  
            self.fire_projectile(player, 'triple')

    def create_hazard(self, player, pattern=None):
        if pattern is None:
            pattern = self.current_hazard_pattern
            
        hazard_sound.play()
        
        player_center_x = player.x + player.width / 2
        player_center_y = player.y + player.height / 2
        
        if pattern == 'random':
            hazard_type = random.choice(self.hazard_types)
            
            while True:
                x = random.randint(50, SCREEN_WIDTH - 150)
                y = SCREEN_HEIGHT - 100 - random.randint(10, 60)
                
                if abs(x - player_center_x) > 100 or abs(y - player_center_y) > 80:
                    break
                    
            width = random.randint(60, 120)
            height = random.randint(20, 40)
            
            self.hazards.append(
                ArenaHazard(x, y - height, width, height, hazard_type, 15)
            )
            
        elif pattern == 'targeted':
            hazard_type = random.choice(self.hazard_types)
            offset_x = random.randint(-50, 50)
            
            x = max(0, min(SCREEN_WIDTH - 100, player_center_x - 50 + offset_x))
            y = SCREEN_HEIGHT - 100  
            
            self.hazards.append(
                ArenaHazard(x, y - 40, 100, 40, hazard_type, 15)
            )
            
        elif pattern == 'grid':
            hazard_type = random.choice(self.hazard_types)
            section_width = SCREEN_WIDTH // 3
            
            for i in range(3):
                player_section = int(player_center_x / section_width)
                if i == player_section:
                    continue
                    
                x = i * section_width
                y = SCREEN_HEIGHT - 100 
                
                self.hazards.append(
                    ArenaHazard(x, y - 40, section_width, 40, hazard_type, 15)
                )
                
        elif pattern == 'walls':
            hazard_type = random.choice(self.hazard_types)
            
            if player_center_x < SCREEN_WIDTH / 2:
                x = SCREEN_WIDTH - 80
                width = 80
            else:
                x = 0
                width = 80
                
            self.hazards.append(
                ArenaHazard(x, 0, width, SCREEN_HEIGHT - 100, hazard_type, 20, lifetime=180, warning_time=90)
            )

    def move(self, player):
        self.learning_timer += 1
        if self.learning_timer >= self.learning_timer_max:
            self.learning_timer = 0
            self.adapt_to_player(player)
            phase_change_sound.play()
            
        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1
            if self.attack_cooldown <= self.attack_cooldown_max - 5:
                self.attacking = False
                
        if self.dash_cooldown > 0:
            self.dash_cooldown -= 1
            
        if self.invincibility > 0:
            self.invincibility -= 1
            
        if self.adaptation_display_time > 0:
            self.adaptation_display_time -= 1
            
        if self.projectile_cooldown > 0:
            self.projectile_cooldown -= 1
            
        if self.barrage_count > 0 and self.barrage_timer > 0:
            self.barrage_timer -= 1
            if self.barrage_timer <= 0:
                self.barrage_timer = 15  
                self.barrage_count -= 1
                self.fire_projectile(player, 'triple')
                
        if self.hazard_cooldown > 0:
            self.hazard_cooldown -= 1
            
        if self.phase_shifting:
            self.update_phase_shift()
            return  
        
        self.decision_timer -= 1
        if self.decision_timer <= 0:
            self.ai_decision(player)
            self.decision_timer = self.decision_timer_max
            
        if self.current_decision == 'chase':
            self.vel_x = self.speed * (1 if player.x > self.x else -1)
            self.facing_right = player.x > self.x
        elif self.current_decision == 'retreat':
            self.vel_x = self.speed * (-1 if player.x > self.x else 1)
            self.facing_right = player.x > self.x
        elif self.current_decision == 'attack':
            if self.attack_cooldown <= 0:
                self.attacking = True
                self.attack_cooldown = self.attack_cooldown_max
                boss_attack_sound.play()
        elif self.current_decision == 'dash':
            if self.dash_cooldown <= 0:
                self.dash_duration = self.dash_duration_max
                self.dash_cooldown = self.dash_cooldown_max
                self.dash_direction = 1 if player.x > self.x else -1
                boss_dash_sound.play()
        elif self.current_decision == 'projectile':
            if self.projectile_cooldown <= 0:
                self.fire_projectile(player)
                self.projectile_cooldown = self.projectile_cooldown_max
        elif self.current_decision == 'hazard':
            if self.hazard_cooldown <= 0:
                self.create_hazard(player)
                self.hazard_cooldown = self.hazard_cooldown_max
        
        if self.dash_duration > 0:
            self.dash_duration -= 1
            self.vel_x = self.dash_direction * self.dash_speed
            self.vel_y = 0
            self.particles.add_particles(
                self.x + (self.width if self.dash_direction > 0 else 0),
                self.y + self.height // 2,
                BLUE,
                count=3,
                speed=1,
                size_range=(2, 4),
                lifetime_range=(10, 20)
            )
            
        self.x += self.vel_x
        
        if not self.on_ground:
            self.vel_y += self.gravity
            self.y += self.vel_y
        
        if self.y >= SCREEN_HEIGHT - 100 - self.height:
            self.y = SCREEN_HEIGHT - 100 - self.height
            self.on_ground = True
            self.vel_y = 0
        else:
            self.on_ground = False
            
        if self.x < 0:
            self.x = 0
            self.vel_x = 0
        elif self.x > SCREEN_WIDTH - self.width:
            self.x = SCREEN_WIDTH - self.width
            self.vel_x = 0
            
        i = 0
        while i < len(self.projectiles):
            if self.projectiles[i].update(player):
                self.projectiles.pop(i)
            else:
                i += 1
                
        i = 0
        while i < len(self.hazards):
            if self.hazards[i].update():
                self.hazards.pop(i)
            else:
                i += 1
                
        i = 0
        while i < len(self.lasers):
            if self.lasers[i].update():
                self.lasers.pop(i)
            else:
                i += 1
                
        self.particles.update()
        
        if self.current_decision != 'chase' and self.current_decision != 'retreat' and self.dash_duration <= 0:
            self.vel_x *= 0.8
            if abs(self.vel_x) < 0.1:
                self.vel_x = 0

    def ai_decision(self, player):
        distance_to_player = abs(player.x - self.x)
        
        if player.attacking and len(self.playerAttackPattern) < 20:
            self.playerAttackPattern.append((player.x, player.y, player.dash_duration > 0))
            
            if len(self.playerAttackPattern) % 5 == 0:
                self.analyze_player_patterns()
        
        
        if self.phase >= 2 and random.random() < 0.25:  
            special_choice = random.random()
            if special_choice < 0.3:  
                self.current_decision = 'projectile'
                return
            elif special_choice < 0.7:  
                self.current_decision = 'hazard'
                return
        
        if distance_to_player < self.attack_distance:
            if self.attack_cooldown <= 0 and random.random() < self.aggression:
                self.current_decision = 'attack'
            elif distance_to_player < self.retreat_distance:
                self.current_decision = 'retreat'
            elif self.dash_cooldown <= 0 and random.random() < self.dash_preference:
                self.current_decision = 'dash'
            else:
                self.current_decision = 'chase'
        else:
            if self.dash_cooldown <= 0 and random.random() < self.dash_frequency:
                self.current_decision = 'dash'
            else:
                self.current_decision = 'chase'

    def analyze_player_patterns(self):
        positions = {}
        
        for x, y, is_dashing in self.playerAttackPattern:
            bucket_x = round(x / 50) * 50
            bucket_y = round(y / 50) * 50
            
            key = (bucket_x, bucket_y, is_dashing)
            if key in positions:
                positions[key] += 1
            else:
                positions[key] = 1
                
        for key, count in positions.items():
            if count >= 3:  
                if not any(a['type'] == 'position_preference' for a in self.adaptations):
                    self.attack_distance = 80  
                    self.adaptations.append({
                        'type': 'position_preference',
                        'position': key,
                        'description': "I see your preferred attack position..."
                    })
                    
        if len(self.playerAttackPattern) > 15:
            self.playerAttackPattern = self.playerAttackPattern[-10:]

    def adapt_to_player(self, player):
        if len(self.adaptations) >= self.max_adaptations:
            return
            
        adaptation_made = False
        
        player_aggression = player.attack_count / max(1, self.learning_timer / 60)  
        player_mobility = player.dash_count / max(1, self.learning_timer / 60)  
        player_defense = player.block_count / max(1, self.learning_timer / 60)  
        
        if player_aggression > 0.5 and not any(a['type'] == 'counter_aggression' for a in self.adaptations):
            self.dash_preference += 0.3
            
            self.adaptations.append({
                'type': 'counter_aggression',
                'description': "Your aggression will be your downfall..."
            })
            adaptation_made = True
            
        elif player_mobility > 0.3 and not any(a['type'] == 'counter_mobility' for a in self.adaptations):
            self.speed += 1.0
            self.dash_cooldown_max = max(30, self.dash_cooldown_max - 20)
            self.tracking_intensity += 0.3
            
            self.adaptations.append({
                'type': 'counter_mobility',
                'description': "You cannot escape me..."
            })
            adaptation_made = True
            
        elif player_defense > 0.2 and not any(a['type'] == 'counter_defense' for a in self.adaptations):
            self.attack_cooldown_max = max(5, self.attack_cooldown_max - 3)
            self.current_projectile_pattern = 'triple'  
            
            self.adaptations.append({
                'type': 'counter_defense',
                'description': "Your defenses are meaningless..."
            })
            adaptation_made = True
            
        elif not adaptation_made:
            player_positions = getattr(player, 'position_history', [])
            if len(player_positions) > 0:
                position_counts = {}
                for pos in player_positions:
                    bucket = (round(pos[0] / 100) * 100, round(pos[1] / 100) * 100)
                    position_counts[bucket] = position_counts.get(bucket, 0) + 1
                    
                most_common = max(position_counts.items(), key=lambda x: x[1])
                
                if most_common[1] > len(player_positions) * 0.4:  
                    self.adaptations.append({
                        'type': 'area_denial',
                        'position': most_common[0],
                        'description': "This area is no longer safe for you..."
                    })
                    adaptation_made = True
        
        if adaptation_made:
            self.current_adaptation_text = self.adaptations[-1]['description']
            self.adaptation_display_time = 180  
            
            player.attack_count = 0
            player.dash_count = 0
            player.block_count = 0

    def draw(self, surface):
        if not self.is_visible:
          
            if self.reappear_portal_active:
                
                portal_radius = 50
                portal_surface = pygame.Surface((portal_radius * 2, portal_radius * 2), pygame.SRCALPHA)
                
                for i in range(3):
                    color_value = max(0, min(255, 128 + int(math.sin(self.reappear_portal_timer * 0.1 + i) * 127)))
                    color = (color_value, 0, color_value, 150)
                    
                    thickness = 3 - i
                    pygame.draw.circle(
                        portal_surface,
                        color,
                        (portal_radius, portal_radius),
                        portal_radius - i * 10,
                        thickness
                    )
                
                
                for i in range(8):
                    angle = self.reappear_portal_timer * 0.05 + i * math.pi / 4
                    length = portal_radius * 0.7
                    start_x = portal_radius + math.cos(angle) * 15
                    start_y = portal_radius + math.sin(angle) * 15
                    end_x = portal_radius + math.cos(angle) * length
                    end_y = portal_radius + math.sin(angle) * length
                    
                    pygame.draw.line(
                        portal_surface,
                        (200, 0, 200, 150),
                        (start_x, start_y),
                        (end_x, end_y),
                        2
                    )
                
                
                surface.blit(
                    portal_surface,
                    (self.x + self.width // 2 - portal_radius, self.y + self.height // 2 - portal_radius)
                )
        else:
            if self.invincibility > 0:
                if self.invincibility % 6 < 3:
                    color = RED
                else:
                    color = PURPLE
            else:
                color = PURPLE
                
            pygame.draw.rect(surface, color, (self.x, self.y, self.width, self.height))
            
            eye_y = self.y + 10
            if self.facing_right:
                pygame.draw.circle(surface, WHITE, (int(self.x + self.width - 10), int(eye_y)), 5)
                pygame.draw.circle(surface, BLACK, (int(self.x + self.width - 10), int(eye_y)), 2)
            else:
                pygame.draw.circle(surface, WHITE, (int(self.x + 10), int(eye_y)), 5)
                pygame.draw.circle(surface, BLACK, (int(self.x + 10), int(eye_y)), 2)
        
        attack_rect = self.get_attack_rect()
        if attack_rect and self.is_visible:
            pygame.draw.rect(surface, RED, attack_rect)
            
        for projectile in self.projectiles:
            projectile.draw(surface)
            
        for hazard in self.hazards:
            hazard.draw(surface)
            
        for laser in self.lasers:
            laser.draw(surface)
            
        self.particles.draw(surface)
        
        if self.is_visible:
            health_width = 50
            health_height = 5
            health_x = self.x - (health_width - self.width) / 2
            health_y = self.y - 10
            
            pygame.draw.rect(surface, DARK_GRAY, (health_x, health_y, health_width, health_height))
            
            health_percent = max(0, self.health / self.max_health)
            pygame.draw.rect(surface, RED, (health_x, health_y, health_width * health_percent, health_height))
        
        if self.adaptation_display_time > 0:
            text = font_medium.render(self.current_adaptation_text, True, ORANGE)
            text_x = SCREEN_WIDTH // 2 - text.get_width() // 2
            text_y = SCREEN_HEIGHT // 2 - 50
            surface.blit(text, (text_x, text_y))
            
        if self.current_phase_message and self.adaptation_display_time > 0:
            text = font_medium.render(self.current_phase_message, True, PURPLE)
            text_x = SCREEN_WIDTH // 2 - text.get_width() // 2
            text_y = SCREEN_HEIGHT // 2 - 80
            surface.blit(text, (text_x, text_y))

    def update_phase_shift(self):
        self.phase_shift_timer += 1
        
        
        i = 0
        while i < len(self.lasers):
            if self.lasers[i].update():
                self.lasers.pop(i)
            else:
                i += 1
        
       
        if len(self.lasers) < 4 and self.phase_shift_timer % 90 == 0 and self.phase_shift_timer < self.phase_shift_duration - 120:
            x = random.randint(50, SCREEN_WIDTH - 100)
            speed = random.choice([-4, -3, 3, 4])
            laser = Laser(x, 0, speed, 10, lifetime=120, warning_time=30)
            self.lasers.append(laser)
        
        
        if self.phase_shift_timer >= self.phase_shift_duration - 120 and not self.reappear_portal_active:
            self.reappear_portal_active = True
            self.reappear_portal_timer = 0
        
        
        if self.reappear_portal_active:
            self.reappear_portal_timer += 1
            if self.reappear_portal_timer >= self.reappear_portal_duration:
                self.is_visible = True
                self.phase_shifting = False
                self.phase_shift_invulnerable = False
                
                self.lasers.clear()
                
                self.x = random.randint(100, SCREEN_WIDTH - 200)
                self.y = SCREEN_HEIGHT - 150 - self.height
                
                self.particles.add_particles(
                    self.x + self.width/2,
                    self.y + self.height/2,
                    PURPLE,
                    count=30,
                    speed=3,
                    size_range=(3, 8),
                    lifetime_range=(30, 60)
                )

class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 30
        self.height = 40
        self.vel_x = 0
        self.vel_y = 0
        self.speed = 5
        self.jump_power = -15
        self.gravity = 0.6
        self.is_jumping = False
        self.on_ground = False
        self.health = 100
        self.max_health = 100
        self.attack_cooldown = 0
        self.attack_duration = 0
        self.attack_duration_max = 12
        self.dash_cooldown = 0
        self.dash_cooldown_max = 45
        self.dash_duration = 0
        self.dash_duration_max = 10
        self.dash_speed = 12
        self.invincibility = 0
        self.attacking = False
        self.blocking = False
        self.facing_right = True
        self.color = GREEN
        self.particles = ParticleSystem()
        self.visible_during_dash = False  
        self.attack_count = 0
        self.dash_count = 0
        self.block_count = 0
        self.position_history = []
        self.position_history_max = 180
        
      
        self.dash_warning_shown = False
        self.dash_warning_timer = 0

    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)
    
    def get_attack_rect(self):
        if not self.attacking:
            return None
        
        attack_width = 40
        attack_height = 20
        attack_x = self.x + self.width if self.facing_right else self.x - attack_width
        attack_y = self.y + 10
        return pygame.Rect(attack_x, attack_y, attack_width, attack_height)
        
    def get_block_rect(self):
        if not self.blocking:
            return None
            
        block_width = 10
        block_height = 30
        block_x = self.x + self.width if self.facing_right else self.x - block_width
        block_y = self.y + 5
        return pygame.Rect(block_x, block_y, block_width, block_height)

    def take_damage(self, amount):

        if self.dash_duration > 0:
            return False
            
        if self.invincibility <= 0:
           
            block_rect = self.get_block_rect()
            if block_rect:
              
                self.health -= amount // 2
                self.block_count += 1
                
             
                self.particles.add_particles(
                    block_rect.x + block_rect.width // 2,
                    block_rect.y + block_rect.height // 2,
                    BLUE,
                    count=8,
                    speed=2,
                    size_range=(2, 5),
                    lifetime_range=(10, 30)
                )
            else:
           
                self.health -= amount
                
            self.invincibility = 60
            hit_sound.play()
            
         
            self.particles.add_particles(
                self.x + self.width // 2,
                self.y + self.height // 2,
                RED,
                count=10,
                speed=2,
                size_range=(2, 5),
                lifetime_range=(10, 30)
            )
            
            return True
        return False

    def move(self, keys, boss):
 
        self.position_history.append((self.x, self.y))
        if len(self.position_history) > self.position_history_max:
            self.position_history.pop(0)
            
    
        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1
            
        if self.dash_cooldown > 0:
            self.dash_cooldown -= 1
            
        if self.invincibility > 0:
            self.invincibility -= 1
            
        if self.attack_duration > 0:
            self.attack_duration -= 1
            if self.attack_duration <= 0:
                self.attacking = False
                
       
        if self.dash_duration > 0:
            self.dash_duration -= 1
            self.visible_during_dash = False  
            
           
            self.particles.add_particles(
                self.x + (0 if self.facing_right else self.width),
                self.y + self.height // 2,
                BLUE,
                count=3,  
                speed=2,  
                size_range=(2, 5), 
                lifetime_range=(10, 20)
            )
            
            
            self.particles.add_particles(
                self.x + self.width/2,
                self.y + self.height/2,
                (100, 200, 255),  
                count=2,
                speed=1,
                size_range=(3, 6),
                lifetime_range=(5, 15)
            )
            
           
            self.vel_x = self.dash_speed * (1 if self.facing_right else -1)
        else:
            self.visible_during_dash = True 
            
            if not self.attacking and not self.blocking:
                
                self.vel_x = 0
                
                if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                    self.vel_x = -self.speed
                    self.facing_right = False
                if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                    self.vel_x = self.speed
                    self.facing_right = True
                    
   
        if (keys[pygame.K_UP] or keys[pygame.K_w] or keys[pygame.K_SPACE]) and self.on_ground and not self.is_jumping:
            self.vel_y = self.jump_power
            self.is_jumping = True
            self.on_ground = False
            
    
        if (keys[pygame.K_z] or keys[pygame.K_j]) and not self.attacking and self.attack_cooldown <= 0 and not self.blocking:
            self.attacking = True
            self.attack_duration = self.attack_duration_max
            self.attack_cooldown = 20
            self.attack_count += 1
            player_attack_sound.play()
            
     
        self.blocking = (keys[pygame.K_x] or keys[pygame.K_k]) and self.on_ground and not self.attacking
        if self.blocking:
            self.block_count += 0.02  
            
  
        if (keys[pygame.K_c] or keys[pygame.K_l]) and self.dash_cooldown <= 0 and not self.blocking:
            self.dash_duration = self.dash_duration_max
            self.dash_cooldown = self.dash_cooldown_max
            self.dash_count += 1
            player_dash_sound.play()
            
  
        self.x += self.vel_x
        
 
        if not self.on_ground:
            self.vel_y += self.gravity
            self.y += self.vel_y
        
    
        if self.y >= SCREEN_HEIGHT - 100 - self.height:
            self.y = SCREEN_HEIGHT - 100 - self.height
            self.on_ground = True
            self.vel_y = 0
            self.is_jumping = False
        else:
            self.on_ground = False
            
  
        if self.x < 0:
            self.x = 0
        elif self.x > SCREEN_WIDTH - self.width:
            self.x = SCREEN_WIDTH - self.width
            
   
        self.particles.update()
        
     
        for projectile in boss.projectiles[:]:
            if projectile.get_rect().colliderect(self.get_rect()):
                self.take_damage(projectile.damage)
                boss.projectiles.remove(projectile)
                

        for hazard in boss.hazards:
            if hazard.active and hazard.get_rect().colliderect(self.get_rect()):
                self.take_damage(hazard.damage)
         
                self.invincibility = max(self.invincibility, 60)
                
     
        for laser in boss.lasers:
            if laser.active and laser.get_rect().colliderect(self.get_rect()):
   
                if self.dash_duration <= 0:
                    self.take_damage(laser.damage)
             
                    self.invincibility = max(self.invincibility, 60)

    def draw(self, surface):
  
        if self.visible_during_dash:
            if self.invincibility > 0:
            
                if self.invincibility % 6 < 3:
                    color = RED
                else:
                    color = self.color
            else:
                color = self.color
                
            pygame.draw.rect(surface, color, (self.x, self.y, self.width, self.height))
            
        
            eye_y = self.y + 10
            if self.facing_right:
                pygame.draw.circle(surface, WHITE, (int(self.x + self.width - 10), int(eye_y)), 4)
                pygame.draw.circle(surface, BLACK, (int(self.x + self.width - 10), int(eye_y)), 2)
            else:
                pygame.draw.circle(surface, WHITE, (int(self.x + 10), int(eye_y)), 4)
                pygame.draw.circle(surface, BLACK, (int(self.x + 10), int(eye_y)), 2)
            
    
            attack_rect = self.get_attack_rect()
            if attack_rect:
                pygame.draw.rect(surface, WHITE, attack_rect)
            
     
            block_rect = self.get_block_rect()
            if block_rect:
                pygame.draw.rect(surface, BLUE, block_rect)
        
    
        self.particles.draw(surface)
        
   
        health_width = 200
        health_height = 20
        health_x = 20
        health_y = 20
        
   
        pygame.draw.rect(surface, DARK_GRAY, (health_x, health_y, health_width, health_height))
        
     
        health_percent = max(0, self.health / self.max_health)
        pygame.draw.rect(surface, GREEN, (health_x, health_y, health_width * health_percent, health_height))
        
   
        health_text = font_small.render(f"Health: {self.health}/{self.max_health}", True, WHITE)
        surface.blit(health_text, (health_x + 10, health_y + 2))


class MirrorKnightsGame:
    def __init__(self):
        self.player = Player(100, SCREEN_HEIGHT - 200)
        self.boss = Boss(SCREEN_WIDTH - 150, SCREEN_HEIGHT - 200)
        self.game_state = "playing"  
        self.state_timer = 0
        self.particles = ParticleSystem()
        
    def reset(self):
        self.player = Player(100, SCREEN_HEIGHT - 200)
        self.boss = Boss(SCREEN_WIDTH - 150, SCREEN_HEIGHT - 200)
        self.game_state = "playing"
        self.state_timer = 0
        
    def update(self, keys):
        if self.game_state == "playing":
      
            self.player.move(keys, self.boss)
            self.boss.move(self.player)
            
        
            player_attack_rect = self.player.get_attack_rect()
            if player_attack_rect and player_attack_rect.colliderect(self.boss.get_rect()) and self.boss.is_visible:
           
                self.boss.take_damage(5)
                    
     
            boss_attack_rect = self.boss.get_attack_rect()
            if boss_attack_rect and boss_attack_rect.colliderect(self.player.get_rect()):
                self.player.take_damage(5)
            
        
            for laser in self.boss.lasers:
                if laser.warning_shown and not self.player.dash_warning_shown:
                    self.player.dash_warning_shown = True
                    self.player.dash_warning_timer = 180  
            
  
            if self.player.dash_warning_timer > 0:
                self.player.dash_warning_timer -= 1
                if self.player.dash_warning_timer <= 0:
                    self.player.dash_warning_shown = False
            

            if self.player.health <= 0:
                self.game_state = "game_over"
                self.state_timer = 180  
                game_over_sound.play()
            elif self.boss.health <= 0:
                self.game_state = "victory"
                self.state_timer = 180  
                victory_sound.play()
                
        elif self.game_state == "game_over" or self.game_state == "victory":
       
            self.state_timer -= 1
            if self.state_timer <= 0:
          
                if self.game_state == "game_over":
                    for _ in range(50):
                        self.particles.add_particles(
                            self.player.x + self.player.width/2,
                            self.player.y + self.player.height/2,
                            RED,
                            count=1,
                            speed=3,
                            size_range=(3, 8),
                            lifetime_range=(30, 90)
                        )
                else: 
                    for _ in range(50):
                        self.particles.add_particles(
                            self.boss.x + self.boss.width/2,
                            self.boss.y + self.boss.height/2,
                            GREEN,
                            count=1,
                            speed=3,
                            size_range=(3, 8),
                            lifetime_range=(30, 90)
                        )
                        
            
                if keys[pygame.K_r]:
                    self.reset()
        
  
        self.particles.update()
    
    def draw(self, surface):

        surface.fill(BLACK)
        

        pygame.draw.rect(surface, DARK_GRAY, (0, SCREEN_HEIGHT - 100, SCREEN_WIDTH, 100))
        

        self.player.draw(surface)
        self.boss.draw(surface)
        

        self.particles.draw(surface)
        

        boss_health_width = 200
        boss_health_height = 20
        boss_health_x = SCREEN_WIDTH - boss_health_width - 20
        boss_health_y = 20
        
       
        pygame.draw.rect(surface, DARK_GRAY, (boss_health_x, boss_health_y, boss_health_width, boss_health_height))
        
 
        boss_health_percent = max(0, self.boss.health / self.boss.max_health)
        pygame.draw.rect(surface, PURPLE, (boss_health_x, boss_health_y, boss_health_width * boss_health_percent, boss_health_height))
        

        boss_health_text = font_small.render(f"Boss: {self.boss.health}/{self.boss.max_health}", True, WHITE)
        surface.blit(boss_health_text, (boss_health_x + 10, boss_health_y + 2))
        
  
        phase_text = font_small.render(f"Phase: {self.boss.phase}", True, PURPLE)
        surface.blit(phase_text, (boss_health_x + boss_health_width - 80, boss_health_y + 25))
        

        if self.game_state == "game_over":
          
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))  
            surface.blit(overlay, (0, 0))
            
  
            game_over_text = font_large.render("GAME OVER", True, RED)
            text_x = SCREEN_WIDTH // 2 - game_over_text.get_width() // 2
            text_y = SCREEN_HEIGHT // 2 - 50
            surface.blit(game_over_text, (text_x, text_y))
            
         
            if self.state_timer <= 0:
                restart_text = font_medium.render("Press R to restart", True, WHITE)
                restart_x = SCREEN_WIDTH // 2 - restart_text.get_width() // 2
                restart_y = SCREEN_HEIGHT // 2 + 20
                surface.blit(restart_text, (restart_x, restart_y))
                
        elif self.game_state == "victory":
     
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))  
            surface.blit(overlay, (0, 0))
            
          
            victory_text = font_large.render("VICTORY!", True, GREEN)
            text_x = SCREEN_WIDTH // 2 - victory_text.get_width() // 2
            text_y = SCREEN_HEIGHT // 2 - 50
            surface.blit(victory_text, (text_x, text_y))
            

            if self.state_timer <= 0:
                restart_text = font_medium.render("Press R to restart", True, WHITE)
                restart_x = SCREEN_WIDTH // 2 - restart_text.get_width() // 2
                restart_y = SCREEN_HEIGHT // 2 + 20
                surface.blit(restart_text, (restart_x, restart_y))
                
 
        if self.game_state == "playing":
            controls_text = font_small.render("Move: Arrow Keys | Attack: Z | Block: X | Dash: C | Jump: Space", True, LIGHT_GRAY)
            surface.blit(controls_text, (20, SCREEN_HEIGHT - 30))

   
        if self.player.dash_warning_timer > 0:
            warning_text = font_medium.render("Press C to dash through lasers!", True, YELLOW)
            warning_x = SCREEN_WIDTH // 2 - warning_text.get_width() // 2
            warning_y = SCREEN_HEIGHT // 2 - 100
            
       
            if (self.player.dash_warning_timer // 10) % 2 == 0:
                surface.blit(warning_text, (warning_x, warning_y))


def main():
    game = MirrorKnightsGame()
    running = True
    
    while running:
      
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                pygame.quit()
                sys.exit()
        
   
        keys = pygame.key.get_pressed()
        
 
        game.update(keys)
        
    
        game.draw(screen)
        

        pygame.display.flip()
        

        clock.tick(FPS)

if __name__ == '__main__':
    main()
