#! /usr/bin/env python

import pygame
from pygame.locals import *

import gtk, sys

# Change number for change colors (RGB)
BLANCO = (255, 255, 255)
NEGRO = (0, 0, 0)

class MiJuego():
    def __init__(self):
        pass

    def juego_loop(self):
        pygame.init()
        global x, y, fuente, texto
        x = gtk.gdk.screen_width()
        y = gtk.gdk.screen_height() - 55
        # Change the following text to change the program name
        pygame.display.set_caption('Hello world!')
        
        fuente = pygame.font.SysFont(None, 48)
        # Change "Hello World!" to change the main message
        texto = fuente.render('Hello world!', True, BLANCO, NEGRO)

        reloj = pygame.time.Clock()
        pantalla = pygame.display.get_surface()

        while 1:
            while gtk.events_pending():
                gtk.main_iteration()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    # Change "Juego Finalizado" to change the exit message (log)
                    exit("Juego finalizado")
                elif event.type == pygame.VIDEORESIZE:
                    pygame.display.set_mode(event.size, pygame.RESIZABLE)


            pantalla.fill(NEGRO)

            pantalla.blit(texto, ((x / 2) - (x / 10), (y / 2) - (y / 10)))
            pygame.display.flip()

            # Try to stay at 30 FPS
            reloj.tick(30)


if __name__ == "__main__":
    MiJuego()
