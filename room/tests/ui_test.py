# pylint: disable=missing-docstring

from asyncio import CancelledError, new_event_loop
from collections.abc import Callable
from math import sqrt
import os
from pathlib import Path
from socket import gethostname
from threading import Thread
from typing import TypedDict, cast
from unittest import TestCase

from selenium.webdriver import Firefox, FirefoxService, Remote
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.options import ArgOptions
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.expected_conditions import (presence_of_element_located,
                                                            text_to_be_present_in_element_attribute)
from selenium.webdriver.support.wait import WebDriverWait

from room.game import OnlineRoom, Tile, DEFAULT_BLUEPRINTS
from room.__main__ import main

class Location(TypedDict):
    x: int
    y: int

def distance(a: Location, b: Location) -> float:
    return sqrt((b['x'] - a['x']) ** 2 + (b['y'] - a['y']) ** 2)

def element_at(element: WebElement, location: Location, *,
               delta: float = 0) -> Callable[[Remote], bool]:
    def func(_: Remote) -> bool:
        return distance(cast(Location, element.location), location) <= delta
    return func

class UITest(TestCase):
    TIMEOUT = 1
    MEMBER_SPEED = OnlineRoom.HEIGHT / 2 * Tile.SIZE

    def setUp(self) -> None:
        def run() -> None:
            self.loop = new_event_loop()
            self.task = self.loop.create_task(main())
            try:
                self.loop.run_until_complete(self.task)
            except CancelledError:
                self.loop.close()
        self.thread = Thread(target=run)
        self.thread.start()

        if webdriver_url := os.environ.get('WEBDRIVER_URL'):
            options = ArgOptions()
            options.set_capability(
                'browserName', os.environ.get('WEBDRIVER_BROWSER', 'firefox')) # type: ignore[misc]
            options.set_capability('platformName',
                                   os.environ.get('WEBDRIVER_PLATFORM', '')) # type: ignore[misc]
            name = self.id()
            if subject := os.environ.get('WEBDRIVER_SUBJECT'):
                name = f'{name} ({subject})'
            options.set_capability(
                'sauce:options', { # type: ignore[misc]
                    'name': name,
                    'tunnelName': os.environ.get('WEBDRIVER_TUNNEL', '') # type: ignore[misc]
                })
            self.browser = Remote(command_executor=webdriver_url, options=options)
        else:
            # Work around Selenium not finding Firefox installed as snap (see
            # https://github.com/SeleniumHQ/selenium/issues/13169)
            path = Path('/snap/bin/geckodriver')
            self.browser = Firefox(
                service=FirefoxService(
                    executable_path=str(path) if path.exists() else None)) # type: ignore[arg-type]
        self.wait = WebDriverWait(self.browser, self.TIMEOUT)

    def tearDown(self) -> None:
        self.browser.quit()
        self.loop.call_soon_threadsafe(self.task.cancel) # type: ignore[misc]
        self.thread.join()

    def test(self) -> None:
        # View room
        self.browser.get(f'http://{gethostname()}:8080')
        tile = self.wait.until(presence_of_element_located((By.CSS_SELECTOR, '.room-game-tile')))

        # Start tutorial
        start_button = self.browser.find_element(By.CSS_SELECTOR, '.room-howto-start')
        start_button.click()
        self.assertFalse(start_button.is_displayed())

        # View inventory
        equipment = self.browser.find_element(By.CSS_SELECTOR, '.room-game-equipment')
        equipment.click()
        index = next(i for i, blueprint_id in enumerate(DEFAULT_BLUEPRINTS)
                     if blueprint_id == 'wall-door-closed')
        item = self.browser.find_element(By.CSS_SELECTOR,
                                         f'room-inventory ul > :nth-child({index + 2}) .tile')
        self.assertTrue(item.is_displayed())

        # Select item
        item.click()
        self.assertEqual(
            equipment.find_element(By.CSS_SELECTOR, 'img').get_property('src'), # type: ignore[misc]
            DEFAULT_BLUEPRINTS['wall-door-closed'].image)

        # View about room
        equipment.click()
        self.browser.find_element(By.CSS_SELECTOR, '.room-inventory-about').click()
        about_h2 = self.browser.find_element(By.CSS_SELECTOR, 'room-about h2')
        self.assertEqual(about_h2.text, 'New Room')

        # Update room details
        self.browser.find_element(By.CSS_SELECTOR, '.room-about-edit').click()
        form = self.browser.find_element(By.CSS_SELECTOR, 'room-editor form')
        title_input = form.find_element(By.NAME, 'title')
        title_input.clear()
        title_input.send_keys('Cat Colony')
        form.find_element(By.NAME, 'description').send_keys('Hangout for the cats.')
        form.find_element(By.CSS_SELECTOR, 'button:not([type])').click()
        self.assertEqual(about_h2.text, 'Cat Colony')
        header = self.browser.find_element(By.CSS_SELECTOR, 'room-about room-window-header')
        cast(
            WebElement,
            header.shadow_root.find_element(By.CSS_SELECTOR, '.room-window-header-close')
        ).click()

        # View workshop
        equipment.click()
        self.browser.find_element(By.CSS_SELECTOR, '.room-inventory-open-workshop').click()
        create_blueprint_item = self.browser.find_element(By.CSS_SELECTOR,
                                                          '.room-workshop-create-blueprint')
        self.assertTrue(create_blueprint_item.is_displayed())

        # Create blueprint
        create_blueprint_item.click()
        effects_button = self.browser.find_element(By.CSS_SELECTOR, '.room-blueprint-effects')
        effects_button.click()
        self.browser.find_element(By.CSS_SELECTOR, '.room-blueprint-effects-add-cause p').click()
        self.browser.find_element(By.CSS_SELECTOR, '.room-blueprint-effects-use-cause').click()
        self.browser.find_element(By.CSS_SELECTOR, '.room-effect-list-add-effect').click()
        self.browser.find_element(
            By.CSS_SELECTOR, '.room-effect-list-transform-tile-effect'
        ).click()
        self.browser.find_element(By.CSS_SELECTOR, 'room-blueprint-effects button').click()
        self.assertEqual(effects_button.text, '1 Effect')
        self.browser.find_element(By.CSS_SELECTOR, 'room-blueprint button').click()
        self.browser.find_element(By.CSS_SELECTOR, '.room-workshop-close').click()

        # Move
        member = self.browser.find_element(By.CSS_SELECTOR, '.room-game-member')
        location = cast(Location, tile.location)
        hud = self.browser.find_element(By.CSS_SELECTOR, '.room-game-hud')
        scale = cast(dict[str, int], hud.size)['height'] / (OnlineRoom.HEIGHT * Tile.SIZE)
        t = distance(cast(Location, member.location), location) / (self.MEMBER_SPEED * scale)
        actions = ActionChains(self.browser)
        actions.click_and_hold(tile).perform()
        WebDriverWait(self.browser, t + self.TIMEOUT).until(
            element_at(member, location, delta=scale))
        actions.reset_actions()

        # Place tile
        actions.click(tile).perform()
        self.wait.until(
            text_to_be_present_in_element_attribute(
                (By.CSS_SELECTOR, '.room-game-tile img'), 'src',
                DEFAULT_BLUEPRINTS['wall-door-closed'].image))

        # Use
        equipment.click()
        self.browser.find_element(By.CSS_SELECTOR, '.room-inventory-no-item').click()
        actions.click(tile).perform()
        self.wait.until(
            text_to_be_present_in_element_attribute(
                (By.CSS_SELECTOR, '.room-game-tile img'), 'src',
                DEFAULT_BLUEPRINTS['wall-door-open'].image))
